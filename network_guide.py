from __future__ import annotations

import ipaddress
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List

APP_FAMILIES = ((0, "System X", "SX"), (1, "RISC", "RISC"),
                (2, "Mainframe", "MF"), (3, "GPU", "GPU"))


@dataclass
class NetworkSegment:
    app: int
    family: str
    customer_cidr: str
    customer_vlan: int
    custom_cidr: str
    custom_vlan: int
    gateway: str
    mask: str
    server_names: List[str]
    server_ips: List[str]


@dataclass
class FirewallRule:
    order: int
    source: str
    destination: str
    port: str
    protocol: str
    bidirectional: str
    action: str
    note: str


@dataclass
class NetworkPlan:
    customer: str
    customer_code: str
    router_name: str
    firewall_name: str
    router_asn: int
    firewall_cluster_ip: str
    internet: bool
    firewall_apps: List[int]
    segments: List[NetworkSegment]
    firewall_rules: List[FirewallRule]
    cable_steps: List[str]
    switch_settings: List[str]
    checks: List[str]
    warnings: List[str]

    def to_dict(self):
        return asdict(self)


def _code(customer: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", customer.upper())
    if not words:
        return "CUST"
    if len(words) == 1:
        return words[0][:6]
    return "".join(word[0] for word in words)[:6]


def _smallest_prefix(host_count: int) -> int:
    for prefix in range(30, 15, -1):
        if (2 ** (32 - prefix)) - 2 >= host_count:
            return prefix
    raise ValueError("Der er for mange servere til den automatiske 192.168.0.0/16-pulje.")


def _next_vlan(customer_vlan: int, used: set[int]) -> int:
    preferred = customer_vlan + 1000
    if 1 <= preferred <= 4094 and preferred not in used:
        used.add(preferred)
        return preferred
    for candidate in range(1000, 4095):
        if candidate != customer_vlan and candidate not in used:
            used.add(candidate)
            return candidate
    raise ValueError("Ingen ledige VLAN-ID'er i området 1000-4094.")


def build_network_plan(customer: str, family_server_counts: Dict[str, int],
                       customer_networks: Dict[str, Dict[str, object]],
                       firewall: bool, internet: bool, firewall_port: int = 443,
                       protocol: str = "TCP", bidirectional: bool = True,
                       router_asn: int = 1, firewall_cluster_ip: str = "10.255.0.1",
                       firewall_app: int | None = None) -> NetworkPlan:
    if not customer.strip():
        raise ValueError("Indtast kundenavn.")
    code = _code(customer)
    pool = ipaddress.ip_network("192.168.0.0/16")
    reserved: List[ipaddress.IPv4Network] = []
    used_vlans: set[int] = set()
    segments: List[NetworkSegment] = []

    try:
        cluster_ip = str(ipaddress.ip_address(firewall_cluster_ip.strip()))
    except ValueError as exc:
        raise ValueError("Firewall Cluster IP er ugyldig.") from exc

    for app, family, short in APP_FAMILIES:
        server_count = int(family_server_counts.get(family, 0))
        if server_count <= 0:
            continue
        supplied = customer_networks.get(family, {})
        cidr_text = str(supplied.get("cidr", "")).strip()
        vlan = int(supplied.get("vlan", 0) or 0)
        if not cidr_text:
            raise ValueError(f"Indtast kundens CIDR/subnet for {family} (App {app}).")
        try:
            customer_net = ipaddress.ip_network(cidr_text, strict=False)
        except ValueError as exc:
            raise ValueError(f"Ugyldigt kundenetværk for {family}: {cidr_text}") from exc
        if not 1 <= vlan <= 4094:
            raise ValueError(f"Kundens VLAN for {family} skal være 1-4094.")
        used_vlans.add(vlan)

        needed_prefix = _smallest_prefix(server_count + 1)  # gateway + servere
        chosen_prefix = min(customer_net.prefixlen, needed_prefix)
        chosen = None
        for candidate in pool.subnets(new_prefix=chosen_prefix):
            if all(not candidate.overlaps(existing) for existing in reserved):
                chosen = candidate
                break
        if chosen is None:
            raise ValueError("Ingen ledige interne subnet i 192.168.0.0/16.")
        reserved.append(chosen)
        hosts = list(chosen.hosts())
        if len(hosts) < server_count + 1:
            raise ValueError(f"Det valgte subnet er for lille til {family}.")
        gateway = str(hosts[0])
        server_ips = [str(ip) for ip in hosts[1:server_count + 1]]
        names = [f"{code}-APP{app}-{short}-SRV-{index:02d}" for index in range(1, server_count + 1)]
        segments.append(NetworkSegment(app, family, str(customer_net), vlan,
                                       str(chosen), _next_vlan(vlan, used_vlans), gateway,
                                       str(chosen.netmask), names, server_ips))

    if not segments:
        raise ValueError("Netværksplanen kræver mindst én serverfamilie.")

    rules: List[FirewallRule] = []
    protected_segments = segments if firewall_app is None else [s for s in segments if s.app == firewall_app]
    if firewall:
        if not protected_segments:
            raise ValueError(f"Firewall App {firewall_app} har ingen servere i denne plan.")
        for segment in protected_segments:
            rules.append(FirewallRule(len(rules) + 1, segment.custom_cidr, "ANY (blank)",
                                      str(firewall_port), protocol,
                                      "Yes" if bidirectional else "No", "ALLOW",
                                      f"Internet/service rule for App {segment.app}"))
        rules.append(FirewallRule(len(rules) + 1, "ANY (blank)", "ANY (blank)",
                                  "ANY (blank)", "Both", "Yes", "DENY",
                                  "Skal ligge nederst - regler læses oppefra og ned"))

    cables = [
        f"Customer closet [{customer}] -> {code}-RTR-01 (router direkte til kunden)",
        f"{code}-RTR-01 -> kundens server-/access-switches",
        "Access-switches -> serverne i den relevante App/VLAN",
    ]
    if firewall:
        cables.extend([
            f"DMZ ISP A (eller ISP B) -> {code}-FW-01",
            f"{code}-FW-01 -> {code}-RTR-01",
        ])
    switch_settings = [
        f"App {segment.app} {segment.family}: ALLOW Customer VLAN {segment.customer_vlan} og Custom VLAN {segment.custom_vlan} paa alle switches i kabelvejen, hvis default VLAN policy er DENY."
        for segment in segments
    ]
    checks = [
        "Routeren viser hvert custom subnet/VLAN under Subnet/VLAN Creation.",
        "Hver router-route har Source = custom VLAN og Target = kundens App-VLAN.",
        "Alle servere har unik IP; .0 er netadresse og .1 er reserveret som gateway.",
        "Hvis switches bruger default DENY, er både customer VLAN og custom VLAN tilladt på hele kabelvejen.",
        "Serverens viste VLAN og IP matcher App-rækken i planen.",
        "Kundens IOPS tæller op efter alle enheder er tændt.",
    ]
    if firewall:
        checks.extend([
            "DMZ-rummet er købt og en ISP-enhed er fysisk forbundet.",
            "ALLOW-regler står over den afsluttende DENY ANY-regel.",
            "Service Request viser OK for route, firewallregel og Internet reachable.",
        ])
    warnings = [
        "App-mapping følger spillets panelrækkefølge: App 0 System X, App 1 RISC, App 2 Mainframe, App 3 GPU.",
        "Customer subnet og Customer VLAN skal aflæses i den aktuelle save; de kan variere og kan ikke udledes af kundenavnet alene.",
    ]
    if firewall and not internet:
        warnings.append("Firewall er valgt uden Internet/DMZ. Firewallen giver kun mening, hvis trafik faktisk føres gennem den.")
    return NetworkPlan(customer.strip(), code, f"{code}-RTR-01", f"{code}-FW-01",
                       int(router_asn), cluster_ip, bool(internet),
                       [s.app for s in protected_segments] if firewall else [], segments, rules,
                       cables, switch_settings, checks, warnings)


def export_network_pdf(plan: NetworkPlan, output_path: Path) -> None:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                    Table, TableStyle)

    def p(text, style):
        return Paragraph(str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), style)

    def table_style(font_size: int = 8):
        return TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#075985")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("LEADING", (0, 0), (-1, -1), font_size + 2),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#94A3B8")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#E0F2FE")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", parent=styles["Title"], fontSize=25,
                              leading=30, textColor=colors.HexColor("#075985"), alignment=TA_CENTER))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], fontSize=16,
                              leading=20, textColor=colors.HexColor("#0369A1"), spaceBefore=8, spaceAfter=8))
    styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=8, leading=10))
    doc = SimpleDocTemplate(str(output_path), pagesize=landscape(A4),
                            leftMargin=13*mm, rightMargin=13*mm, topMargin=13*mm, bottomMargin=13*mm,
                            title=f"{plan.customer} - Network and Firewall Guide")
    story = [Spacer(1, 20*mm), p("NIS DATA CENTER PLANNER", styles["Heading2"]),
             Spacer(1, 5*mm), p(f"{plan.customer} - Netvaerks- og firewallguide", styles["CoverTitle"]),
             Spacer(1, 6*mm), p(f"Router: {plan.router_name} | ASN: {plan.router_asn} | Firewall: {plan.firewall_name}", styles["Heading2"]),
             Spacer(1, 8*mm), p("Denne guide er lavet til spillets konfigurationsfelter. Foelg raekkefoelgen: kabelvej, router, server-IP'er, firewall og kontrol.", styles["BodyText"]), PageBreak()]

    story += [p("1. Kabel- og enhedsplan", styles["Section"])]
    cable_data = [["Trin", "Forbindelse"]] + [[str(i), step] for i, step in enumerate(plan.cable_steps, 1)]
    table = Table(cable_data, colWidths=[18*mm, 245*mm], repeatRows=1)
    table.setStyle(table_style())
    story += [table, Spacer(1, 5*mm), p("Navngivning", styles["Heading2"]),
              p(f"Router: {plan.router_name} | Firewall: {plan.firewall_name} | Firewall Cluster IP: {plan.firewall_cluster_ip}", styles["BodyText"]),
              Spacer(1, 4*mm), p("Switch VLAN settings", styles["Heading2"])]
    for setting in plan.switch_settings:
        story.append(p(setting, styles["Small"]))
    story += [Spacer(1, 4*mm), p("Vigtigt: Customer closet forbindes til routeren. Internet fra DMZ gaar gennem firewallen til routeren.", styles["BodyText"]), PageBreak()]

    story += [p("2. Router - Subnet/VLAN Creation", styles["Section"])]
    subnet_data = [["App", "Familie", "Custom subnet", "Mask", "Gateway", "Custom VLAN", "Customer VLAN"]]
    for s in plan.segments:
        subnet_data.append([s.app, s.family, s.custom_cidr, s.mask, s.gateway, s.custom_vlan, s.customer_vlan])
    table = Table(subnet_data, colWidths=[14*mm, 30*mm, 42*mm, 42*mm, 35*mm, 30*mm, 32*mm], repeatRows=1)
    table.setStyle(table_style()); story += [table, Spacer(1, 5*mm), p("Router - Routes", styles["Heading2"])]
    route_data = [["Source", "Target", "Target IP", "Forklaring"]]
    for s in plan.segments:
        route_data.append([s.custom_vlan, s.customer_vlan,
                           plan.firewall_cluster_ip if s.app in plan.firewall_apps else "Blank",
                           f"Custom App {s.app} -> customer App {s.app}"])
    table = Table(route_data, colWidths=[35*mm, 35*mm, 48*mm, 120*mm], repeatRows=1)
    table.setStyle(table_style()); story += [table, Spacer(1, 3*mm),
        p("Hvis Service Request specifikt siger 'target IP toward a firewall', brug Firewall Cluster IP. Ved en almindelig subnet-route uden firewall lades Target IP blank.", styles["Small"]), PageBreak()]

    story += [p("3. Server-IP-plan", styles["Section"])]
    ip_data = [["Enhedsnavn", "App", "Familie", "IP-adresse", "Mask", "Gateway", "VLAN"]]
    for s in plan.segments:
        for name, ip in zip(s.server_names, s.server_ips):
            ip_data.append([name, s.app, s.family, ip, s.mask, s.gateway, s.custom_vlan])
    table = Table(ip_data, colWidths=[55*mm, 12*mm, 28*mm, 34*mm, 38*mm, 34*mm, 22*mm], repeatRows=1)
    table.setStyle(table_style(font_size=7)); story += [table, PageBreak()]

    if plan.firewall_rules:
        story += [p("4. Firewall rules", styles["Section"]),
                  p(f"Cluster IP: {plan.firewall_cluster_ip}. Brug samme Cluster IP paa redundante firewalls for at synkronisere regler.", styles["BodyText"])]
        fw_data = [["#", "Source", "Destination", "Port", "Protocol", "Bi-dir", "Action", "Note"]]
        for r in plan.firewall_rules:
            fw_data.append([r.order, r.source, r.destination, r.port, r.protocol,
                            r.bidirectional, r.action, r.note])
        table = Table(fw_data, colWidths=[10*mm, 40*mm, 36*mm, 25*mm, 25*mm, 20*mm, 22*mm, 72*mm], repeatRows=1)
        table.setStyle(table_style(font_size=7)); story += [table, Spacer(1, 4*mm),
            p("Regler behandles oppefra og ned. ALLOW skal derfor staa over DENY ANY.", styles["BodyText"]), PageBreak()]

    story += [p("5. Kontrol i spillet", styles["Section"])]
    check_data = [["#", "Kontrolpunkt"]] + [[str(index), item] for index, item in enumerate(plan.checks, 1)]
    table = Table(check_data, colWidths=[12*mm, 245*mm], repeatRows=1)
    table.setStyle(table_style(font_size=8)); story += [table, Spacer(1, 5*mm), p("Forbehold", styles["Heading2"])]
    warning_data = [["", item] for item in plan.warnings]
    warning_table = Table(warning_data, colWidths=[6*mm, 250*mm])
    warning_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#475569")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])); story.append(warning_table)

    def footer(canvas, document):
        canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(13*mm, 7*mm, f"NIS Data Center Planner - {plan.customer}")
        canvas.drawRightString(284*mm, 7*mm, f"Side {document.page}"); canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
