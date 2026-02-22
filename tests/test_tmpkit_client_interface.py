from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tmpkit.deco.client import DecoSshClient, DecoSshConfig
from tmpkit.deco.models import Firmware, IPv4Status, Status


class TestDecoSshClient(unittest.TestCase):
    def test_authorize_persists_session_and_getters_reuse_it(self) -> None:
        cfg = DecoSshConfig(host="deco", email="user@example.com", ssh_password="pw")
        client = DecoSshClient(cfg)

        fake_tunnel = MagicMock()
        fake_tunnel.channel = object()
        session = MagicMock()

        with (
            patch("tmpkit.deco.client.TmpSshTunnel", return_value=fake_tunnel),
            patch("tmpkit.deco.client.TmpAppV2Session", return_value=session),
            patch(
                "tmpkit.deco.client.deco_get_firmware",
                return_value=Firmware("h", "m", "f"),
            ) as gf,
            patch("tmpkit.deco.client.deco_get_status", return_value=Status()) as gs,
            patch(
                "tmpkit.deco.client.deco_get_ipv4_status", return_value=IPv4Status()
            ) as g4,
        ):
            client.authorize()
            fw = client.get_firmware()
            st = client.get_status()
            ip4 = client.get_ipv4_status()
            client.logout()

        self.assertIsInstance(fw, Firmware)
        self.assertIsInstance(st, Status)
        self.assertIsInstance(ip4, IPv4Status)

        # Bootstrapping occurs once per authorize() lifecycle.
        self.assertEqual(session.assoc.call_count, 1)
        self.assertEqual(session.request_appv2.call_count, 2)
        self.assertEqual(fake_tunnel.open.call_count, 1)
        self.assertEqual(fake_tunnel.close.call_count, 1)
        self.assertEqual(session.close.call_count, 1)

        # Adapter functions called.
        self.assertEqual(gf.call_count, 1)
        self.assertEqual(gs.call_count, 1)
        self.assertEqual(g4.call_count, 1)

    def test_get_devices_delegates_to_status(self) -> None:
        cfg = DecoSshConfig(host="deco", email="user@example.com", ssh_password="pw")
        client = DecoSshClient(cfg)

        st = Status()
        st.devices = []

        with patch.object(DecoSshClient, "get_status", return_value=st):
            devs = client.get_devices()

        self.assertEqual(devs, [])

    def test_getter_without_authorize_raises(self) -> None:
        cfg = DecoSshConfig(host="deco", email="user@example.com", ssh_password="pw")
        client = DecoSshClient(cfg)

        with self.assertRaises(RuntimeError):
            _ = client.get_status()
