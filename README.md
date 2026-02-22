# tmpkit

Minimal Python wrapper for the TP-Link Tether Management Protocol (TMP). This can be a richer alternative to accessing TP-Link routers than the regular HTTP interface, where some functionality may not be exposed.

This is based on the [tmpcli](https://github.com/ropbear/tmpcli) project and reverse engineering the Deco Android app.

Testing only with the TP-Link Deco AX5000, and may not work with other devices.

# Usage

See examples folder for examples of the low-level and high-level interfaces. The high-level interface is meant to minimic [tplinkrouterc6u](https://github.com/AlexandrErohin/TP-Link-Archer-C6U).

# Example

```bash
# uv run python examples/deco_x5000_overview.py --host 10.0.0.25
Firmware(hardware_version='1.0', model='X5000', firmware_version='1.4.0 Build 20241212 Rel. 48194')
Status(
    wan_macaddr=EUI48('AA-BB-CC-00-00-01'),
    lan_macaddr=EUI48('AA-BB-CC-00-00-02'),
    wan_ipv4_addr=None,
    lan_ipv4_addr=IPv4Address('10.0.1.1'),
    wan_ipv4_gateway=None,
    wired_total=0,
    wifi_clients_total=7,
    guest_clients_total=0,
    iot_clients_total=None,
    clients_total=7,
    guest_2g_enable=False,
    guest_5g_enable=False,
    guest_6g_enable=None,
    iot_2g_enable=None,
    iot_5g_enable=None,
    iot_6g_enable=None,
    wifi_2g_enable=True,
    wifi_5g_enable=True,
    wifi_6g_enable=None,
    wan_ipv4_uptime=None,
    mem_usage=None,
    cpu_usage=None,
    conn_type='dynamic_ip',
    devices=[
        Device(type=<Connection.HOST_2G: 'host_2g'>,
               macaddr=EUI48('AA-BB-CC-00-10-01'),
               ipaddr=IPv4Address('10.0.0.101'),
               hostname='camera-livingroom-01',
               packets_sent=None,
               packets_received=None,
               down_speed=0,
               up_speed=0,
               tx_rate=None,
               rx_rate=None,
               online_time=None,
               traffic_usage=None,
               signal=2,
               active=True),

        Device(type=<Connection.HOST_2G: 'host_2g'>,
               macaddr=EUI48('AA-BB-CC-00-10-02'),
               ipaddr=IPv4Address('0.0.0.0'),
               hostname='camera-patio-01',
               packets_sent=None,
               packets_received=None,
               down_speed=2,
               up_speed=7,
               tx_rate=None,
               rx_rate=None,
               online_time=None,
               traffic_usage=None,
               signal=3,
               active=True),

        Device(type=<Connection.HOST_2G: 'host_2g'>,
               macaddr=EUI48('AA-BB-CC-00-10-03'),
               ipaddr=IPv4Address('0.0.0.0'),
               hostname='camera-garage-01',
               packets_sent=None,
               packets_received=None,
               down_speed=14,
               up_speed=440,
               tx_rate=None,
               rx_rate=None,
               online_time=None,
               traffic_usage=None,
               signal=3,
               active=True),

        Device(type=<Connection.HOST_2G: 'host_2g'>,
               macaddr=EUI48('AA-BB-CC-00-10-04'),
               ipaddr=IPv4Address('10.0.0.102'),
               hostname='camera-familyroom-01',
               packets_sent=None,
               packets_received=None,
               down_speed=29,
               up_speed=713,
               tx_rate=None,
               rx_rate=None,
               online_time=None,
               traffic_usage=None,
               signal=3,
               active=True),

        Device(type=<Connection.HOST_2G: 'host_2g'>,
               macaddr=EUI48('AA-BB-CC-00-10-05'),
               ipaddr=IPv4Address('10.0.0.103'),
               hostname='camera-entryway-01',
               packets_sent=None,
               packets_received=None,
               down_speed=0,
               up_speed=0,
               tx_rate=None,
               rx_rate=None,
               online_time=None,
               traffic_usage=None,
               signal=2,
               active=True),

        Device(type=<Connection.HOST_2G: 'host_2g'>,
               macaddr=EUI48('AA-BB-CC-00-10-06'),
               ipaddr=IPv4Address('10.0.0.104'),
               hostname='sensor-bedroom-01',
               packets_sent=None,
               packets_received=None,
               down_speed=9,
               up_speed=186,
               tx_rate=None,
               rx_rate=None,
               online_time=None,
               traffic_usage=None,
               signal=3,
               active=True),

        Device(type=<Connection.HOST_2G: 'host_2g'>,
               macaddr=EUI48('AA-BB-CC-00-10-07'),
               ipaddr=IPv4Address('10.0.0.105'),
               hostname='camera-office-01',
               packets_sent=None,
               packets_received=None,
               down_speed=0,
               up_speed=0,
               tx_rate=None,
               rx_rate=None,
               online_time=None,
               traffic_usage=None,
               signal=3,
               active=True)
    ]
)
```

# Credit

Credit to [tmpcli](https://github.com/ropbear/tmpcli). 

Note that a significant port of the this was developed with AI (GPT 5.2).
