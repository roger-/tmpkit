"""MAC address normalization helpers for Deco payload parsing."""

from __future__ import annotations

from macaddress import EUI48

_ZERO_MAC48 = "00:00:00:00:00:00"


def _eui48_to_str(eui: EUI48) -> str:
    return ":".join(f"{b:02x}" for b in bytes(eui))


def normalize_mac48_str(value: object) -> str:
    """Normalize a MAC-48 address into canonical lowercase colon form.

    Accepts formats supported by python-macaddress (EUI-48):
    - xx-xx-xx-xx-xx-xx
    - xx:xx:xx:xx:xx:xx
    - xxxx.xxxx.xxxx
    - xxxxxxxxxxxx

    Returns "00:00:00:00:00:00" if the input is missing/invalid.
    """

    match value:
        case str() as s if s.strip():
            try:
                return _eui48_to_str(EUI48(s.strip()))
            except ValueError:
                return _ZERO_MAC48
        case bytes() as b if len(b) == 6:
            # EUI48 accepts packed bytes.
            return _eui48_to_str(EUI48(b))
        case EUI48() as eui:
            return _eui48_to_str(eui)
        case _:
            return _ZERO_MAC48
