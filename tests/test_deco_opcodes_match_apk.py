from __future__ import annotations

import re
import unittest
from pathlib import Path

from tmpkit.deco.opcodes import DecoAppV2Opcode


class TestDecoOpcodesMatchApk(unittest.TestCase):
    def test_deco_appv2_opcodes_match_decompiled_apk(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        java_path = (
            repo_root
            / "apk_out"
            / "deco_1.10.5_jadx"
            / "sources"
            / "com"
            / "tplink"
            / "libtpnetwork"
            / "TMPNetwork"
            / "e.java"
        )
        if not java_path.exists():
            self.skipTest(f"Decompiled APK source not found at {java_path}")

        src = java_path.read_text(encoding="utf-8", errors="replace")

        const_re = re.compile(r"public\s+static\s+final\s+short\s+(\w+)\s*=\s*(\d+);")
        put_re = re.compile(
            r"cK\.put\(\s*(?:\(short\)\s*(\d+)|Short\.valueOf\((\w+)\))\s*,\s*\"([^\"]+)\"\s*\);"
        )

        consts: dict[str, int] = {
            name: int(value) for name, value in const_re.findall(src)
        }
        extracted: dict[int, str] = {}

        for literal_value, symbol_name, op_name in put_re.findall(src):
            if literal_value:
                code = int(literal_value)
            else:
                if symbol_name not in consts:
                    self.fail(
                        f"Unknown short constant referenced in cK.put: {symbol_name}"
                    )
                code = consts[symbol_name]
            extracted[code] = op_name

        self.assertGreater(
            len(extracted), 0, "Failed to extract any opcode mappings from APK"
        )

        ours: dict[int, str] = {int(op.value): str(op.name) for op in DecoAppV2Opcode}
        self.assertEqual(set(ours.keys()), set(extracted.keys()))
        for code, name in ours.items():
            self.assertEqual(
                extracted[code],
                name,
                f"Opcode name mismatch for 0x{code:04X}: apk={extracted[code]} ours={name}",
            )


if __name__ == "__main__":
    unittest.main()
