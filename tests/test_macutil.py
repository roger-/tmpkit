from __future__ import annotations

import unittest

from tmpkit.deco.macutil import normalize_mac48_str


class TestMacUtil(unittest.TestCase):
    def test_normalize_mac48_str_accepts_common_formats(self) -> None:
        self.assertEqual(normalize_mac48_str("AA-BB-CC-DD-EE-FF"), "aa:bb:cc:dd:ee:ff")
        self.assertEqual(normalize_mac48_str("AA:BB:CC:DD:EE:FF"), "aa:bb:cc:dd:ee:ff")
        self.assertEqual(normalize_mac48_str("aabb.ccdd.eeff"), "aa:bb:cc:dd:ee:ff")
        self.assertEqual(normalize_mac48_str("AABBCCDDEEFF"), "aa:bb:cc:dd:ee:ff")

    def test_normalize_mac48_str_invalid_returns_zero(self) -> None:
        self.assertEqual(normalize_mac48_str(None), "00:00:00:00:00:00")
        self.assertEqual(normalize_mac48_str(""), "00:00:00:00:00:00")
        self.assertEqual(normalize_mac48_str("not a mac"), "00:00:00:00:00:00")


if __name__ == "__main__":
    unittest.main()
