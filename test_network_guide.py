import tempfile
import unittest
from pathlib import Path

from network_guide import build_network_plan, export_network_pdf


class NetworkGuideTests(unittest.TestCase):
    def test_subnet_router_firewall_plan(self):
        plan = build_network_plan(
            "FakeNews Daily",
            {"System X": 8},
            {"System X": {"cidr": "59.107.13.0/27", "vlan": 939}},
            firewall=True,
            internet=True,
        )
        segment = plan.segments[0]
        self.assertEqual(segment.app, 0)
        self.assertEqual(segment.custom_vlan, 1939)
        self.assertEqual(segment.gateway, "192.168.0.1")
        self.assertEqual(segment.server_ips[0], "192.168.0.2")
        self.assertEqual(len(segment.server_ips), 8)
        self.assertEqual(plan.firewall_rules[0].port, "443")
        self.assertEqual(plan.firewall_rules[-1].action, "DENY")

    def test_app_mapping(self):
        plan = build_network_plan(
            "Test",
            {"Mainframe": 2},
            {"Mainframe": {"cidr": "10.2.3.0/28", "vlan": 300}},
            firewall=False,
            internet=False,
        )
        self.assertEqual(plan.segments[0].app, 2)

    def test_firewall_can_target_one_app(self):
        plan = build_network_plan(
            "Test", {"System X": 1, "RISC": 1},
            {"System X": {"cidr": "10.0.0.0/28", "vlan": 10},
             "RISC": {"cidr": "10.0.1.0/28", "vlan": 11}},
            True, True, firewall_app=1,
        )
        self.assertEqual(plan.firewall_apps, [1])
        self.assertEqual(plan.firewall_rules[0].source, plan.segments[1].custom_cidr)

    def test_missing_vlan_rejected(self):
        with self.assertRaisesRegex(ValueError, "VLAN"):
            build_network_plan("Test", {"GPU": 1}, {"GPU": {"cidr": "10.0.0.0/28", "vlan": 0}}, False, False)


if __name__ == "__main__":
    unittest.main()
