from __future__ import annotations

import argparse
import json

from _common import add_auth_args, get_email, make_target, read_password
from tmpkit.deco.opcodes import DecoAppV2Opcode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Low-level TMP/AppV2 example: ASSOC + TOKEN_ALLOC + COMP_NEGOTIATE"
    )
    parser.add_argument("--host", default="192.168.0.29", help="Deco host/IP")
    add_auth_args(parser)
    pw = parser.add_mutually_exclusive_group(required=False)
    pw.add_argument("--ssh-pass", default=None, help="SSH password")
    parser.add_argument(
        "--timeout-seconds", type=float, default=20.0, help="Timeout in seconds"
    )
    parser.add_argument(
        "--debug-raw", action="store_true", help="Pretty-print raw AppV2 payloads"
    )
    parser.add_argument(
        "--assoc-only",
        action="store_true",
        help="Only perform TMP ASSOC handshake and exit",
    )
    args = parser.parse_args()

    target = make_target(
        host=str(args.host),
        email=get_email(args),
        ssh_password=read_password(args),
        timeout_seconds=float(args.timeout_seconds),
    )

    try:
        with target.connect_appv2(debug_raw=bool(args.debug_raw)) as session:
            session.assoc(
                timeout_seconds=float(args.timeout_seconds), send_client_hello=True
            )
            if args.assoc_only:
                print("ASSOC OK")
                return 0

            token_alloc_raw = session.request_appv2(
                op_code=DecoAppV2Opcode.TMP_APPV2_OP_TOKEN_ALLOC,
                payload=b"",
                timeout_seconds=float(args.timeout_seconds),
            )
            comp_negotiate_raw = session.request_appv2(
                op_code=DecoAppV2Opcode.TMP_APPV2_OP_COMP_NEGOTIATE,
                payload=b"",
                timeout_seconds=float(args.timeout_seconds),
            )

        def to_pretty(raw: bytes) -> str:
            try:
                return json.dumps(
                    json.loads(raw.decode("utf-8")),
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                )
            except Exception:
                return raw.hex()

        print("TOKEN_ALLOC response:")
        print(to_pretty(token_alloc_raw))
        print("COMP_NEGOTIATE response:")
        print(to_pretty(comp_negotiate_raw))
        return 0
    except (OSError, RuntimeError, ValueError) as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
