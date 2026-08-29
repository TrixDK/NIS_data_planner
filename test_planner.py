import unittest
from pathlib import Path

from planner_core import DEFAULT_CATALOG, FAMILIES, build_plan, load_catalog, suggest_mix


class PlannerTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {key: dict(value) for key, value in DEFAULT_CATALOG.items()}

    def test_new_game_uses_only_5000_iops_servers(self):
        result = build_plan("Kunde", {"System X": 40000}, "Økonomisk", True, False, False, self.catalog, current_xp=0)
        self.assertEqual(result.delivered_iops, 40000)
        self.assertEqual(sum(x.large for x in result.families), 0)
        self.assertEqual(sum(x.small for x in result.families), 8)
        self.assertEqual(result.total_cost, 5450)

    def test_exact_120k_with_all_store_items(self):
        result = build_plan("Kunde", {"System X": 120000}, "Økonomisk", True, False, False, self.catalog, current_xp=10000)
        self.assertEqual(result.delivered_iops, 120000)
        self.assertEqual(sum(x.large for x in result.families), 10)
        self.assertGreaterEqual(sum(x.free_units for x in result.racks), 0)

    def test_redundant_has_two_links_per_server(self):
        result = build_plan("Kunde", {"GPU": 50000}, "Redundant", True, False, True, self.catalog, current_xp=10000)
        self.assertEqual(result.server_cables, result.server_count * 2)
        self.assertTrue(all(x.switches == 2 for x in result.racks if x.large + x.small > 0))

    def test_router_and_firewall_use_rack_space(self):
        base = build_plan("Kunde", {"RISC": 5000}, "Økonomisk", False, False, False, self.catalog, current_xp=1000)
        infra = build_plan("Kunde", {"RISC": 5000}, "Økonomisk", False, True, True, self.catalog, current_xp=1000)
        self.assertEqual(sum(x.used_units for x in infra.racks), sum(x.used_units for x in base.racks) + 2)

    def test_locked_family_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "RISC-servere er låst"):
            build_plan("Kunde", {"RISC": 5000}, "Økonomisk", True, False, False, self.catalog, current_xp=0)

    def test_router_is_rejected_below_700_xp(self):
        with self.assertRaisesRegex(ValueError, "Router låses"):
            build_plan("Kunde", {"System X": 5000}, "Økonomisk", True, True, False, self.catalog, current_xp=699)

    def test_catalog_created(self):
        path = Path(__file__).with_name("catalog_test_output.json")
        try:
            catalog = load_catalog(path)
            self.assertEqual(catalog["system_x_large"]["iops"], 12000)
            self.assertEqual(catalog["router"]["unlock_xp"], 700)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
