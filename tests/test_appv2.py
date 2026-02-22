from __future__ import annotations

import json
import time
import unittest
from unittest import mock

from tmpkit.lib.appv2 import (
    TmpAppV2Codec,
    TmpAppV2Header,
    TmpBusinessHeader,
    make_tmp_params_payload,
)
from tmpkit.lib.constants import AppV2Flag, TmpCtrlCode
from tmpkit.deco.opcodes import DecoAppV2Opcode
from tmpkit.lib.tmp import TmpFrame, TmpProtocolError
from tmpkit.lib.ssh import SshTmpTarget


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


class TestAppV2Headers(unittest.TestCase):
    def test_business_header_roundtrip(self) -> None:
        b = TmpBusinessHeader(1, 2)
        self.assertEqual(TmpBusinessHeader.unpack(b.pack()), b)

    def test_appv2_header_roundtrip(self) -> None:
        h = TmpAppV2Header(
            op_code=DecoAppV2Opcode.TMP_APPV2_OP_CLIENT_LIST_GET,
            appv2_flag=AppV2Flag.PUSH,
            appv2_error_code=0,
            trans_id=0x1234,
            all_payload_checksum=0x01020304,
            total_payload_size=0x11223344,
            start_idx_or_ack_size=0x55667788,
        )
        packed = h.pack()
        self.assertEqual(
            packed[0:2],
            int(DecoAppV2Opcode.TMP_APPV2_OP_CLIENT_LIST_GET).to_bytes(2, "big"),
        )
        self.assertEqual(TmpAppV2Header.unpack(packed), h)


class TestTmpParamsPayload(unittest.TestCase):
    def test_make_tmp_params_payload_wraps_params_and_config_version(self) -> None:
        before = int(time.time() * 1000)
        payload = make_tmp_params_payload({"x": 1})
        after = int(time.time() * 1000)

        parsed = json.loads(payload.decode("utf-8"))
        self.assertEqual(parsed["params"], {"x": 1})
        self.assertIsInstance(parsed["configVersion"], int)
        self.assertGreaterEqual(parsed["configVersion"], before)
        self.assertLessEqual(parsed["configVersion"], after)

    def test_make_tmp_params_payload_passes_through_bytes(self) -> None:
        self.assertEqual(make_tmp_params_payload(b"abc"), b"abc")


class TestAppV2Codec(unittest.TestCase):
    def test_push_chunk_is_valid_tmp_frame(self) -> None:
        codec = TmpAppV2Codec()
        raw = codec.pack_appv2_push_chunk(
            op_code=DecoAppV2Opcode.TMP_APPV2_OP_CLIENT_LIST_GET,
            trans_id=1,
            all_payload_checksum=0xAABBCCDD,
            total_payload_size=3,
            start_idx=0,
            chunk=b"xyz",
        )
        frame = TmpFrame.read_from(_FakeStream(raw))
        self.assertEqual(frame.gph.ctrl_code, TmpCtrlCode.DATA_TRANSFER)
        self.assertIsNotNone(frame.tph)
        self.assertGreaterEqual(len(frame.payload), 2 + 18)


class TestConvenience(unittest.TestCase):
    def test_target_connect_appv2_delegates(self) -> None:
        target = SshTmpTarget(host="h", port=22, username="u", password="p")

        sentinel_ctx = object()
        with mock.patch(
            "tmpkit.lib.ssh.connect_appv2_over_ssh", return_value=sentinel_ctx
        ) as m:
            got = target.connect_appv2(
                main_ver=9, second_ver=8, business_type=7, business_ver=6
            )

        self.assertIs(got, sentinel_ctx)
        m.assert_called_once()

    def test_connect_appv2_builds_target(self) -> None:
        import tmpkit

        sentinel_ctx = object()
        with mock.patch.object(
            SshTmpTarget, "connect_appv2", return_value=sentinel_ctx
        ) as m:
            got = tmpkit.connect_appv2(host="h", port=22, username="u", password="p")

        self.assertIs(got, sentinel_ctx)
        m.assert_called_once()


class TestHeaderUnpackErrors(unittest.TestCase):
    def test_business_unpack_wrong_size_raises_tmp_protocol_error(self) -> None:
        with self.assertRaises(TmpProtocolError):
            TmpBusinessHeader.unpack(b"\x00" * 5)

    def test_appv2_unpack_wrong_size_raises_tmp_protocol_error(self) -> None:
        with self.assertRaises(TmpProtocolError):
            TmpAppV2Header.unpack(b"\x00")


if __name__ == "__main__":
    unittest.main()
