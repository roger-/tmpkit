from __future__ import annotations

import argparse

from _common import add_auth_args, get_email, make_target, read_password
from tmpkit.lib.tmp import TmpProtocolError

DECO_HOST = "192.168.0.29"
DECO_SSH_PORT = 20001
TMP_DEST_HOST = "127.0.0.1"
TMP_DEST_PORT = 20002


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Minimal verifier for your Deco: SSH to 192.168.0.29:20001, tunnel to 127.0.0.1:20002, run TMP ASSOC."
        )
    )
    add_auth_args(parser)
    pw = parser.add_mutually_exclusive_group(required=False)
    pw.add_argument("--ssh-pass", default=None, help="SSH password")
    parser.add_argument(
        "--timeout-seconds", type=float, default=8.0, help="Timeout in seconds"
    )
    args = parser.parse_args()

    target = make_target(
        host=DECO_HOST,
        ssh_port=DECO_SSH_PORT,
        email=get_email(args),
        ssh_password=read_password(args),
        timeout_seconds=float(args.timeout_seconds),
        dest_host=TMP_DEST_HOST,
        dest_port=TMP_DEST_PORT,
    )

    try:
        with target.connect_tmp() as session:
            session.assoc(
                timeout_seconds=float(args.timeout_seconds), send_client_hello=True
            )

        print("ASSOC OK")
        return 0
    except (TmpProtocolError, OSError, RuntimeError) as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
