from __future__ import annotations

import unittest

from tmpkit.lib.appv2 import _pretty_debug_payload


class TestAppV2DebugPretty(unittest.TestCase):
    def test_pretty_json(self) -> None:
        raw = b'{"b":2,"a":1}'
        s = _pretty_debug_payload(raw)
        # Should be pretty printed and key-sorted.
        self.assertIn("\n", s)
        self.assertIn('"a": 1', s)
        self.assertIn('"b": 2', s)

    def test_non_json_text(self) -> None:
        raw = b"not json"
        s = _pretty_debug_payload(raw)
        self.assertTrue(s.startswith("<text"))

    def test_non_utf8_bytes(self) -> None:
        raw = bytes([0xFF, 0x00, 0x01, 0x02])
        s = _pretty_debug_payload(raw)
        self.assertTrue(s.startswith("<bytes"))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
