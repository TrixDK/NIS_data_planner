from __future__ import annotations

import json
import ipaddress
import os
import sqlite3
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFormLayout,
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QPushButton, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget)

from planner_core import FAMILIES, DEFAULT_CATALOG, build_plan, load_catalog, save_catalog
from network_guide import build_network_plan, export_network_pdf
from subnet_registry import SubnetSuggestion, suggest_subnet, validate_registry_entry
from app_paths import CATALOG_PATH, DATA_DIR, DB_PATH, EXPORT_DIR, SETTINGS_PATH, initialize_user_data
from update_service import get_latest_release
from version_info import APP_NAME, APP_VERSION, DEFAULT_GITHUB_REPOSITORY

STYLE = """
QWidget { background:#0b1220; color:#e5e7eb; font:10pt 'Segoe UI'; }
QFrame#side { background:#07101e; border-right:1px solid #263449; }
QFrame#resultCard { background:#0f1d31; border:1px solid #28506d; border-radius:10px; }
QLabel#brand { color:#38bdf8; font-size:18pt; font-weight:700; padding:20px; }
QLabel#title { color:#f8fafc; font-size:20pt; font-weight:700; }
QLabel#muted { color:#94a3b8; }
QLabel#metric { color:#7dd3fc; font-size:16pt; font-weight:700; }
QLabel#subnetValue { color:#7dd3fc; font-size:14pt; font-weight:700; }
QPushButton { background:#1e293b; border:1px solid #334155; border-radius:7px; padding:9px 13px; }
QPushButton:hover { background:#293548; } QPushButton#primary { background:#0284c7; font-weight:700; }
QLineEdit,QSpinBox,QComboBox { background:#111827; border:1px solid #3b4a61; border-radius:5px; padding:7px; }
QTableWidget { background:#0f172a; alternate-background-color:#111c30; border:1px solid #263449; gridline-color:#263449; }
QHeaderView::section { background:#1e293b; color:#cbd5e1; padding:7px; border:0; }
"""


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return {"github_repository": DEFAULT_GITHUB_REPOSITORY}
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (OSError, ValueError, json.JSONDecodeError):
        return {"github_repository": DEFAULT_GITHUB_REPOSITORY}


def save_settings(settings: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")


def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT NOT NULL, created_at TEXT NOT NULL,
            profile TEXT NOT NULL, inputs_json TEXT NOT NULL, result_json TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS subnet_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            purpose TEXT NOT NULL DEFAULT '',
            server_count INTEGER NOT NULL,
            cidr TEXT NOT NULL UNIQUE,
            mask TEXT NOT NULL,
            gateway TEXT NOT NULL,
            first_server_ip TEXT NOT NULL,
            last_server_ip TEXT NOT NULL,
            broadcast TEXT NOT NULL,
            vlan INTEGER NOT NULL UNIQUE,
            note TEXT NOT NULL DEFAULT 'Aktiv',
            created_at TEXT NOT NULL)""")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(subnet_allocations)")}
        if "note" not in columns:
            conn.execute("ALTER TABLE subnet_allocations ADD COLUMN note TEXT NOT NULL DEFAULT 'Aktiv'")


def collect_used_networks(exclude_allocation_id: int | None = None):
    """Read both subnet reservations and known networks from saved plans."""
    used_cidrs: set[str] = set()
    used_vlans: set[int] = set()
    with db() as conn:
        if exclude_allocation_id is None:
            allocation_rows = conn.execute("SELECT cidr, vlan FROM subnet_allocations").fetchall()
        else:
            allocation_rows = conn.execute(
                "SELECT cidr, vlan FROM subnet_allocations WHERE id != ?",
                (exclude_allocation_id,),
            ).fetchall()
        for row in allocation_rows:
            used_cidrs.add(str(row["cidr"]))
            used_vlans.add(int(row["vlan"]))
        plan_rows = conn.execute("SELECT inputs_json, result_json FROM plans").fetchall()

    for row in plan_rows:
        try:
            inputs = json.loads(row["inputs_json"])
            for network in inputs.get("customer_networks", {}).values():
                cidr = str(network.get("cidr", "")).strip()
                vlan = int(network.get("vlan", 0) or 0)
                if cidr:
                    used_cidrs.add(cidr)
                if vlan:
                    used_vlans.add(vlan)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

        try:
            result = json.loads(row["result_json"])
            for segment in result.get("network_plan", {}).get("segments", []):
                cidr = str(segment.get("custom_cidr", "")).strip()
                vlan = int(segment.get("custom_vlan", 0) or 0)
                if cidr:
                    used_cidrs.add(cidr)
                if vlan:
                    used_vlans.add(vlan)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return used_cidrs, used_vlans


class PlannerPage(QWidget):
    def __init__(self, on_saved):
        super().__init__(); self.on_saved = on_saved; self.result = None; self.network_result = None
        root = QVBoxLayout(self); root.setContentsMargins(26,22,26,24); root.setSpacing(13)
        title = QLabel("Ny kapacitetsplan"); title.setObjectName("title"); root.addWidget(title)
        sub = QLabel("IOPS → servere → racks → netværk → komplet indkøbsliste"); sub.setObjectName("muted"); root.addWidget(sub)
        form = QGridLayout(); self.customer = QLineEdit(); self.customer.setPlaceholderText("Kundenavn")
        self.profile = QComboBox(); self.profile.addItems(["Økonomisk","Balanceret","Redundant"]); self.profile.setCurrentText("Balanceret")
        self.xp = QSpinBox(); self.xp.setRange(0,10_000_000); self.xp.setSingleStep(100); self.xp.setSuffix(" XP")
        self.unlocked_only = QCheckBox("Brug kun oplåst udstyr"); self.unlocked_only.setChecked(True)
        self.patching = QCheckBox("Patchpaneler"); self.patching.setChecked(True)
        self.router = QCheckBox("Router"); self.firewall = QCheckBox("Firewall")
        self.subnet_plan = QCheckBox("Subnet/IP-plan"); self.internet = QCheckBox("Internet/DMZ")
        form.addWidget(QLabel("Kunde"),0,0); form.addWidget(self.customer,0,1)
        form.addWidget(QLabel("Design"),0,2); form.addWidget(self.profile,0,3)
        form.addWidget(QLabel("Din XP"),0,4); form.addWidget(self.xp,0,5); form.addWidget(self.unlocked_only,0,6)
        form.addWidget(self.patching,1,0); form.addWidget(self.router,1,1); form.addWidget(self.subnet_plan,1,2); form.addWidget(self.firewall,1,3); form.addWidget(self.internet,1,4)
        root.addLayout(form)
        req = QGridLayout(); req.addWidget(QLabel("IOPS-krav pr. familie"),0,0,1,4)
        self.spins = {}
        for i, family in enumerate(FAMILIES):
            req.addWidget(QLabel(family),1,i); spin=QSpinBox(); spin.setRange(0,10_000_000); spin.setSingleStep(5000); spin.setSpecialValueText("Ikke anvendt")
            self.spins[family]=spin; req.addWidget(spin,2,i)
        root.addLayout(req)
        network = QGridLayout(); network.addWidget(QLabel("Kundedata fra panelet (kræves kun ved Subnet/IP-plan)"),0,0,1,6)
        network.addWidget(QLabel("App"),1,0); network.addWidget(QLabel("Familie"),1,1); network.addWidget(QLabel("Customer CIDR/subnet"),1,2); network.addWidget(QLabel("Customer VLAN"),1,3)
        self.customer_cidrs={}; self.customer_vlans={}
        for i,family in enumerate(FAMILIES):
            network.addWidget(QLabel(str(i)),i+2,0); network.addWidget(QLabel(family),i+2,1)
            cidr=QLineEdit(); cidr.setPlaceholderText("fx 59.107.13.0/27"); vlan=QSpinBox(); vlan.setRange(0,4094); vlan.setSpecialValueText("Ikke angivet")
            self.customer_cidrs[family]=cidr; self.customer_vlans[family]=vlan; network.addWidget(cidr,i+2,2); network.addWidget(vlan,i+2,3)
        self.router_asn=QSpinBox(); self.router_asn.setRange(1,65535); self.router_asn.setValue(1)
        self.cluster_ip=QLineEdit("10.255.0.1"); self.firewall_port=QSpinBox(); self.firewall_port.setRange(1,65535); self.firewall_port.setValue(443)
        self.protocol=QComboBox(); self.protocol.addItems(["TCP","UDP","Both"])
        self.firewall_app=QComboBox(); self.firewall_app.addItems(["Alle aktive Apps","App 0 - System X","App 1 - RISC","App 2 - Mainframe","App 3 - GPU"])
        network.addWidget(QLabel("Router ASN"),2,4); network.addWidget(self.router_asn,2,5)
        network.addWidget(QLabel("Firewall Cluster IP"),3,4); network.addWidget(self.cluster_ip,3,5)
        network.addWidget(QLabel("Firewall-port"),4,4); network.addWidget(self.firewall_port,4,5)
        network.addWidget(QLabel("Protokol"),5,4); network.addWidget(self.protocol,5,5)
        network.addWidget(QLabel("Firewall gælder"),6,4); network.addWidget(self.firewall_app,6,5)
        root.addLayout(network)
        actions=QHBoxLayout(); calc=QPushButton("Beregn komplet plan"); calc.setObjectName("primary"); calc.clicked.connect(self.calculate)
        save=QPushButton("Gem plan"); save.clicked.connect(self.save); export=QPushButton("Hent netværksguide som PDF"); export.clicked.connect(self.export_pdf)
        actions.addWidget(calc); actions.addWidget(save); actions.addWidget(export); actions.addStretch(); root.addLayout(actions)
        metrics=QHBoxLayout(); self.metric_labels=[]
        for caption in ("Servere","Racks","Switches","Leveret IOPS","Båndbredde","Pris"):
            box=QVBoxLayout(); val=QLabel("—"); val.setObjectName("metric"); box.addWidget(val); box.addWidget(QLabel(caption)); metrics.addLayout(box); metrics.addStretch(); self.metric_labels.append(val)
        root.addLayout(metrics)
        self.tabs=QStackedWidget(); root.addWidget(self.tabs,1)
        result_widget=QWidget(); rv=QVBoxLayout(result_widget); nav=QHBoxLayout()
        self.result_stack=QStackedWidget();
        for idx,name in enumerate(("Indkøbsliste","Rackplan","Serverplan","Netværksguide")):
            b=QPushButton(name); b.clicked.connect(lambda _,i=idx:self.result_stack.setCurrentIndex(i)); nav.addWidget(b)
        nav.addStretch(); rv.addLayout(nav); rv.addWidget(self.result_stack,1)
        self.bom=QTableWidget(0,7); self.bom.setHorizontalHeaderLabels(["Kategori","Udstyr","Antal","Stk. pris","Total","XP-krav","Bemærkning"])
        self.racks=QTableWidget(0,10); self.racks.setHorizontalHeaderLabels(["Rack","Familie","Store","Små","Switches","Patch","Infra U","Brugt U","Ledig U","IOPS"])
        self.families=QTableWidget(0,7); self.families.setHorizontalHeaderLabels(["Familie","Krav","Store","Små","Servere","Leveret","U"])
        for t in (self.bom,self.racks,self.families): t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); t.setEditTriggers(QTableWidget.NoEditTriggers); t.setAlternatingRowColors(True); self.result_stack.addWidget(t)
        self.network_text=QTextEdit(); self.network_text.setReadOnly(True); self.result_stack.addWidget(self.network_text)
        self.warning=QLabel(""); self.warning.setWordWrap(True); self.warning.setStyleSheet("color:#fde68a"); rv.addWidget(self.warning)
        self.tabs.addWidget(result_widget)

    def inputs(self): return {f:self.spins[f].value() for f in FAMILIES}
    def load_saved(self, customer, profile, inputs):
        self.customer.setText(customer)
        self.profile.setCurrentText(profile)
        for family in FAMILIES:
            self.spins[family].setValue(int(inputs.get("requirements", {}).get(family, 0)))
        self.patching.setChecked(bool(inputs.get("patching", True)))
        self.router.setChecked(bool(inputs.get("router", False)))
        self.firewall.setChecked(bool(inputs.get("firewall", False)))
        self.subnet_plan.setChecked(bool(inputs.get("subnet_plan", False))); self.internet.setChecked(bool(inputs.get("internet", False)))
        self.xp.setValue(int(inputs.get("current_xp", 0)))
        self.unlocked_only.setChecked(bool(inputs.get("unlocked_only", True)))
        self.router_asn.setValue(int(inputs.get("router_asn",1))); self.cluster_ip.setText(str(inputs.get("cluster_ip","10.255.0.1"))); self.firewall_port.setValue(int(inputs.get("firewall_port",443))); self.protocol.setCurrentText(str(inputs.get("protocol","TCP")))
        self.firewall_app.setCurrentIndex(int(inputs.get("firewall_app_index",0)))
        saved_networks=inputs.get("customer_networks",{})
        for family in FAMILIES:
            self.customer_cidrs[family].setText(str(saved_networks.get(family,{}).get("cidr",""))); self.customer_vlans[family].setValue(int(saved_networks.get(family,{}).get("vlan",0)))
        self.calculate()
    def calculate(self):
        try:
            needs_router=self.router.isChecked() or self.subnet_plan.isChecked()
            self.result=build_plan(self.customer.text(),self.inputs(),self.profile.currentText(),self.patching.isChecked(),needs_router,self.firewall.isChecked(),load_catalog(CATALOG_PATH),self.xp.value(),self.unlocked_only.isChecked())
            self.network_result=None
            if self.subnet_plan.isChecked():
                counts={f.family:f.server_count for f in self.result.families}
                networks={family:{"cidr":self.customer_cidrs[family].text(),"vlan":self.customer_vlans[family].value()} for family in FAMILIES}
                selected_app=None if self.firewall_app.currentIndex()==0 else self.firewall_app.currentIndex()-1
                self.network_result=build_network_plan(self.customer.text(),counts,networks,self.firewall.isChecked(),self.internet.isChecked(),self.firewall_port.value(),self.protocol.currentText(),True,self.router_asn.value(),self.cluster_ip.text(),selected_app)
        except Exception as exc: QMessageBox.warning(self,"Kan ikke beregne",str(exc)); return
        r=self.result; vals=[r.server_count,r.rack_count,r.switch_count,f"{r.delivered_iops:,}",f"{r.required_bandwidth_gbps:.1f} Gbps",f"$ {r.total_cost:,}"]
        for label,value in zip(self.metric_labels,vals): label.setText(str(value))
        self._fill(self.bom,[[x.category,x.item,x.quantity,f"$ {x.unit_price:,}",f"$ {x.total_price:,}",f"{x.unlock_xp:,}",x.note] for x in r.bom])
        self._fill(self.racks,[[x.rack_no,x.family,x.large,x.small,x.switches,x.patch_panels,x.infrastructure_units,x.used_units,x.free_units,f"{x.delivered_iops:,}"] for x in r.racks])
        self._fill(self.families,[[x.family,f"{x.required_iops:,}",x.large,x.small,x.server_count,f"{x.delivered_iops:,}",x.units] for x in r.families])
        self.network_text.setPlainText(self.network_preview() if self.network_result else "Slå Subnet/IP-plan til og indtast Customer CIDR samt Customer VLAN for hver aktiv App.")
        self.warning.setText("\n".join("⚠ " + w for w in r.warnings))
    def network_preview(self):
        p=self.network_result; lines=[f"KABEL- OG IP-GUIDE - {p.customer}",f"Router: {p.router_name} | ASN {p.router_asn}",f"Firewall: {p.firewall_name} | Cluster IP {p.firewall_cluster_ip}","","KABELVEJ"]
        lines += [f"{i}. {step}" for i,step in enumerate(p.cable_steps,1)]
        lines += ["","SWITCH VLAN SETTINGS"]+[f"- {x}" for x in p.switch_settings]
        lines += ["","ROUTER - SUBNET/VLAN CREATION"]
        for s in p.segments: lines.append(f"App {s.app} {s.family}: subnet {s.custom_cidr} | mask {s.mask} | gateway {s.gateway} | VLAN {s.custom_vlan}")
        lines += ["","ROUTER - ROUTES"]
        for s in p.segments: lines.append(f"Source {s.custom_vlan} -> Target {s.customer_vlan} | Target IP: {p.firewall_cluster_ip if s.app in p.firewall_apps else 'blank'}")
        lines += ["","SERVER-IP'ER"]
        for s in p.segments:
            lines += [f"{name}: {ip} | GW {s.gateway} | VLAN {s.custom_vlan}" for name,ip in zip(s.server_names,s.server_ips)]
        if p.firewall_rules:
            lines += ["","FIREWALL - REGLER I DENNE RÆKKEFØLGE"]
            for rule in p.firewall_rules: lines.append(f"{rule.order}. {rule.source} -> {rule.destination} | {rule.protocol} {rule.port} | Bi-dir {rule.bidirectional} | {rule.action}")
        lines += ["","KONTROL"]+[f"[ ] {x}" for x in p.checks]
        return "\n".join(lines)
    def export_pdf(self):
        self.calculate()
        if not self.network_result: QMessageBox.information(self,"Ingen netværksplan","Slå Subnet/IP-plan til og beregn planen først."); return
        suggested=f"{self.network_result.customer.replace(' ','_')}_network_firewall_guide.pdf"
        path,_=QFileDialog.getSaveFileName(self,"Gem netværksguide",str(EXPORT_DIR/suggested),"PDF (*.pdf)")
        if path:
            try: export_network_pdf(self.network_result,Path(path)); QMessageBox.information(self,"PDF gemt",f"Guiden er gemt her:\n{path}")
            except Exception as exc: QMessageBox.warning(self,"Kunne ikke gemme PDF",str(exc))
    @staticmethod
    def _fill(table,rows):
        table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,value in enumerate(row): table.setItem(i,j,QTableWidgetItem(str(value)))
    def save(self):
        self.calculate()
        if not self.result:return
        inputs={"requirements":self.inputs(),"patching":self.patching.isChecked(),"router":self.router.isChecked(),"firewall":self.firewall.isChecked(),"current_xp":self.xp.value(),"unlocked_only":self.unlocked_only.isChecked(),"subnet_plan":self.subnet_plan.isChecked(),"internet":self.internet.isChecked(),"router_asn":self.router_asn.value(),"cluster_ip":self.cluster_ip.text(),"firewall_port":self.firewall_port.value(),"protocol":self.protocol.currentText(),"firewall_app_index":self.firewall_app.currentIndex(),"customer_networks":{family:{"cidr":self.customer_cidrs[family].text(),"vlan":self.customer_vlans[family].value()} for family in FAMILIES}}
        with db() as conn: conn.execute("INSERT INTO plans(customer,created_at,profile,inputs_json,result_json) VALUES(?,?,?,?,?)",(self.result.customer,datetime.now().isoformat(timespec="seconds"),self.result.profile,json.dumps(inputs),json.dumps(self.result.to_dict(),ensure_ascii=False)))
        self.on_saved(); QMessageBox.information(self,"Gemt","Planen er gemt i den nye v1-database.")


class SubnetPage(QWidget):
    def __init__(self, on_reserved=None):
        super().__init__()
        self.on_reserved = on_reserved
        self.suggestion: SubnetSuggestion | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 24)
        root.setSpacing(13)

        title = QLabel("Subnetberegner")
        title.setObjectName("title")
        root.addWidget(title)
        intro = QLabel(
            "Brug kun denne side, når programmet skal beregne størrelsen ud fra et antal servere. "
            "Du kan bruge IP/VLAN-registeret helt uden serveroplysninger."
        )
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QGridLayout()
        self.customer = QLineEdit()
        self.customer.setPlaceholderText("Kundenavn")
        self.purpose = QLineEdit()
        self.purpose.setPlaceholderText("Valgfri type eller beskrivelse")
        self.server_count = QSpinBox()
        self.server_count.setRange(1, 10000)
        self.server_count.setValue(6)
        self.server_count.setSuffix(" servere")
        self.pool = QLineEdit("192.168.0.0/16")
        self.vlan_start = QSpinBox()
        self.vlan_start.setRange(1, 4094)
        self.vlan_start.setValue(1000)
        fields = (
            ("Kunde", self.customer), ("Type / beskrivelse (valgfri)", self.purpose),
            ("Antal servere", self.server_count), ("Adressepulje", self.pool),
            ("Start VLAN-søgning ved", self.vlan_start),
        )
        for index, (caption, widget) in enumerate(fields):
            row, column = divmod(index, 2)
            form.addWidget(QLabel(caption), row, column * 2)
            form.addWidget(widget, row, column * 2 + 1)
        root.addLayout(form)

        actions = QHBoxLayout()
        find_button = QPushButton("Find ledigt subnet og VLAN")
        find_button.setObjectName("primary")
        find_button.clicked.connect(self.find_suggestion)
        self.reserve_button = QPushButton("Gem i IP/VLAN-register")
        self.reserve_button.setEnabled(False)
        self.reserve_button.clicked.connect(self.reserve)
        self.copy_button = QPushButton("Kopiér opsætning")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_suggestion)
        actions.addWidget(find_button)
        actions.addWidget(self.reserve_button)
        actions.addWidget(self.copy_button)
        actions.addStretch()
        root.addLayout(actions)

        card = QFrame()
        card.setObjectName("resultCard")
        card_layout = QGridLayout(card)
        card_layout.setContentsMargins(18, 15, 18, 15)
        self.result_values: dict[str, QLabel] = {}
        fields = (
            ("Subnet", "cidr"), ("Subnetmaske", "mask"), ("VLAN", "vlan"),
            ("Gateway", "gateway"), ("Server-IP'er", "server_range"),
            ("Broadcast", "broadcast"), ("Ledige adresser bagefter", "spare"),
        )
        for index, (caption, key) in enumerate(fields):
            row, column = divmod(index, 4)
            box = QVBoxLayout()
            value = QLabel("—")
            value.setObjectName("subnetValue")
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            box.addWidget(value)
            label = QLabel(caption)
            label.setObjectName("muted")
            box.addWidget(label)
            card_layout.addLayout(box, row, column)
            self.result_values[key] = value
        root.addWidget(card)
        self.status = QLabel("Forslaget bliver først optaget, når du gemmer det i registeret.")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        root.addStretch()

    def find_suggestion(self):
        try:
            used_cidrs, used_vlans = collect_used_networks()
            self.suggestion = suggest_subnet(
                self.server_count.value(),
                used_cidrs,
                used_vlans,
                self.pool.text().strip(),
                self.vlan_start.value(),
            )
        except Exception as exc:
            self.suggestion = None
            self.reserve_button.setEnabled(False)
            self.copy_button.setEnabled(False)
            QMessageBox.warning(self, "Kan ikke finde et forslag", str(exc))
            return
        self._show_suggestion()
        self.reserve_button.setEnabled(True)
        self.copy_button.setEnabled(True)
        self.status.setText("Forslaget er ledigt lige nu, men endnu ikke reserveret.")

    def _show_suggestion(self):
        s = self.suggestion
        if not s:
            return
        server_range = s.server_ips[0]
        if len(s.server_ips) > 1:
            server_range += f" – {s.server_ips[-1]}"
        values = {
            "cidr": s.cidr,
            "mask": s.mask,
            "vlan": str(s.vlan),
            "gateway": s.gateway,
            "server_range": server_range,
            "broadcast": s.broadcast,
            "spare": str(s.spare_addresses),
        }
        for key, value in values.items():
            self.result_values[key].setText(value)

    def reserve(self):
        customer = self.customer.text().strip()
        if not customer:
            QMessageBox.information(self, "Kundenavn mangler", "Indtast kundenavnet, før subnettet reserveres.")
            self.customer.setFocus()
            return
        if not self.suggestion:
            self.find_suggestion()
            if not self.suggestion:
                return

        s = self.suggestion
        try:
            with db() as conn:
                conn.execute(
                    """INSERT INTO subnet_allocations(
                        customer, purpose, server_count, cidr, mask, gateway,
                        first_server_ip, last_server_ip, broadcast, vlan, note, created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        customer, self.purpose.text().strip(), self.server_count.value(),
                        s.cidr, s.mask, s.gateway, s.server_ips[0], s.server_ips[-1],
                        s.broadcast, s.vlan, "Aktiv", datetime.now().isoformat(timespec="seconds"),
                    ),
                )
        except sqlite3.IntegrityError:
            QMessageBox.warning(
                self, "Forslaget blev optaget",
                "Subnettet eller VLAN'et er netop blevet reserveret. Klik på Find igen for et nyt forslag.",
            )
            self.find_suggestion()
            return

        self.reserve_button.setEnabled(False)
        self.status.setText(f"Reserveret til {customer}. Det bliver ikke foreslået til andre kunder.")
        if self.on_reserved:
            self.on_reserved()
        QMessageBox.information(self, "Reservation gemt", f"{s.cidr} og VLAN {s.vlan} er reserveret til {customer}.")

    def copy_suggestion(self):
        if not self.suggestion:
            return
        s = self.suggestion
        server_range = s.server_ips[0] if len(s.server_ips) == 1 else f"{s.server_ips[0]} - {s.server_ips[-1]}"
        text = "\n".join([
            f"Kunde: {self.customer.text().strip() or 'Ikke angivet'}",
            f"Type: {self.purpose.text().strip() or 'Ikke angivet'}",
            f"Servere: {self.server_count.value()}",
            f"Subnet: {s.cidr}",
            f"Subnetmaske: {s.mask}",
            f"VLAN: {s.vlan}",
            f"Gateway: {s.gateway}",
            f"Server-IP'er: {server_range}",
            f"Broadcast: {s.broadcast}",
        ])
        QApplication.clipboard().setText(text)
        self.status.setText("Opsætningen er kopieret og klar til at indsætte i dine noter.")


class NetworkRegistryPage(QWidget):
    def __init__(self):
        super().__init__()
        self.editing_id: int | None = None
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 24)
        root.setSpacing(12)

        title = QLabel("IP- og VLAN-register")
        title.setObjectName("title")
        root.addWidget(title)
        intro = QLabel(
            "Gem de subnet og VLAN'er, du har oprettet i spillet. "
            "Serverantal og serverudstyr bruges ikke på denne side. Type-feltet er valgfrit."
        )
        intro.setObjectName("muted")
        intro.setWordWrap(True)
        root.addWidget(intro)

        form = QGridLayout()
        self.manual_customer = QLineEdit()
        self.manual_customer.setPlaceholderText("Fx Kunde A")
        self.manual_type = QLineEdit()
        self.manual_type.setPlaceholderText("Valgfri, fx System X")
        self.manual_cidr = QLineEdit()
        self.manual_cidr.setPlaceholderText("192.168.70.0/24")
        self.manual_gateway = QLineEdit()
        self.manual_gateway.setPlaceholderText("192.168.70.1")
        self.manual_vlan = QSpinBox()
        self.manual_vlan.setRange(1, 4094)
        self.manual_vlan.setValue(1000)
        self.manual_note = QLineEdit("Aktiv")
        fields = (
            ("Kunde", self.manual_customer), ("Type (valgfri)", self.manual_type),
            ("Subnet", self.manual_cidr), ("Gateway", self.manual_gateway),
            ("VLAN", self.manual_vlan), ("Note", self.manual_note),
        )
        for index, (caption, widget) in enumerate(fields):
            row, column = divmod(index, 3)
            form.addWidget(QLabel(caption), row * 2, column)
            form.addWidget(widget, row * 2 + 1, column)
        self.manual_cidr.editingFinished.connect(self.fill_manual_gateway)
        root.addLayout(form)

        actions = QHBoxLayout()
        save_button = QPushButton("Gem i register")
        save_button.setObjectName("primary")
        save_button.clicked.connect(self.save_manual)
        self.update_manual_button = QPushButton("Opdater valgt")
        self.update_manual_button.setEnabled(False)
        self.update_manual_button.clicked.connect(self.update_manual)
        load_button = QPushButton("Hent valgt til redigering")
        load_button.clicked.connect(self.load_selected)
        clear_button = QPushButton("Ryd felter")
        clear_button.clicked.connect(self.clear_manual)
        actions.addWidget(save_button)
        actions.addWidget(self.update_manual_button)
        actions.addWidget(load_button)
        actions.addWidget(clear_button)
        actions.addStretch()
        root.addLayout(actions)

        self.status = QLabel("Listen er fælles med subnetberegneren og bruges til at undgå genbrug.")
        self.status.setObjectName("muted")
        root.addWidget(self.status)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["ID", "Kunde", "Type", "Subnet", "Gateway", "VLAN", "Note"])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(lambda *_: self.load_selected())
        root.addWidget(self.table, 1)
        self.refresh()

    def fill_manual_gateway(self):
        if self.manual_gateway.text().strip() or not self.manual_cidr.text().strip():
            return
        try:
            network = ipaddress.ip_network(self.manual_cidr.text().strip(), strict=False)
            self.manual_cidr.setText(str(network))
            self.manual_gateway.setText(str(next(network.hosts())))
        except (ValueError, StopIteration):
            return

    def _manual_values(self, exclude_id: int | None = None):
        customer = self.manual_customer.text().strip()
        network_type = self.manual_type.text().strip()
        if not customer:
            raise ValueError("Indtast kundenavnet.")
        used_cidrs, used_vlans = collect_used_networks(exclude_id)
        network = validate_registry_entry(
            self.manual_cidr.text(), self.manual_gateway.text(), self.manual_vlan.value(),
            used_cidrs, used_vlans,
        )
        gateway = str(ipaddress.ip_address(self.manual_gateway.text().strip()))
        note = self.manual_note.text().strip() or "Aktiv"
        return customer, network_type, network, gateway, self.manual_vlan.value(), note

    def save_manual(self):
        try:
            customer, network_type, network, gateway, vlan, note = self._manual_values()
            with db() as conn:
                conn.execute(
                    """INSERT INTO subnet_allocations(
                        customer, purpose, server_count, cidr, mask, gateway,
                        first_server_ip, last_server_ip, broadcast, vlan, note, created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        customer, network_type, 0, str(network), str(network.netmask), gateway,
                        "", "", str(network.broadcast_address), vlan, note,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
        except (ValueError, sqlite3.IntegrityError) as exc:
            QMessageBox.warning(self, "Kan ikke gemme netværket", str(exc))
            return
        self.status.setText(f"{network} og VLAN {vlan} er gemt til {customer}.")
        self.refresh()
        self.clear_manual()
        QMessageBox.information(self, "Gemt i register", "IP- og VLAN-oplysningerne er gemt.")

    def load_selected(self):
        row_index = self.table.currentRow()
        if row_index < 0:
            QMessageBox.information(self, "Vælg en post", "Vælg først en række i registeret.")
            return
        allocation_id = int(self.table.item(row_index, 0).text())
        with db() as conn:
            row = conn.execute("SELECT * FROM subnet_allocations WHERE id=?", (allocation_id,)).fetchone()
        if not row:
            return
        self.editing_id = allocation_id
        self.manual_customer.setText(row["customer"])
        self.manual_type.setText(row["purpose"])
        self.manual_cidr.setText(row["cidr"])
        self.manual_gateway.setText(row["gateway"])
        self.manual_vlan.setValue(int(row["vlan"]))
        self.manual_note.setText(row["note"])
        self.update_manual_button.setEnabled(True)
        self.status.setText("Den valgte post er hentet. Ret felterne og klik på Opdater valgt.")

    def update_manual(self):
        if self.editing_id is None:
            QMessageBox.information(self, "Vælg en post", "Hent først en række fra registeret.")
            return
        try:
            customer, network_type, network, gateway, vlan, note = self._manual_values(self.editing_id)
            with db() as conn:
                conn.execute(
                    """UPDATE subnet_allocations SET
                        customer=?, purpose=?, server_count=0, cidr=?, mask=?, gateway=?,
                        first_server_ip='', last_server_ip='', broadcast=?, vlan=?, note=?
                    WHERE id=?""",
                    (
                        customer, network_type, str(network), str(network.netmask), gateway,
                        str(network.broadcast_address), vlan, note, self.editing_id,
                    ),
                )
        except (ValueError, sqlite3.IntegrityError) as exc:
            QMessageBox.warning(self, "Kan ikke opdatere netværket", str(exc))
            return
        self.status.setText(f"Posten for {customer} er opdateret.")
        self.refresh()
        self.clear_manual()
        QMessageBox.information(self, "Register opdateret", "Ændringerne er gemt.")

    def clear_manual(self):
        self.editing_id = None
        self.manual_customer.clear()
        self.manual_type.clear()
        self.manual_cidr.clear()
        self.manual_gateway.clear()
        self.manual_vlan.setValue(1000)
        self.manual_note.setText("Aktiv")
        self.update_manual_button.setEnabled(False)

    def refresh(self):
        with db() as conn:
            rows = conn.execute("SELECT * FROM subnet_allocations ORDER BY id DESC").fetchall()
        self.table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["id"], row["customer"], row["purpose"], row["cidr"],
                row["gateway"], row["vlan"], row["note"],
            ]
            for column, value in enumerate(values):
                self.table.setItem(row_index, column, QTableWidgetItem(str(value)))


class SavedPage(QWidget):
    def __init__(self):
        super().__init__(); self.on_load=None; l=QVBoxLayout(self); l.setContentsMargins(26,22,26,24); t=QLabel("Gemte planer"); t.setObjectName("title"); l.addWidget(t)
        self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(["ID","Kunde","Oprettet","Design","IOPS","Racks"]); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); self.table.setEditTriggers(QTableWidget.NoEditTriggers); l.addWidget(self.table); self.refresh()
        open_button=QPushButton("Åbn valgt plan til redigering"); open_button.clicked.connect(self.open_selected); l.addWidget(open_button,alignment=Qt.AlignLeft)
    def refresh(self):
        with db() as conn: rows=conn.execute("SELECT * FROM plans ORDER BY id DESC").fetchall()
        self.table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            result=json.loads(row["result_json"]); values=[row["id"],row["customer"],row["created_at"].replace("T"," "),row["profile"],f'{result["delivered_iops"]:,}',result["rack_count"]]
            for j,v in enumerate(values): self.table.setItem(i,j,QTableWidgetItem(str(v)))
    def open_selected(self):
        row=self.table.currentRow()
        if row < 0: QMessageBox.information(self,"Vælg plan","Vælg først en plan i tabellen."); return
        plan_id=int(self.table.item(row,0).text())
        with db() as conn: saved=conn.execute("SELECT * FROM plans WHERE id=?",(plan_id,)).fetchone()
        if saved and self.on_load: self.on_load(saved["customer"],saved["profile"],json.loads(saved["inputs_json"]))


class CatalogPage(QWidget):
    def __init__(self):
        super().__init__(); self.current_xp=0; l=QVBoxLayout(self); l.setContentsMargins(26,22,26,24); t=QLabel("Butik og unlocks"); t.setObjectName("title"); l.addWidget(t)
        self.summary=QLabel(""); self.summary.setObjectName("muted"); l.addWidget(self.summary)
        self.table=QTableWidget(0,11); self.table.setHorizontalHeaderLabels(["Status","Nøgle","Kategori","Navn","IOPS","U","Porte","Gbps","XP-krav","Pris","EOL timer"]); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); l.addWidget(self.table)
        b=QPushButton("Gem katalog"); b.setObjectName("primary"); b.clicked.connect(self.save); l.addWidget(b,alignment=Qt.AlignLeft); self.load()
    def set_xp(self, value): self.current_xp=int(value); self.load()
    def load(self):
        c=load_catalog(CATALOG_PATH)
        fields=list(c.items()); self.table.setRowCount(len(fields)); unlocked=0
        for i,(key,d) in enumerate(fields):
            is_unlocked=self.current_xp >= int(d.get("unlock_xp",0)); unlocked += int(is_unlocked)
            vals=["Oplåst" if is_unlocked else "Låst",key,d.get("category",""),d.get("name",""),d.get("iops",""),d.get("units",""),d.get("downlink_ports",d.get("ports","")),d.get("uplink_gbps",d.get("speed_gbps","")),d.get("unlock_xp",0),d.get("price",0),d.get("eol_hours","")]
            for j,v in enumerate(vals): self.table.setItem(i,j,QTableWidgetItem(str(v)))
            self.table.item(i,0).setFlags(Qt.ItemIsEnabled); self.table.item(i,1).setFlags(Qt.ItemIsEnabled)
        self.summary.setText(f"Ved {self.current_xp:,} XP er {unlocked} af {len(fields)} butiksvarer oplåst. Værdierne kommer fra dine butiksskærmbilleder og kan redigeres.")
    def save(self):
        c=load_catalog(CATALOG_PATH)
        try:
            for i in range(self.table.rowCount()):
                key=self.table.item(i,1).text(); d=c[key]; d["category"]=self.table.item(i,2).text().strip(); d["name"]=self.table.item(i,3).text().strip()
                mappings=((4,"iops"),(5,"units"),(8,"unlock_xp"),(9,"price"),(10,"eol_hours"))
                for col,name in mappings:
                    text=self.table.item(i,col).text().strip()
                    if text: d[name]=int(text)
                    elif name in d: d.pop(name)
                port_text=self.table.item(i,6).text().strip()
                if port_text: d["downlink_ports" if "downlink_ports" in d else "ports"]=int(port_text)
                speed_text=self.table.item(i,7).text().strip()
                if speed_text: d["uplink_gbps" if "uplink_gbps" in d else "speed_gbps"]=int(speed_text)
            save_catalog(CATALOG_PATH,c); self.load(); QMessageBox.information(self,"Gemt","Butikskataloget er opdateret.")
        except ValueError: QMessageBox.warning(self,"Ugyldig værdi","Tal-felterne skal indeholde hele tal.")


class UpdatePage(QWidget):
    def __init__(self):
        super().__init__()
        self.download_url = ""
        settings = load_settings()
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 24)
        root.setSpacing(14)

        title = QLabel("Om og opdateringer")
        title.setObjectName("title")
        root.addWidget(title)
        version = QLabel(f"{APP_NAME} · version {APP_VERSION}")
        version.setObjectName("metric")
        root.addWidget(version)
        explanation = QLabel(
            "Appen kan kontrollere GitHub Releases for en nyere Windows-installation. "
            "Indtast projektets GitHub-repository én gang, fx firma/nis-data-center-planner."
        )
        explanation.setObjectName("muted")
        explanation.setWordWrap(True)
        root.addWidget(explanation)

        form = QFormLayout()
        self.repository = QLineEdit(str(settings.get("github_repository", DEFAULT_GITHUB_REPOSITORY)))
        self.repository.setPlaceholderText("ejer/repository")
        form.addRow("GitHub repository", self.repository)
        root.addLayout(form)

        actions = QHBoxLayout()
        save_button = QPushButton("Gem GitHub-adresse")
        save_button.clicked.connect(self.save_repository)
        check_button = QPushButton("Søg efter opdatering")
        check_button.setObjectName("primary")
        check_button.clicked.connect(self.check_for_update)
        self.download_button = QPushButton("Hent ny version")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.open_download)
        actions.addWidget(save_button)
        actions.addWidget(check_button)
        actions.addWidget(self.download_button)
        actions.addStretch()
        root.addLayout(actions)

        self.status = QLabel("Der er ikke søgt efter opdateringer endnu.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("padding:12px; background:#0f1d31; border:1px solid #28506d; border-radius:7px")
        root.addWidget(self.status)

        data_title = QLabel("Dine data")
        data_title.setStyleSheet("font-size:13pt; font-weight:600; margin-top:10px")
        root.addWidget(data_title)
        data_text = QLabel(
            f"Planer, katalog og IP/VLAN-register gemmes her:\n{DATA_DIR}\n\n"
            "Mappen ligger uden for installationsmappen, så data bevares ved opdatering og afinstallation."
        )
        data_text.setObjectName("muted")
        data_text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        data_text.setWordWrap(True)
        root.addWidget(data_text)
        open_data = QPushButton("Åbn datamappe")
        open_data.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(DATA_DIR))))
        root.addWidget(open_data, alignment=Qt.AlignLeft)
        root.addStretch()

    def save_repository(self):
        repository = self.repository.text().strip()
        settings = load_settings()
        settings["github_repository"] = repository
        save_settings(settings)
        self.status.setText("GitHub-adressen er gemt.")

    def check_for_update(self):
        repository = self.repository.text().strip()
        if not repository:
            QMessageBox.information(
                self, "GitHub mangler",
                "Indtast først GitHub-repository som ejer/repository. Det kan tilføjes, når projektet er oprettet på GitHub.",
            )
            return
        self.status.setText("Søger efter den seneste release …")
        self.download_button.setEnabled(False)
        QApplication.processEvents()
        try:
            release = get_latest_release(repository, APP_VERSION)
        except Exception as exc:
            self.status.setText(f"Kunne ikke kontrollere GitHub: {exc}")
            return
        self.save_repository()
        if not release.is_newer:
            self.download_url = release.release_url
            self.status.setText(f"Du har den nyeste version ({APP_VERSION}). Seneste GitHub-release er {release.version}.")
            return
        self.download_url = release.installer_url or release.release_url
        if release.installer_url:
            self.status.setText(f"Version {release.version} er klar. Klik på Hent ny version for at hente installationsfilen.")
            self.download_button.setText(f"Hent version {release.version}")
        else:
            self.status.setText(f"Version {release.version} er klar, men releasen mangler en Setup.exe. GitHub-siden kan stadig åbnes.")
            self.download_button.setText("Åbn GitHub-release")
        self.download_button.setEnabled(bool(self.download_url))

    def open_download(self):
        if self.download_url:
            QDesktopServices.openUrl(QUrl(self.download_url))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}"); self.resize(1600,980)
        rootw=QWidget(); self.setCentralWidget(rootw); root=QHBoxLayout(rootw); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        side=QFrame(); side.setObjectName("side"); side.setFixedWidth(225); sl=QVBoxLayout(side); sl.setContentsMargins(0,0,0,0)
        brand=QLabel("NIS PLANNER"); brand.setObjectName("brand"); sl.addWidget(brand)
        self.stack=QStackedWidget(); self.saved=SavedPage(); self.planner=PlannerPage(self.saved.refresh); self.registry=NetworkRegistryPage(); self.subnets=SubnetPage(self.registry.refresh); self.catalog=CatalogPage(); self.updates=UpdatePage()
        self.saved.on_load=self.load_plan
        self.planner.xp.valueChanged.connect(self.catalog.set_xp)
        for i,(name,page) in enumerate((("Ny plan",self.planner),("Subnetberegner",self.subnets),("IP/VLAN-register",self.registry),("Gemte planer",self.saved),("Butik og unlocks",self.catalog),("Om og opdateringer",self.updates))):
            b=QPushButton("  "+name); b.clicked.connect(lambda _,x=i:self.stack.setCurrentIndex(x)); sl.addWidget(b); self.stack.addWidget(page)
        sl.addStretch(); v=QLabel(f"v{APP_VERSION} · Windows app"); v.setObjectName("muted"); v.setContentsMargins(15,0,0,15); sl.addWidget(v)
        root.addWidget(side); root.addWidget(self.stack,1)
    def load_plan(self, customer, profile, inputs):
        self.planner.load_saved(customer,profile,inputs)
        self.stack.setCurrentWidget(self.planner)


def main():
    initialize_user_data(); init_db(); load_catalog(CATALOG_PATH); app=QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setApplicationVersion(APP_VERSION); app.setOrganizationName("NIS"); app.setStyleSheet(STYLE); w=MainWindow(); w.show(); sys.exit(app.exec())


def package_self_test(output_dir: Path) -> None:
    """Internal build verification used after creating the Windows executable."""
    output_dir.mkdir(parents=True, exist_ok=True)
    initialize_user_data()
    init_db()
    catalog = load_catalog(CATALOG_PATH)
    hardware = build_plan(
        "Package Test", {"System X": 30000, "RISC": 0, "Mainframe": 0, "GPU": 0},
        "Balanceret", False, False, False, catalog, 0, True,
    )
    network = build_network_plan(
        "Package Test", {"System X": hardware.server_count},
        {"System X": {"cidr": "10.20.30.0/24", "vlan": 200}},
        firewall=False, internet=False,
    )
    pdf_path = output_dir / "package_self_test.pdf"
    export_network_pdf(network, pdf_path)
    result = {
        "version": APP_VERSION,
        "server_count": hardware.server_count,
        "pdf_created": pdf_path.exists() and pdf_path.stat().st_size > 0,
        "data_directory": str(DATA_DIR),
    }
    (output_dir / "package_self_test.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
    )


if __name__ == "__main__":
    self_test_environment = os.environ.get("NIS_PACKAGE_SELF_TEST_DIR", "").strip()
    if "--package-self-test" in sys.argv or self_test_environment:
        argument_index = sys.argv.index("--package-self-test") if "--package-self-test" in sys.argv else -1
        target = Path(self_test_environment) if self_test_environment else (
            Path(sys.argv[argument_index + 1]) if len(sys.argv) > argument_index + 1 else DATA_DIR / "self-test"
        )
        try:
            package_self_test(target)
        except Exception:
            target.mkdir(parents=True, exist_ok=True)
            (target / "package_self_test_error.txt").write_text(traceback.format_exc(), encoding="utf-8")
            raise
    else:
        main()
