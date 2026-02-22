"""TMP/AppV2 packet structures, codecs, and session request flow."""

from __future__ import annotations

import json
import logging
import secrets
import struct
import sys
import time
import zlib
from dataclasses import astuple, dataclass
from typing import Any, TextIO

from tmpkit.lib.constants import AppV2Flag, TmpCtrlCode, TMP_CRC32_PLACEHOLDER
from tmpkit.lib.tmp import (
    ReadableWritable,
    TmpFrame,
    TmpGphHeader,
    TmpProtocolError,
    TmpTphHeader,
)
from tmpkit.lib.structutil import unpack_exact

logger = logging.getLogger(__name__)


def _crc32(data: bytes) -> int:
    # CRC32 is defined as an unsigned 32-bit value.
    return zlib.crc32(data) & 0xFFFFFFFF


def _pretty_debug_payload(data: bytes) -> str:
    """Best-effort pretty formatting for debug output.

    If `data` is UTF-8 JSON, returns a stable pretty-printed string.
    Otherwise returns a short, safe representation.
    """

    try:
        txt = data.decode("utf-8")
    except Exception:
        return f"<bytes len={len(data)} hex={data[:96].hex()}{'…' if len(data) > 96 else ''}>"

    try:
        obj = json.loads(txt)
    except Exception:
        preview = txt[:512]
        suffix = "…" if len(txt) > 512 else ""
        return f"<text len={len(txt)}>{preview}{suffix}"

    match obj:
        case dict() | list():
            return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False)
        case _:
            return json.dumps(obj, ensure_ascii=False)


_BUSINESS_HDR_STRUCT = struct.Struct("!BB")
_APPV2_HDR_STRUCT = struct.Struct("!HBBHIII")


@dataclass(frozen=True, slots=True)
class TmpBusinessHeader:
    business_type: int
    business_ver: int

    def pack(self) -> bytes:
        return _BUSINESS_HDR_STRUCT.pack(*astuple(self))

    @staticmethod
    def unpack(data: bytes) -> "TmpBusinessHeader":
        values = unpack_exact(
            _BUSINESS_HDR_STRUCT,
            data,
            label="BPH header",
            exc_type=TmpProtocolError,
        )
        return TmpBusinessHeader(*values)


@dataclass(frozen=True, slots=True)
class TmpAppV2Header:
    op_code: int
    appv2_flag: int
    appv2_error_code: int
    trans_id: int
    all_payload_checksum: int
    total_payload_size: int
    start_idx_or_ack_size: int

    def pack(self) -> bytes:
        return _APPV2_HDR_STRUCT.pack(*astuple(self))

    @staticmethod
    def unpack(data: bytes) -> "TmpAppV2Header":
        values = unpack_exact(
            _APPV2_HDR_STRUCT,
            data,
            label="AppV2 header",
            exc_type=TmpProtocolError,
        )
        return TmpAppV2Header(*values)


@dataclass(frozen=True, slots=True)
class TmpAppV2Packet:
    frame: TmpFrame
    business: TmpBusinessHeader
    appv2: TmpAppV2Header
    chunk: bytes

    @staticmethod
    def from_tmp_frame(frame: TmpFrame) -> "TmpAppV2Packet":
        match frame.tph:
            case None:
                raise TmpProtocolError("not a data frame")
            case _:
                pass
        bph_size = _BUSINESS_HDR_STRUCT.size
        hdr_size = _APPV2_HDR_STRUCT.size
        if len(frame.payload) < bph_size + hdr_size:
            raise TmpProtocolError("TMP payload too small for AppV2")

        business = TmpBusinessHeader.unpack(frame.payload[:bph_size])
        appv2 = TmpAppV2Header.unpack(frame.payload[bph_size : bph_size + hdr_size])
        chunk = frame.payload[bph_size + hdr_size :]
        return TmpAppV2Packet(frame=frame, business=business, appv2=appv2, chunk=chunk)


class TmpAppV2Codec:
    def __init__(
        self,
        *,
        main_ver: int = 1,
        second_ver: int = 1,
        business_type: int = 1,
        business_ver: int = 2,
    ) -> None:
        self._main_ver = int(main_ver)
        self._second_ver = int(second_ver)
        self._business_type = int(business_type)
        self._business_ver = int(business_ver)

    def pack_assoc_req(self) -> bytes:
        return TmpFrame(
            gph=TmpGphHeader(
                self._main_ver, self._second_ver, TmpCtrlCode.ASSOC_REQ, 0
            ),
            tph=None,
            payload=b"",
        ).pack()

    def pack_assoc_accept_ack(self) -> bytes:
        return TmpFrame(
            gph=TmpGphHeader(
                self._main_ver, self._second_ver, TmpCtrlCode.ASSOC_ACCEPT, 0
            ),
            tph=None,
            payload=b"",
        ).pack()

    def pack_hello(self) -> bytes:
        return TmpFrame(
            gph=TmpGphHeader(self._main_ver, self._second_ver, TmpCtrlCode.HELLO, 0),
            tph=None,
            payload=b"",
        ).pack()

    def pack_bye(self) -> bytes:
        return TmpFrame(
            gph=TmpGphHeader(self._main_ver, self._second_ver, TmpCtrlCode.BYE, 0),
            tph=None,
            payload=b"",
        ).pack()

    def pack_appv2_pull(
        self,
        *,
        op_code: int,
        trans_id: int,
        payload: bytes,
        start_idx: int = 0,
    ) -> bytes:
        appv2 = TmpAppV2Header(
            op_code=int(op_code),
            appv2_flag=AppV2Flag.PULL,
            appv2_error_code=0,
            trans_id=int(trans_id),
            all_payload_checksum=_crc32(payload),
            total_payload_size=len(payload),
            start_idx_or_ack_size=int(start_idx),
        )
        body = (
            TmpBusinessHeader(self._business_type, self._business_ver).pack()
            + appv2.pack()
            + bytes(payload)
        )
        frame = TmpFrame(
            gph=TmpGphHeader(
                self._main_ver, self._second_ver, TmpCtrlCode.DATA_TRANSFER, 0
            ),
            tph=TmpTphHeader(payload_length=len(body), serial_no=secrets.randbits(32)),
            payload=body,
        )
        return frame.pack()

    def pack_appv2_push_chunk(
        self,
        *,
        op_code: int,
        trans_id: int,
        all_payload_checksum: int,
        total_payload_size: int,
        start_idx: int,
        chunk: bytes,
    ) -> bytes:
        appv2 = TmpAppV2Header(
            op_code=int(op_code),
            appv2_flag=AppV2Flag.PUSH,
            appv2_error_code=0,
            trans_id=int(trans_id),
            all_payload_checksum=int(all_payload_checksum),
            total_payload_size=int(total_payload_size),
            start_idx_or_ack_size=int(start_idx),
        )
        body = (
            TmpBusinessHeader(self._business_type, self._business_ver).pack()
            + appv2.pack()
            + bytes(chunk)
        )
        frame = TmpFrame(
            gph=TmpGphHeader(
                self._main_ver, self._second_ver, TmpCtrlCode.DATA_TRANSFER, 0
            ),
            tph=TmpTphHeader(payload_length=len(body), serial_no=secrets.randbits(32)),
            payload=body,
        )
        return frame.pack()

    def pack_appv2_push_ack(
        self, *, op_code: int, trans_id: int, ack_size: int
    ) -> bytes:
        appv2 = TmpAppV2Header(
            op_code=int(op_code),
            appv2_flag=AppV2Flag.PUSH_ACK,
            appv2_error_code=0,
            trans_id=int(trans_id),
            all_payload_checksum=0,
            total_payload_size=0,
            start_idx_or_ack_size=int(ack_size),
        )
        body = (
            TmpBusinessHeader(self._business_type, self._business_ver).pack()
            + appv2.pack()
        )
        frame = TmpFrame(
            gph=TmpGphHeader(
                self._main_ver, self._second_ver, TmpCtrlCode.DATA_TRANSFER, 0
            ),
            tph=TmpTphHeader(payload_length=len(body), serial_no=secrets.randbits(32)),
            payload=body,
        )
        return frame.pack()


class TmpAppV2Session:
    def __init__(
        self,
        stream: ReadableWritable,
        *,
        codec: TmpAppV2Codec,
        debug_raw: bool = False,
        debug_stream: TextIO | None = None,
    ) -> None:
        self._stream = stream
        self._codec = codec
        self._next_trans_id = 1
        self._debug_raw = bool(debug_raw)
        self._debug_stream = sys.stderr if debug_stream is None else debug_stream

    def _debug_print(self, msg: str) -> None:
        if not self._debug_raw:
            return
        try:
            self._debug_stream.write(str(msg).rstrip("\n") + "\n")
            self._debug_stream.flush()
        except Exception:
            # Debug output should never break protocol execution.
            pass

    def close(self) -> None:
        logger.debug("AppV2 session closing")
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
        logger.info("AppV2 assoc start (timeout=%ss)", float(timeout_seconds))
        self._stream.sendall(self._codec.pack_assoc_req())

        deadline = time.time() + float(timeout_seconds)
        while time.time() < deadline:
            frame = TmpFrame.read_from(self._stream)
            match frame.gph.ctrl_code:
                case TmpCtrlCode.HELLO:
                    logger.debug("AppV2 assoc: got HELLO")
                    continue
                case TmpCtrlCode.ASSOC_ACCEPT:
                    logger.info("AppV2 assoc accepted")
                    self._stream.sendall(self._codec.pack_assoc_accept_ack())
                    if send_client_hello:
                        logger.debug("AppV2 assoc: sending client HELLO")
                        self._stream.sendall(self._codec.pack_hello())
                    return
                case TmpCtrlCode.ASSOC_REFUSE:
                    logger.warning("AppV2 assoc refused")
                    raise TmpProtocolError("association refused")
                case _:
                    continue

        logger.warning("AppV2 assoc timeout")
        raise TmpProtocolError("association timeout")

    def request_appv2(
        self,
        *,
        op_code: int,
        payload: bytes,
        timeout_seconds: float = 8.0,
        max_chunk_size: int = 8156,
    ) -> bytes:
        trans_id = self._next_trans_id & 0xFFFF
        self._next_trans_id += 1

        payload = bytes(payload)

        start_ts = time.time()
        logger.debug(
            "AppV2 request start (op=%s trans=%s bytes=%s timeout=%ss)",
            int(op_code),
            int(trans_id),
            len(payload),
            float(timeout_seconds),
        )
        if self._debug_raw:
            logger.debug(
                "AppV2 raw debug enabled for op=%s trans=%s",
                int(op_code),
                int(trans_id),
            )
        if self._debug_raw:
            self._debug_print(
                f"== AppV2 op={int(op_code)} trans={int(trans_id)} request =="
            )
            self._debug_print(_pretty_debug_payload(payload))
        all_crc = _crc32(payload)
        total = len(payload)

        # Match the Android app behavior (see com.tplink.b.i):
        # - client PUSHes the request payload (possibly chunked)
        # - waits for PUSH_ACK confirming the upload
        # - then issues PULL(s) to retrieve the response
        if total == 0:
            self._stream.sendall(
                self._codec.pack_appv2_push_chunk(
                    op_code=op_code,
                    trans_id=trans_id,
                    all_payload_checksum=all_crc,
                    total_payload_size=0,
                    start_idx=0,
                    chunk=b"",
                )
            )
        else:
            start_idx = 0
            while start_idx < total:
                chunk = payload[start_idx : start_idx + int(max_chunk_size)]
                logger.debug(
                    "AppV2 request PUSH chunk (op=%s trans=%s start=%s size=%s)",
                    int(op_code),
                    int(trans_id),
                    int(start_idx),
                    len(chunk),
                )
                self._stream.sendall(
                    self._codec.pack_appv2_push_chunk(
                        op_code=op_code,
                        trans_id=trans_id,
                        all_payload_checksum=all_crc,
                        total_payload_size=total,
                        start_idx=0,
                        chunk=chunk,
                    )
                )
                start_idx += len(chunk)

        sent_initial_pull = False
        if total == 0:
            logger.debug("AppV2 request initial PULL (empty request payload)")
            self._stream.sendall(
                self._codec.pack_appv2_pull(
                    op_code=op_code,
                    trans_id=trans_id,
                    payload=b"",
                    start_idx=0,
                )
            )
            sent_initial_pull = True

        last_pulled_from = 0

        deadline = time.time() + float(timeout_seconds)
        chunks: dict[int, bytes] = {}
        expected_total: int | None = None
        expected_crc: int | None = None
        last_seen_end = 0

        while time.time() < deadline:
            try:
                frame = TmpFrame.read_from(self._stream)
            except TimeoutError:
                continue
            except OSError as e:
                import socket

                if isinstance(e, socket.timeout):
                    continue
                raise

            if frame.tph is None:
                continue

            pkt = TmpAppV2Packet.from_tmp_frame(frame)
            if pkt.appv2.trans_id != trans_id or pkt.appv2.op_code != int(op_code):
                continue

            flag = AppV2Flag(pkt.appv2.appv2_flag)

            logger.debug(
                "AppV2 recv (op=%s trans=%s flag=%s start_or_ack=%s chunk=%s)",
                int(op_code),
                int(trans_id),
                int(flag),
                int(pkt.appv2.start_idx_or_ack_size),
                len(pkt.chunk),
            )

            match pkt.appv2.appv2_error_code:
                case int() as code if code != 0:
                    logger.warning(
                        "AppV2 error (op=%s trans=%s flag=%s code=%s)",
                        int(op_code),
                        int(trans_id),
                        int(flag),
                        int(code),
                    )
                    raise TmpProtocolError(
                        f"AppV2 error: op={op_code} trans={trans_id} flag={int(flag)} code={code}"
                    )
                case _:
                    pass

            match flag:
                case AppV2Flag.PUSH_ACK:
                    if (
                        not sent_initial_pull
                        and pkt.appv2.start_idx_or_ack_size >= total
                    ):
                        logger.debug(
                            "AppV2 got PUSH_ACK; sending initial PULL (op=%s trans=%s)",
                            int(op_code),
                            int(trans_id),
                        )
                        self._stream.sendall(
                            self._codec.pack_appv2_pull(
                                op_code=op_code,
                                trans_id=trans_id,
                                payload=b"",
                                start_idx=0,
                            )
                        )
                        sent_initial_pull = True
                    continue
                case AppV2Flag.PULL_ACK | AppV2Flag.PUSH:
                    pass
                case _:
                    continue

            if expected_total is None:
                expected_total = pkt.appv2.total_payload_size
                expected_crc = pkt.appv2.all_payload_checksum
                logger.debug(
                    "AppV2 response expected (op=%s trans=%s total=%s crc=%#x)",
                    int(op_code),
                    int(trans_id),
                    int(expected_total),
                    0 if expected_crc is None else int(expected_crc),
                )

            start = pkt.appv2.start_idx_or_ack_size
            chunks[start] = pkt.chunk

            end = start + len(pkt.chunk)
            if end > last_seen_end:
                last_seen_end = end
                if flag == AppV2Flag.PUSH:
                    logger.debug(
                        "AppV2 sending PUSH_ACK (op=%s trans=%s ack_size=%s)",
                        int(op_code),
                        int(trans_id),
                        int(last_seen_end),
                    )
                    self._stream.sendall(
                        self._codec.pack_appv2_push_ack(
                            op_code=op_code,
                            trans_id=trans_id,
                            ack_size=last_seen_end,
                        )
                    )

                if expected_total is None or last_seen_end < expected_total:
                    if last_seen_end != last_pulled_from:
                        last_pulled_from = last_seen_end
                        logger.debug(
                            "AppV2 sending PULL (op=%s trans=%s start_idx=%s)",
                            int(op_code),
                            int(trans_id),
                            int(last_pulled_from),
                        )
                        self._stream.sendall(
                            self._codec.pack_appv2_pull(
                                op_code=op_code,
                                trans_id=trans_id,
                                payload=b"",
                                start_idx=last_pulled_from,
                            )
                        )

            if expected_total is not None:
                received = sum(len(c) for c in chunks.values())
                if received >= expected_total:
                    assembled = bytearray()
                    for idx in sorted(chunks.keys()):
                        assembled += chunks[idx]
                    data = bytes(assembled[:expected_total])
                    if expected_crc is not None and _crc32(data) != expected_crc:
                        logger.warning(
                            "AppV2 payload CRC mismatch (op=%s trans=%s expected=%#x)",
                            int(op_code),
                            int(trans_id),
                            int(expected_crc),
                        )
                        raise TmpProtocolError("AppV2 payload CRC mismatch")
                    if self._debug_raw:
                        self._debug_print(
                            f"== AppV2 op={int(op_code)} trans={int(trans_id)} response =="
                        )
                        self._debug_print(_pretty_debug_payload(data))

                    logger.debug(
                        "AppV2 request done (op=%s trans=%s bytes=%s elapsed_ms=%.1f)",
                        int(op_code),
                        int(trans_id),
                        len(data),
                        (time.time() - start_ts) * 1000.0,
                    )
                    return data

        logger.warning(
            "AppV2 response timeout (op=%s trans=%s elapsed_ms=%.1f)",
            int(op_code),
            int(trans_id),
            (time.time() - start_ts) * 1000.0,
        )
        raise TmpProtocolError("AppV2 response timeout")

    def request_json(
        self,
        *,
        op_code: int,
        params: Any | None = None,
        timeout_seconds: float = 8.0,
    ) -> dict[str, Any]:
        raw = self.request_appv2(
            op_code=op_code,
            payload=make_tmp_params_payload(params),
            timeout_seconds=timeout_seconds,
        )
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise TmpProtocolError("failed to parse JSON response") from e


def make_tmp_params_payload(params: Any | None) -> bytes:
    """Encode the request payload for TMP/AppV2.

    The Deco Android app wraps the params object inside a TMPParams envelope:
    - `configVersion`: currentTimeMillis
    - `params`: the params object (often null)
    """

    if isinstance(params, (bytes, bytearray)):
        return bytes(params)

    payload: dict[str, Any] = {
        "configVersion": int(time.time() * 1000),
        "params": params,
    }
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")
