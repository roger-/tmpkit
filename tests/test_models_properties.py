from __future__ import annotations

import unittest

from ipaddress import IPv4Address
from macaddress import EUI48

from tmpkit.deco.models import IPv4Status, Status


class TestModelsProperties(unittest.TestCase):
    def test_status_string_views(self) -> None:
        st = Status()
        self.assertIsNone(st.wan_macaddr)

        st.wan_macaddr = EUI48("aa:bb:cc:dd:ee:ff")
        self.assertEqual(st.wan_macaddr, EUI48("aa:bb:cc:dd:ee:ff"))

        st.wan_ipv4_addr = IPv4Address("1.2.3.4")
        self.assertEqual(st.wan_ipv4_addr, IPv4Address("1.2.3.4"))

    def test_ipv4status_string_views(self) -> None:
        ip4 = IPv4Status()
        self.assertIsNone(ip4.wan_ipv4_gateway)

        ip4.wan_ipv4_gateway = IPv4Address("192.0.2.1")
        self.assertEqual(ip4.wan_ipv4_gateway, IPv4Address("192.0.2.1"))


if __name__ == "__main__":
    unittest.main()
