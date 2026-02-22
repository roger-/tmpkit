from __future__ import annotations

import unittest
from unittest import mock

from tmpkit.lib.constants import TmpCtrlCode
from tmpkit.lib.tmp import (
    TmpCodec,
    TmpFrame,
    TmpGphHeader,
    TmpProtocolError,
    TmpSession,
    TmpTphHeader,
)
from tmpkit.lib.ssh import SshTmpTarget, TmpSshTunnel, _prefer_kex


class _FakeStream:
    def __init__(self, incoming: bytes) -> None:
        self._incoming = bytearray(incoming)
        self.sent = bytearray()

    def recv(self, n: int) -> bytes:
        if not self._incoming:
            return b""
        out = self._incoming[:n]
        del self._incoming[:n]
        return bytes(out)

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def close(self) -> None:
        return


class TestFrames(unittest.TestCase):
    def test_data_frame_roundtrip_with_crc(self) -> None:
        payload = b"hello"
        frame = TmpFrame(
            gph=TmpGphHeader(1, 1, TmpCtrlCode.DATA_TRANSFER, 0),
            tph=TmpTphHeader(payload_length=len(payload), serial_no=123),
            payload=payload,
        )
        packed = frame.pack()
        parsed = TmpFrame.read_from(_FakeStream(packed))
        self.assertEqual(parsed.gph, frame.gph)
        self.assertIsNotNone(parsed.tph)
        self.assertEqual(parsed.payload, payload)

    def test_crc_mismatch_raises(self) -> None:
        payload = b"abc"
        frame = TmpFrame(
            gph=TmpGphHeader(1, 1, TmpCtrlCode.DATA_TRANSFER, 0),
            tph=TmpTphHeader(payload_length=len(payload), serial_no=1),
            payload=payload,
        )
        packed = bytearray(frame.pack())
        packed[-1] ^= 0xFF
        with self.assertRaises(TmpProtocolError):
            TmpFrame.read_from(_FakeStream(bytes(packed)))


class TestHeaderUnpackErrors(unittest.TestCase):
    def test_gph_unpack_wrong_size_raises_tmp_protocol_error(self) -> None:
        with self.assertRaises(TmpProtocolError):
            TmpGphHeader.unpack(b"\x00")

    def test_tph_unpack_wrong_size_raises_tmp_protocol_error(self) -> None:
        with self.assertRaises(TmpProtocolError):
            TmpTphHeader.unpack(b"\x00" * 11)


class TestAssoc(unittest.TestCase):
    def test_assoc_can_send_client_hello(self) -> None:
        incoming = bytes([1, 1, TmpCtrlCode.ASSOC_ACCEPT, 0])
        stream = _FakeStream(incoming)
        session = TmpSession(stream, codec=TmpCodec())

        session.assoc(timeout_seconds=0.1, send_client_hello=True)

        sent_stream = _FakeStream(bytes(stream.sent))
        f1 = TmpFrame.read_from(sent_stream)
        f2 = TmpFrame.read_from(sent_stream)
        f3 = TmpFrame.read_from(sent_stream)
        self.assertEqual(f1.gph.ctrl_code, TmpCtrlCode.ASSOC_REQ)
        self.assertEqual(f2.gph.ctrl_code, TmpCtrlCode.ASSOC_ACCEPT)
        self.assertEqual(f3.gph.ctrl_code, TmpCtrlCode.HELLO)


class TestSshHelper(unittest.TestCase):
    def test_prefer_kex_orders_items_first(self) -> None:
        existing = ["a", "b", "c", "d"]
        out = _prefer_kex(existing, ["c", "x"])
        self.assertEqual(out[0:2], ["c", "x"])
        self.assertIn("a", out)
        self.assertIn("b", out)
        self.assertIn("d", out)

    def test_target_connect_tmp_delegates(self) -> None:
        target = SshTmpTarget(host="h", port=22, username="u", password="p")

        sentinel_ctx = object()
        with mock.patch(
            "tmpkit.lib.ssh.connect_tmp_over_ssh", return_value=sentinel_ctx
        ) as m:
            got = target.connect_tmp(main_ver=9, second_ver=8)

        self.assertIs(got, sentinel_ctx)
        m.assert_called_once()


class TestConvenience(unittest.TestCase):
    def test_connect_tmp_builds_target(self) -> None:
        import tmpkit

        sentinel_ctx = object()
        with mock.patch.object(
            SshTmpTarget, "connect_tmp", return_value=sentinel_ctx
        ) as m:
            got = tmpkit.connect_tmp(host="h", port=22, username="u", password="p")

        self.assertIs(got, sentinel_ctx)
        m.assert_called_once()

    # Paramiko is a required dependency for tmpkit.


if __name__ == "__main__":
    unittest.main()
