import unittest

from subnet_registry import (
    find_available_subnet,
    find_available_vlan,
    required_prefix,
    suggest_subnet,
    validate_registry_entry,
)


class SubnetRegistryTests(unittest.TestCase):
    def test_six_servers_need_a_28(self):
        self.assertEqual(required_prefix(6), 28)
        suggestion = suggest_subnet(6)
        self.assertEqual(suggestion.cidr, "192.168.0.0/28")
        self.assertEqual(suggestion.mask, "255.255.255.240")
        self.assertEqual(suggestion.gateway, "192.168.0.1")
        self.assertEqual(suggestion.server_ips[0], "192.168.0.2")
        self.assertEqual(suggestion.server_ips[-1], "192.168.0.7")
        self.assertEqual(suggestion.broadcast, "192.168.0.15")
        self.assertEqual(suggestion.spare_addresses, 7)
        self.assertEqual(suggestion.vlan, 1000)

    def test_used_subnet_and_vlan_are_skipped(self):
        suggestion = suggest_subnet(
            6,
            used_cidrs=["192.168.0.0/28"],
            used_vlans=[1000, 1001],
        )
        self.assertEqual(suggestion.cidr, "192.168.0.16/28")
        self.assertEqual(suggestion.vlan, 1002)

    def test_overlap_with_larger_used_network_is_skipped(self):
        network = find_available_subnet(6, ["192.168.0.0/24"])
        self.assertEqual(str(network), "192.168.1.0/28")

    def test_vlan_range_is_checked(self):
        self.assertEqual(find_available_vlan([4093], 4093, 4094), 4094)

    def test_invalid_server_count_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "mindst 1"):
            required_prefix(0)

    def test_manual_registry_entry_is_normalized(self):
        network = validate_registry_entry("192.168.70.7/24", "192.168.70.1", 1005)
        self.assertEqual(str(network), "192.168.70.0/24")

    def test_manual_entry_rejects_overlap(self):
        with self.assertRaisesRegex(ValueError, "overlapper"):
            validate_registry_entry(
                "192.168.70.128/25", "192.168.70.129", 1006,
                used_cidrs=["192.168.70.0/24"],
            )

    def test_manual_entry_rejects_used_vlan(self):
        with self.assertRaisesRegex(ValueError, "allerede i brug"):
            validate_registry_entry(
                "192.168.80.0/24", "192.168.80.1", 1005,
                used_vlans=[1005],
            )

    def test_gateway_must_be_a_usable_address(self):
        with self.assertRaisesRegex(ValueError, "broadcast"):
            validate_registry_entry("192.168.80.0/24", "192.168.80.255", 1007)


if __name__ == "__main__":
    unittest.main()
