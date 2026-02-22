"""Core TMP frame structures, codec helpers, and handshake session logic."""

from __future__ import annotations

import logging
import secrets
import struct
import time
import zlib
from dataclasses import astuple, dataclass
from typing import Protocol

from tmpkit.lib.constants import TmpCtrlCode, TMP_CRC32_PLACEHOLDER
from tmpkit.lib.structutil import unpack_exact

logger = logging.getLogger(__name__)


class TmpProtocolError(RuntimeError):
    pass


class ReadableWritable(Protocol):
    def recv(self, n: int) -> bytes: ...

    def sendall(self, data: bytes) -> None: ...

    def close(self) -> None: ...


def _crc32(data: bytes) -> int:
    # CRC32 is defined as an unsigned 32-bit value.
    return zlib.crc32(data) & 0xFFFFFFFF


_GPH_HDR_STRUCT = struct.Struct("!4B")
_TPH_HDR_STRUCT = struct.Struct("!HBBII")


def _read_exact(stream: ReadableWritable, n: int) -> bytes:
    out = bytearray()
    while len(out) < n:
        chunk = stream.recv(n - len(out))
        if not chunk:
            raise TmpProtocolError(f"unexpected EOF (wanted {n} bytes, got {len(out)})")
        out += chunk
    return bytes(out)


@dataclass(frozen=True, slots=True)
class TmpGphHeader:
    main_ver: int
    second_ver: int
    ctrl_code: int
    reason_code: int = 0

    def pack(self) -> bytes:
        return _GPH_HDR_STRUCT.pack(*astuple(self))

    @staticmethod
    def unpack(data: bytes) -> "TmpGphHeader":
        values = unpack_exact(
            _GPH_HDR_STRUCT,
            data,
            label="GPH header",
            exc_type=TmpProtocolError,
        )
        return TmpGphHeader(*values)


@dataclass(frozen=True, slots=True)
class TmpTphHeader:
    payload_length: int
    tmp_flag: int = 0
    tmp_error_code: int = 0
    serial_no: int = 0
    checksum: int = TMP_CRC32_PLACEHOLDER

    def pack(self) -> bytes:
        return _TPH_HDR_STRUCT.pack(*astuple(self))

    @staticmethod
    def unpack(data: bytes) -> "TmpTphHeader":
        values = unpack_exact(
            _TPH_HDR_STRUCT,
            data,
            label="TPH header",
            exc_type=TmpProtocolError,
        )
        return TmpTphHeader(*values)


@dataclass(frozen=True, slots=True)
class TmpFrame:
    gph: TmpGphHeader
    tph: TmpTphHeader | None
    payload: bytes = b""

    def pack(self) -> bytes:
        if self.tph is None:
            return self.gph.pack()
        if len(self.payload) != self.tph.payload_length:
            raise TmpProtocolError("TPH payload_length does not match payload")

        tph_for_crc = TmpTphHeader(
            payload_length=self.tph.payload_length,
            tmp_flag=self.tph.tmp_flag,
            tmp_error_code=self.tph.tmp_error_code,
            serial_no=self.tph.serial_no,
            checksum=TMP_CRC32_PLACEHOLDER,
        )
        frame_for_crc = self.gph.pack() + tph_for_crc.pack() + self.payload
        checksum = _crc32(frame_for_crc)

        tph_final = TmpTphHeader(
            payload_length=self.tph.payload_length,
            tmp_flag=self.tph.tmp_flag,
            tmp_error_code=self.tph.tmp_error_code,
            serial_no=self.tph.serial_no,
            checksum=checksum,
        )
        return self.gph.pack() + tph_final.pack() + self.payload

    @staticmethod
    def read_from(stream: ReadableWritable) -> "TmpFrame":
        gph = TmpGphHeader.unpack(_read_exact(stream, _GPH_HDR_STRUCT.size))

        try:
            ctrl: int | TmpCtrlCode = TmpCtrlCode(gph.ctrl_code)
        except ValueError:
            ctrl = gph.ctrl_code

        logger.debug("TMP recv GPH ctrl=%s reason=%s", ctrl, gph.reason_code)
        match gph.ctrl_code:
            case TmpCtrlCode.DATA_TRANSFER:
                tph = TmpTphHeader.unpack(_read_exact(stream, _TPH_HDR_STRUCT.size))
                payload = _read_exact(stream, tph.payload_length)
            case _:
                return TmpFrame(gph=gph, tph=None, payload=b"")

        tph_for_crc = TmpTphHeader(
            payload_length=tph.payload_length,
            tmp_flag=tph.tmp_flag,
            tmp_error_code=tph.tmp_error_code,
            serial_no=tph.serial_no,
            checksum=TMP_CRC32_PLACEHOLDER,
        )
        calc = _crc32(gph.pack() + tph_for_crc.pack() + payload)
        if calc != tph.checksum:
            logger.debug(
                "TMP checksum mismatch (ctrl=%s serial=%s expected=%#x got=%#x)",
                ctrl,
                tph.serial_no,
                tph.checksum,
                calc,
            )
            raise TmpProtocolError(
                f"TMP checksum mismatch: expected {tph.checksum:#x}, got {calc:#x}"
            )

        return TmpFrame(gph=gph, tph=tph, payload=payload)


class TmpCodec:
    def __init__(self, *, main_ver: int = 1, second_ver: int = 1) -> None:
        self._main_ver = int(main_ver)
        self._second_ver = int(second_ver)

    def pack_assoc_req(self) -> bytes:
        return TmpFrame(
            gph=TmpGphHeader(
                self._main_ver, self._second_ver, TmpCtrlCode.ASSOC_REQ, 0
            ),
            tph=None,
        ).pack()

    def pack_assoc_accept_ack(self) -> bytes:
        return TmpFrame(
            gph=TmpGphHeader(
                self._main_ver, self._second_ver, TmpCtrlCode.ASSOC_ACCEPT, 0
            ),
            tph=None,
        ).pack()

    def pack_hello(self) -> bytes:
        return TmpFrame(
            gph=TmpGphHeader(self._main_ver, self._second_ver, TmpCtrlCode.HELLO, 0),
            tph=None,
        ).pack()

    def pack_bye(self) -> bytes:
        return TmpFrame(
            gph=TmpGphHeader(self._main_ver, self._second_ver, TmpCtrlCode.BYE, 0),
            tph=None,
        ).pack()

    def pack_data(
        self,
        payload: bytes,
        *,
        tmp_flag: int = 0,
        tmp_error_code: int = 0,
        serial_no: int | None = None,
    ) -> bytes:
        serial = secrets.randbits(32) if serial_no is None else int(serial_no)
        body = bytes(payload)
        frame = TmpFrame(
            gph=TmpGphHeader(
                self._main_ver, self._second_ver, TmpCtrlCode.DATA_TRANSFER, 0
            ),
            tph=TmpTphHeader(
                payload_length=len(body),
                tmp_flag=int(tmp_flag),
                tmp_error_code=int(tmp_error_code),
                serial_no=serial,
            ),
            payload=body,
        )
        return frame.pack()


class TmpSession:
    def __init__(self, stream: ReadableWritable, *, codec: TmpCodec) -> None:
        self._stream = stream
        self._codec = codec

    def close(self) -> None:
        logger.debug("TMP session closing")
        try:
            self._stream.sendall(self._codec.pack_bye())
        except Exception:
            pass
        try:
            self._stream.close()
        except Exception:
            pass

    def assoc(
        self, *, timeout_seconds: float = 8.0, send_client_hello: bool = False
    ) -> None:
        logger.info("TMP assoc start (timeout=%ss)", float(timeout_seconds))
        self._stream.sendall(self._codec.pack_assoc_req())

        deadline = time.time() + float(timeout_seconds)
        while time.time() < deadline:
            frame = TmpFrame.read_from(self._stream)
            match frame.gph.ctrl_code:
                case TmpCtrlCode.HELLO:
                    logger.debug("TMP assoc: got HELLO")
                    continue
                case TmpCtrlCode.ASSOC_ACCEPT:
                    logger.info("TMP assoc accepted")
                    self._stream.sendall(self._codec.pack_assoc_accept_ack())
                    if send_client_hello:
                        logger.debug("TMP assoc: sending client HELLO")
                        self._stream.sendall(self._codec.pack_hello())
                    return
                case TmpCtrlCode.ASSOC_REFUSE:
                    logger.warning("TMP assoc refused")
                    raise TmpProtocolError("association refused")
                case _:
                    continue

        logger.warning("TMP assoc timeout")
        raise TmpProtocolError("association timeout")
