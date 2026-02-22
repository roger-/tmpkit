# tmpkit

Minimal Python wrapper for the TP-Link Tether Management Protocol (TMP). This can be a richer alternative to accessing TP-Link routers than the regular HTTP interface, where some functionality may not be exposed.

This is based on the [tmpcli](https://github.com/ropbear/tmpcli) project and reverse engineering the Deco Android app.

Testing only with the TP-Link Deco AX5000, and may not work with other devices.

# Usage

See examples folder for examples of the low-level and high-level interfaces. The high-level interface is meant to minimic [tplinkrouterc6u](https://github.com/AlexandrErohin/TP-Link-Archer-C6U).

# Example

```bash
# uv run python examples/deco_x5000_status_firmware.py --host 192.168.0.29
Firmware: hardware_version='1.0' model='X5000' firmware_version='1.4.0 Build 20241212 Rel. 48194'
Status: clients_total=7 wired_total=0 wifi_clients_total=7 guest_clients_total=0 iot_clients_total=None
devices=7
```

# Credit

Credit to [tmpcli](https://github.com/ropbear/tmpcli). 

Note that a significant port of the this was developed with AI (GPT 5.2).
