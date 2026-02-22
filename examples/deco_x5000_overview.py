from __future__ import annotations

import argparse

from _common import add_auth_args, get_email, make_client, read_password


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Deco data via high-level client"
    )
    parser.add_argument("--host", default="192.168.0.29", help="Deco host/IP")
    add_auth_args(parser)
    parser.add_argument(
        "--view",
        choices=["status", "clients", "devices", "signals"],
        default="status",
        help="What to print",
    )
    pw = parser.add_mutually_exclusive_group(required=False)
    pw.add_argument("--ssh-pass", default=None, help="SSH password")
    parser.add_argument(
        "--timeout-seconds", type=float, default=60.0, help="Timeout in seconds"
    )
    parser.add_argument("--all-nodes", action="store_true", help="Include mesh nodes")
    parser.add_argument(
        "--debug-raw", action="store_true", help="Pretty-print raw AppV2 payloads"
    )
    args = parser.parse_args()

    client = make_client(
        host=str(args.host),
        email=get_email(args),
        ssh_password=read_password(args),
        timeout_seconds=float(args.timeout_seconds),
        debug_raw=bool(args.debug_raw),
        all_nodes=bool(args.all_nodes),
    )

    try:
        with client:
            match args.view:
                case "status":
                    firmware = client.get_firmware()
                    status = client.get_status()
                    print(
                        "Firmware: "
                        f"hardware_version={firmware.hardware_version!r} "
                        f"model={firmware.model!r} "
                        f"firmware_version={firmware.firmware_version!r}"
                    )
                    print(
                        "Status: "
                        f"clients_total={status.clients_total} "
                        f"wired_total={status.wired_total} "
                        f"wifi_clients_total={status.wifi_clients_total} "
                        f"guest_clients_total={status.guest_clients_total} "
                        f"iot_clients_total={status.iot_clients_total}"
                    )
                    print(f"devices={len(status.devices)}")
                case "clients" | "devices":
                    devices = client.get_devices()
                    for d in devices:
                        print(
                            f"{d.hostname}|{d.ipaddr}|{d.macaddr}|type={d.type.value}|signal={d.signal}|active={d.active}|up={d.up_speed}|down={d.down_speed}"
                        )
                    print(f"devices={len(devices)}")
                case "signals":
                    devices = client.get_devices()
                    online_count = 0
                    for d in devices:
                        if d.active:
                            online_count += 1
                        print(
                            f"{d.hostname} | {d.ipaddr} | {d.macaddr} | online={d.active} | signal={d.signal}"
                        )
                    print(f"online_clients={online_count} total_clients={len(devices)}")

        return 0
    except (OSError, RuntimeError, ValueError) as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
