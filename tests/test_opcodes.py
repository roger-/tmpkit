from __future__ import annotations

import unittest

from tmpkit.deco.opcodes import DECO_APPV2_OPCODES, DecoAppV2Opcode, opcode_names


class TestOpcodeTables(unittest.TestCase):
    def test_deco_table_contains_known_appv2_ops(self) -> None:
        self.assertIn(
            int(DecoAppV2Opcode.TMP_APPV2_OP_CLIENT_LIST_GET), DECO_APPV2_OPCODES
        )
        self.assertIn(
            "TMP_APPV2_OP_CLIENT_LIST_GET",
            opcode_names(
                DECO_APPV2_OPCODES, int(DecoAppV2Opcode.TMP_APPV2_OP_CLIENT_LIST_GET)
            ),
        )


if __name__ == "__main__":
    unittest.main()
