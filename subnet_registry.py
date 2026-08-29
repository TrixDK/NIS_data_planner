from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Iterable


DEFAULT_POOL = "192.168.0.0/16"
DEFAULT_VLAN_START = 1000
DEFAULT_VLAN_END = 4094


@dataclass(frozen=True)
class SubnetSuggestion:
    cidr: str
    mask: str
    gateway: str
    server_ips: list[str]
    broadcast: str
    vlan: int
    usable_addresses: int
    spare_addresses: int


def required_prefix(server_count: int) -> int:
    """Return the smallest IPv4 subnet that fits servers plus one gateway."""
    if server_count < 1:
        raise ValueError("Antal servere skal være mindst 1.")

    required_addresses = server_count + 3  # servers + gateway + network + broadcast
    block_size = 4
    while block_size < required_addresses:
        block_size *= 2
    return 32 - (block_size.bit_length() - 1)


def find_available_subnet(
    server_count: int,
    used_cidrs: Iterable[str] = (),
    pool_cidr: str = DEFAULT_POOL,
) -> ipaddress.IPv4Network:
    pool = ipaddress.ip_network(pool_cidr, strict=True)
    if pool.version != 4:
        raise ValueError("Adressepuljen skal være IPv4.")

    prefix = required_prefix(server_count)
    if prefix < pool.prefixlen:
        raise ValueError("Adressepuljen er for lille til det ønskede antal servere.")

    used: list[ipaddress.IPv4Network] = []
    for value in used_cidrs:
        try:
            network = ipaddress.ip_network(str(value).strip(), strict=False)
        except ValueError:
            continue
        if network.version == 4:
            used.append(network)

    for candidate in pool.subnets(new_prefix=prefix):
        if not any(candidate.overlaps(existing) for existing in used):
            return candidate
    raise ValueError(f"Der er ingen ledige subnet i {pool}.")


def find_available_vlan(
    used_vlans: Iterable[int],
    start: int = DEFAULT_VLAN_START,
    end: int = DEFAULT_VLAN_END,
) -> int:
    if not 1 <= start <= end <= 4094:
        raise ValueError("VLAN-området skal ligge mellem 1 og 4094.")
    used = {int(value) for value in used_vlans if str(value).strip()}
    for vlan in range(start, end + 1):
        if vlan not in used:
            return vlan
    raise ValueError(f"Der er ingen ledige VLAN i området {start}-{end}.")


def suggest_subnet(
    server_count: int,
    used_cidrs: Iterable[str] = (),
    used_vlans: Iterable[int] = (),
    pool_cidr: str = DEFAULT_POOL,
    vlan_start: int = DEFAULT_VLAN_START,
) -> SubnetSuggestion:
    network = find_available_subnet(server_count, used_cidrs, pool_cidr)
    vlan = find_available_vlan(used_vlans, vlan_start)
    hosts = list(network.hosts())
    gateway = hosts[0]
    server_ips = hosts[1:server_count + 1]
    return SubnetSuggestion(
        cidr=str(network),
        mask=str(network.netmask),
        gateway=str(gateway),
        server_ips=[str(ip) for ip in server_ips],
        broadcast=str(network.broadcast_address),
        vlan=vlan,
        usable_addresses=len(hosts),
        spare_addresses=len(hosts) - 1 - server_count,
    )


def validate_registry_entry(
    cidr: str,
    gateway: str,
    vlan: int,
    used_cidrs: Iterable[str] = (),
    used_vlans: Iterable[int] = (),
) -> ipaddress.IPv4Network:
    """Validate and normalize a manually entered network registry row."""
    try:
        network = ipaddress.ip_network(str(cidr).strip(), strict=False)
    except ValueError as exc:
        raise ValueError("Subnet skal skrives som CIDR, fx 192.168.70.0/24.") from exc
    if network.version != 4:
        raise ValueError("Subnettet skal være IPv4.")

    try:
        gateway_ip = ipaddress.ip_address(str(gateway).strip())
    except ValueError as exc:
        raise ValueError("Gateway er ikke en gyldig IPv4-adresse.") from exc
    if gateway_ip.version != 4 or gateway_ip not in network:
        raise ValueError("Gateway skal ligge i det valgte subnet.")
    if gateway_ip in (network.network_address, network.broadcast_address):
        raise ValueError("Gateway må ikke være netværksadressen eller broadcast-adressen.")

    try:
        vlan_number = int(vlan)
    except (TypeError, ValueError) as exc:
        raise ValueError("VLAN skal være et helt tal mellem 1 og 4094.") from exc
    if not 1 <= vlan_number <= 4094:
        raise ValueError("VLAN skal være mellem 1 og 4094.")

    for value in used_cidrs:
        try:
            existing = ipaddress.ip_network(str(value).strip(), strict=False)
        except ValueError:
            continue
        if existing.version == 4 and network.overlaps(existing):
            raise ValueError(f"Subnettet overlapper et eksisterende netværk: {existing}.")

    used_vlan_numbers = {int(value) for value in used_vlans if str(value).strip()}
    if vlan_number in used_vlan_numbers:
        raise ValueError(f"VLAN {vlan_number} er allerede i brug.")
    return network
