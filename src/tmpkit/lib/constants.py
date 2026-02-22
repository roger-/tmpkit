"""Shared wire-protocol constants for TMP and TMP/AppV2."""

from __future__ import annotations

from enum import IntEnum, IntFlag
from typing import Final

# Centralized protocol constants.
#
# Keep numeric wire-protocol values in one place so they cannot drift.


# ---- TMP (transport framing) ----

TMP_CRC32_PLACEHOLDER: Final[int] = 0x5A6B7C8D


class TmpCtrlCode(IntEnum):
    ASSOC_REQ = 1
    ASSOC_ACCEPT = 2
    ASSOC_REFUSE = 3
    HELLO = 4
    DATA_TRANSFER = 5
    BYE = 6


# ---- TMP/AppV2 ----


class AppV2Flag(IntFlag):
    ACK = 1
    PUSH = 2
    PULL = 4

    PUSH_ACK = ACK | PUSH
    PULL_ACK = ACK | PULL
