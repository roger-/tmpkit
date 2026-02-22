from __future__ import annotations

import argparse
import json

from _common import add_auth_args, get_email, make_target, read_password
from tmpkit.deco.opcodes import DecoAppV2Opcode


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Low-level TMP/AppV2 example: fetch raw IPV4_GET JSON"
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
            _ = session.request_appv2(
                op_code=DecoAppV2Opcode.TMP_APPV2_OP_TOKEN_ALLOC,
                payload=b"",
                timeout_seconds=float(args.timeout_seconds),
            )
            _ = session.request_appv2(
                op_code=DecoAppV2Opcode.TMP_APPV2_OP_COMP_NEGOTIATE,
                payload=b"",
                timeout_seconds=float(args.timeout_seconds),
            )
            payload = session.request_json(
                op_code=DecoAppV2Opcode.TMP_APPV2_OP_IPV4_GET,
                params=None,
                timeout_seconds=float(args.timeout_seconds),
            )

        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    except (OSError, RuntimeError, ValueError) as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
