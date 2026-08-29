from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Tuple

FAMILIES = ("System X", "RISC", "Mainframe", "GPU")
RACK_U = 47

DEFAULT_CATALOG = {
    # Servere
    "system_x_small": {"category": "System X", "name": "System X 3U 5000 IOPS", "iops": 5000, "units": 3, "ports": 2, "unlock_xp": 0, "price": 400, "eol_hours": 4},
    "system_x_large": {"category": "System X", "name": "System X 7U 12000 IOPS", "iops": 12000, "units": 7, "ports": 2, "unlock_xp": 2200, "price": 1600, "eol_hours": 4},
    "risc_small": {"category": "RISC", "name": "RISC 3U 5000 IOPS", "iops": 5000, "units": 3, "ports": 2, "unlock_xp": 100, "price": 450, "eol_hours": 5},
    "risc_large": {"category": "RISC", "name": "RISC 7U 12000 IOPS", "iops": 12000, "units": 7, "ports": 2, "unlock_xp": 3000, "price": 1750, "eol_hours": 5},
    "mainframe_small": {"category": "Mainframe", "name": "Mainframe 3U 5000 IOPS", "iops": 5000, "units": 3, "ports": 2, "unlock_xp": 480, "price": 850, "eol_hours": 7},
    "mainframe_large": {"category": "Mainframe", "name": "Mainframe 7U 12000 IOPS", "iops": 12000, "units": 7, "ports": 2, "unlock_xp": 6500, "price": 2000, "eol_hours": 7},
    "gpu_small": {"category": "GPU", "name": "GPU 3U 5000 IOPS", "iops": 5000, "units": 3, "ports": 2, "unlock_xp": 350, "price": 550, "eol_hours": 3},
    "gpu_large": {"category": "GPU", "name": "GPU 7U 12000 IOPS", "iops": 12000, "units": 7, "ports": 2, "unlock_xp": 5500, "price": 2200, "eol_hours": 3},
    # Aktivt netværksudstyr
    "switch_rj45": {"category": "Switch", "name": "16 × 10Gbps RJ45", "units": 1, "downlink_ports": 16, "uplink_gbps": 10, "unlock_xp": 0, "price": 250, "eol_hours": 4},
    "switch_sfp4": {"category": "Switch", "name": "4 × SFP+/SFP28", "units": 1, "downlink_ports": 4, "uplink_gbps": 25, "unlock_xp": 400, "price": 400, "eol_hours": 4},
    "switch_qsfp32": {"category": "Switch", "name": "32 × QSFP+", "units": 1, "downlink_ports": 32, "uplink_gbps": 40, "unlock_xp": 2500, "price": 3800, "eol_hours": 4},
    "switch_combo": {"category": "Switch", "name": "4 × QSFP+ + 16 × SFP+/SFP28", "units": 1, "downlink_ports": 16, "uplink_gbps": 40, "unlock_xp": 2100, "price": 3500, "eol_hours": 4},
    "router": {"category": "Router", "name": "Router", "units": 1, "unlock_xp": 700, "price": 12000, "eol_hours": 6},
    "firewall": {"category": "Firewall", "name": "Firewall", "units": 1, "unlock_xp": 700, "price": 12000, "eol_hours": 6},
    # Passive komponenter
    "rack": {"category": "Passiv", "name": "Lanberg Rack Cabinet 19\" 47U/800×800", "units": 47, "unlock_xp": 0, "price": 1250},
    "rack_custom": {"category": "Passiv", "name": "Lanberg Rack Cabinet 19\" Custom color", "units": 47, "unlock_xp": 800, "price": 1250},
    "patch_rj45": {"category": "Patchpanel", "name": "Patch panel RJ45", "units": 1, "ports": 16, "unlock_xp": 0, "price": 250},
    "patch_combo": {"category": "Patchpanel", "name": "Patch panel Combo", "units": 1, "ports": 16, "unlock_xp": 500, "price": 450},
    "patch_fiber": {"category": "Patchpanel", "name": "Patch panel Fiber", "units": 1, "ports": 16, "unlock_xp": 500, "price": 450},
    # Kabler (prisen er pr. rulle i butikken; antal ruller kan ikke udledes af skærmbillederne)
    "cable_cat6_blue": {"category": "Kabel", "name": "Cable copper CAT6E blue", "unlock_xp": 0, "price": 500},
    "cable_cat6_black": {"category": "Kabel", "name": "Cable copper CAT6E black", "unlock_xp": 200, "price": 500},
    "cable_cat6_gray": {"category": "Kabel", "name": "Cable copper CAT6E gray", "unlock_xp": 200, "price": 500},
    "cable_cat6_custom": {"category": "Kabel", "name": "Cable copper CAT6E custom color", "unlock_xp": 800, "price": 500},
    "cable_fiber_green": {"category": "Kabel", "name": "Cable fiber 1 lane green", "unlock_xp": 500, "price": 1000},
    "cable_fiber_custom": {"category": "Kabel", "name": "Cable fiber 1 lane Custom Color", "unlock_xp": 800, "price": 1000},
    "cable_qsfp_yellow": {"category": "Kabel", "name": "Cable fiber 4 lanes (QSFP) yellow", "unlock_xp": 1500, "price": 3000},
    "cable_qsfp_custom": {"category": "Kabel", "name": "Cable fiber 4 lanes (QSFP) Custom Color", "unlock_xp": 2000, "price": 3000},
    # SFP-pakker á 5 stk.
    "module_sfp_rj45": {"category": "SFP", "name": "5× SFP+ Module RJ45 10Gbps", "unlock_xp": 500, "price": 250, "speed_gbps": 10},
    "module_sfp_fiber": {"category": "SFP", "name": "5× SFP+ Module Fiber 10Gbps", "unlock_xp": 700, "price": 350, "speed_gbps": 10},
    "module_sfp28": {"category": "SFP", "name": "5× SFP28 Module Fiber 25Gbps", "unlock_xp": 1200, "price": 900, "speed_gbps": 25},
    "module_qsfp": {"category": "SFP", "name": "5× QSFP+ Module Fiber 40Gbps", "unlock_xp": 2400, "price": 1500, "speed_gbps": 40},
}

FAMILY_KEYS = {
    "System X": ("system_x_large", "system_x_small"),
    "RISC": ("risc_large", "risc_small"),
    "Mainframe": ("mainframe_large", "mainframe_small"),
    "GPU": ("gpu_large", "gpu_small"),
}

PROFILES = {
    "Økonomisk": {"server_links": 1, "switches_per_rack": 1, "uplinks_per_switch": 1, "reserve_pct": 0},
    "Balanceret": {"server_links": 1, "switches_per_rack": 1, "uplinks_per_switch": 2, "reserve_pct": 10},
    "Redundant": {"server_links": 2, "switches_per_rack": 2, "uplinks_per_switch": 2, "reserve_pct": 15},
}


def load_catalog(path: Path) -> dict:
    if not path.exists():
        save_catalog(path, DEFAULT_CATALOG)
        return json.loads(json.dumps(DEFAULT_CATALOG))
    data = json.loads(path.read_text(encoding="utf-8"))
    merged = json.loads(json.dumps(DEFAULT_CATALOG))
    for key, values in data.items():
        if key in merged and isinstance(values, dict):
            merged[key].update(values)
    return merged


def save_catalog(path: Path, catalog: dict) -> None:
    path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass
class FamilyPlan:
    family: str
    required_iops: int
    large: int
    small: int
    delivered_iops: int
    units: int
    server_count: int


@dataclass
class RackPlan:
    rack_no: int
    family: str
    large: int
    small: int
    switches: int
    patch_panels: int
    infrastructure_units: int
    used_units: int
    free_units: int
    delivered_iops: int


@dataclass
class BomLine:
    category: str
    item: str
    quantity: int
    note: str = ""
    unit_price: int = 0
    total_price: int = 0
    unlock_xp: int = 0


@dataclass
class PlanResult:
    customer: str
    profile: str
    families: List[FamilyPlan]
    racks: List[RackPlan]
    bom: List[BomLine]
    required_iops: int
    delivered_iops: int
    server_count: int
    rack_count: int
    switch_count: int
    patch_panel_count: int
    server_cables: int
    patch_cables: int
    uplink_cables: int
    required_bandwidth_gbps: float
    available_uplink_gbps: float
    current_xp: int
    total_cost: int
    warnings: List[str]

    def to_dict(self) -> dict:
        return asdict(self)


def suggest_mix(required: int, large_iops: int, large_u: int, small_iops: int, small_u: int,
                allow_large: bool = True, allow_small: bool = True) -> Tuple[int, int]:
    if required <= 0:
        return 0, 0
    if not allow_large and not allow_small:
        raise ValueError("Ingen servermodel er oplåst for denne serverfamilie.")
    best = None
    max_large = math.ceil(required / large_iops) + 2 if allow_large else 0
    max_small = math.ceil(required / small_iops) + 3 if allow_small else 0
    for large in range(max_large + 1):
        for small in range(max_small + 1):
            delivered = large * large_iops + small * small_iops
            if delivered < required:
                continue
            score = (large * large_u + small * small_u, delivered - required, large + small)
            if best is None or score < best[0]:
                best = (score, large, small)
    if best is None:
        raise ValueError("Det valgte, oplåste udstyr kan ikke opfylde IOPS-kravet.")
    return best[1], best[2]


def _pack_family(family: FamilyPlan, rack_start: int, catalog: dict, profile: dict, patching: bool) -> List[RackPlan]:
    large_key, small_key = FAMILY_KEYS[family.family]
    large_u = int(catalog[large_key]["units"])
    small_u = int(catalog[small_key]["units"])
    switch_u = int(catalog["switch_rj45"]["units"])
    panel_u = int(catalog["patch_rj45"]["units"])
    ports = int(catalog["switch_rj45"]["downlink_ports"])
    links = profile["server_links"]
    remaining = [("large", family.large, large_u, int(catalog[large_key]["iops"])),
                 ("small", family.small, small_u, int(catalog[small_key]["iops"]))]
    racks: List[RackPlan] = []
    while any(count for _, count, _, _ in remaining):
        large = small = delivered = server_count = 0
        switches = profile["switches_per_rack"]
        panels = switches if patching else 0
        infra_u = switches * switch_u + panels * panel_u
        capacity_u = RACK_U - infra_u
        port_capacity = switches * ports // links
        updated = []
        for kind, count, units, iops in remaining:
            fit = min(count, capacity_u // units, max(0, port_capacity - server_count))
            if kind == "large": large += fit
            else: small += fit
            server_count += fit
            capacity_u -= fit * units
            delivered += fit * iops
            updated.append((kind, count - fit, units, iops))
        if server_count == 0:
            raise ValueError("Udstyrskataloget giver ingen plads/porte til servere i et rack.")
        remaining = updated
        used = infra_u + large * large_u + small * small_u
        racks.append(RackPlan(rack_start + len(racks), family.family, large, small, switches,
                              panels, infra_u, used, RACK_U - used, delivered))
    return racks


def build_plan(customer: str, requirements: Dict[str, int], profile_name: str, patching: bool,
               router: bool, firewall: bool, catalog: dict, current_xp: int = 0,
               unlocked_only: bool = True) -> PlanResult:
    customer = customer.strip()
    if not customer:
        raise ValueError("Indtast kundenavn.")
    if profile_name not in PROFILES:
        raise ValueError("Ukendt designprofil.")
    profile = PROFILES[profile_name]
    current_xp = max(0, int(current_xp))
    if router and unlocked_only and current_xp < int(catalog["router"]["unlock_xp"]):
        raise ValueError(f'Router låses først op ved {catalog["router"]["unlock_xp"]:,} XP.')
    if firewall and unlocked_only and current_xp < int(catalog["firewall"]["unlock_xp"]):
        raise ValueError(f'Firewall låses først op ved {catalog["firewall"]["unlock_xp"]:,} XP.')
    families: List[FamilyPlan] = []
    racks: List[RackPlan] = []
    for family in FAMILIES:
        required = max(0, int(requirements.get(family, 0)))
        if not required:
            continue
        large_key, small_key = FAMILY_KEYS[family]
        large = catalog[large_key]
        small = catalog[small_key]
        allow_large = not unlocked_only or current_xp >= int(large["unlock_xp"])
        allow_small = not unlocked_only or current_xp >= int(small["unlock_xp"])
        if not allow_large and not allow_small:
            needed = min(int(large["unlock_xp"]), int(small["unlock_xp"]))
            raise ValueError(f"{family}-servere er låst. Første model låses op ved {needed:,} XP.")
        target = math.ceil(required * (100 + profile["reserve_pct"]) / 100)
        lc, sc = suggest_mix(target, int(large["iops"]), int(large["units"]), int(small["iops"]),
                             int(small["units"]), allow_large, allow_small)
        fp = FamilyPlan(family, required, lc, sc, lc * int(large["iops"]) + sc * int(small["iops"]),
                        lc * int(large["units"]) + sc * int(small["units"]), lc + sc)
        families.append(fp)
        family_racks = _pack_family(fp, len(racks) + 1, catalog, profile, patching)
        racks.extend(family_racks)
    if not families:
        raise ValueError("Angiv et IOPS-krav for mindst én serverfamilie.")

    # Router og firewall er fysiske enheder og skal derfor også med i U-planen.
    extra_units = (int(catalog["router"]["units"]) if router else 0) + (int(catalog["firewall"]["units"]) if firewall else 0)
    if extra_units:
        for rack in racks:
            if rack.free_units >= extra_units:
                rack.infrastructure_units += extra_units
                rack.used_units += extra_units
                rack.free_units -= extra_units
                extra_units = 0
                break
        if extra_units:
            racks.append(RackPlan(len(racks) + 1, "Fælles infrastruktur", 0, 0, 0, 0,
                                  extra_units, extra_units, RACK_U - extra_units, 0))

    server_count = sum(x.server_count for x in families)
    switch_count = sum(x.switches for x in racks)
    panel_count = sum(x.patch_panels for x in racks)
    links = profile["server_links"]
    server_cables = server_count * links
    patch_cables = server_cables if patching else 0
    uplink_cables = switch_count * profile["uplinks_per_switch"]
    required_iops = sum(x.required_iops for x in families)
    delivered_iops = sum(x.delivered_iops for x in families)
    bandwidth = delivered_iops / 20000.0
    access = catalog["switch_rj45"]
    uplink_capacity = switch_count * profile["uplinks_per_switch"] * float(access["uplink_gbps"])
    bom: List[BomLine] = []
    for family_plan in families:
        large_key, small_key = FAMILY_KEYS[family_plan.family]
        for key, quantity in ((large_key, family_plan.large), (small_key, family_plan.small)):
            item = catalog[key]
            if quantity:
                price = int(item["price"])
                bom.append(BomLine("Server", item["name"], quantity,
                                   f'{item["units"]}U · EOL {item["eol_hours"]}:00',
                                   price, quantity * price, int(item["unlock_xp"])))
    rack_item = catalog["rack"]
    bom.append(BomLine("Rack", rack_item["name"], len(racks), f'{RACK_U}U pr. rack',
                       int(rack_item["price"]), len(racks) * int(rack_item["price"]), int(rack_item["unlock_xp"])))
    bom.append(BomLine("Netværk", access["name"], switch_count, f'{access["downlink_ports"]} serverporte',
                       int(access["price"]), switch_count * int(access["price"]), int(access["unlock_xp"])))
    if patching:
        item = catalog["patch_rj45"]
        bom.append(BomLine("Netværk", item["name"], panel_count, "", int(item["price"]),
                           panel_count * int(item["price"]), int(item["unlock_xp"])))
    if router:
        item = catalog["router"]
        bom.append(BomLine("Netværk", item["name"], 1, f'EOL {item["eol_hours"]}:00',
                           int(item["price"]), int(item["price"]), int(item["unlock_xp"])))
    if firewall:
        item = catalog["firewall"]
        bom.append(BomLine("Sikkerhed", item["name"], 1, f'EOL {item["eol_hours"]}:00',
                           int(item["price"]), int(item["price"]), int(item["unlock_xp"])))
    cable = catalog["cable_cat6_blue"]
    total_runs = server_cables + patch_cables + uplink_cables
    bom.append(BomLine("Kabel", cable["name"], 1, f"{total_runs} kabelføringer planlagt; butikken sælger kabelrullen, ikke enkeltkabler",
                       int(cable["price"]), int(cable["price"]), int(cable["unlock_xp"])))
    total_cost = sum(line.total_price for line in bom)
    warnings = []
    if bandwidth > uplink_capacity:
        warnings.append(f"Uplink-kapaciteten er for lav: {bandwidth:.1f} Gbps kræves, {uplink_capacity:.1f} Gbps er planlagt.")
    if profile_name == "Økonomisk":
        warnings.append("Økonomisk design har ingen alternativ serverforbindelse ved switch- eller kabelfejl.")
    if not patching:
        warnings.append("Patchpanel er fravalgt; kabler føres direkte til switches.")
    locked_large = [catalog[FAMILY_KEYS[x.family][0]] for x in families
                    if current_xp < int(catalog[FAMILY_KEYS[x.family][0]]["unlock_xp"])]
    if unlocked_only and locked_large:
        next_item = min(locked_large, key=lambda item: int(item["unlock_xp"]))
        warnings.append(f'Den større servermodel er låst. Næste relevante model er {next_item["name"]} ved {next_item["unlock_xp"]:,} XP.')
    return PlanResult(customer, profile_name, families, racks, bom, required_iops, delivered_iops,
                      server_count, len(racks), switch_count, panel_count, server_cables,
                      patch_cables, uplink_cables, bandwidth, uplink_capacity, current_xp,
                      total_cost, warnings)
