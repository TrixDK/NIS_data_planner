
# NIS Data Center Planner v1.5.0

Planlægningsværktøj til spillet **Data Center 1.1.x**.

## Nyheder i v1.5 - rigtig Windows-app

- Leveres som en almindelig Windows-installationsfil og kræver ikke Python hos brugeren.
- Opretter genvej i Start-menuen og kan valgfrit oprette en skrivebordsgenvej.
- Gemmer database, hardwarekatalog og indstillinger sikkert i brugerens lokale appdata-mappe.
- Ny side **Om og opdateringer**, som kan kontrollere den seneste GitHub Release.
- Git-repository, automatisk Windows-build og GitHub Release-workflow er inkluderet.
- Subnetberegneren og det selvstændige IP/VLAN-register fra v1.4.1 er bevaret.

## Installation

1. Hent `NIS_Data_Center_Planner_Setup_v1.5.0.exe`.
2. Dobbeltklik på filen og følg installationsguiden.
3. Start **NIS Data Center Planner** fra Start-menuen.

Programdata ligger i `%LOCALAPPDATA%\NIS Data Center Planner`. Du kan åbne mappen
direkte fra siden **Om og opdateringer**. En opdatering eller afinstallation sletter ikke
automatisk dine gemte kunder, planer eller IP/VLAN-poster.

Windows kan vise en SmartScreen-advarsel, fordi installationsfilen ikke er signeret med et
betalt code-signing-certifikat. Kontrollér filens SHA-256-værdi mod den medfølgende checksum.

### GitHub-opdateringer

Angiv repository som `ejer/repository` eller en fuld GitHub-adresse under **Om og
opdateringer**. Appen finder derefter den nyeste publicerede Release og tilbyder link til
den nye Setup-fil. Se `BUILDING.md` for build- og releaseforløbet.

## Rettelse i v1.4.1 - registeret er nu sin egen side

- **Subnetberegner** og **IP/VLAN-register** er nu to separate menupunkter.
- IP/VLAN-registeret spørger ikke om antal servere eller serverudstyr.
- Registeret bruger kun Kunde, valgfri Type, Subnet, Gateway, VLAN og Note.
- Type er et valgfrit tekstfelt og kan stå tomt.
- Subnetberegnerens forslag kan stadig sendes direkte til det fælles register.

## Nyheder i v1.4 - IP- og VLAN-register

- Subnetsiden er udvidet til et egentligt register med kolonnerne **Kunde, Type, Subnet, Gateway, VLAN og Note**.
- Programmets automatiske subnetforslag kan fortsat reserveres direkte til kunden.
- Eksisterende netværk fra spillet kan tilføjes manuelt.
- Type kan vælges som System X, RISC, Mainframe, GPU, Infrastruktur eller Management, og der kan også skrives en valgfri type.
- Gateway udfyldes automatisk med første brugbare adresse, når der indtastes et subnet.
- Gemte poster kan hentes, rettes og opdateres.
- Overlappende subnet, optagne VLAN, ugyldige gateways og dubletter afvises.
- Alle gemte poster indgår automatisk, når næste ledige subnet og VLAN findes.

## Nyheder i v1.3 - selvstændigt subnetregister

- Ny side: **Subnet og VLAN**.
- Indtast kunde og antal servere, og få næste ledige subnet og VLAN foreslået.
- Der regnes automatisk plads til både gateway, alle servere, netværksadresse og broadcast.
- Forslaget viser CIDR, subnetmaske, gateway, server-IP-interval, broadcast og resterende adresser.
- Reservér forslaget til kunden, så subnet og VLAN ikke foreslås igen.
- Alle reservationer vises i en oversigt direkte i programmet.
- Gemte kundeplaners kendte CIDR- og VLAN-værdier springes også over.
- Opsætningen kan kopieres direkte til udklipsholderen.

Eksempel med 6 servere: Programmet vælger et `/28`, fordi et `/29` kun har seks brugbare
adresser og derfor ikke har plads til både gateway og seks servere.

### Behold data fra v1.2 eller v1.3

Hvis du allerede har gemte planer eller subnetreservationer i en ældre version, skal programmet
være lukket, mens du kopierer `nis_planner_v1.db` fra den gamle mappe til v1.4-mappen. v1.4
opdaterer selv registeret med det nye Note-felt, når programmet starter. Ved en helt frisk
installation oprettes databasen automatisk.

## Nyheder i v1.0

- Indtast IOPS pr. System X, RISC, Mainframe og GPU.
- Vælg økonomisk, balanceret eller redundant design.
- Automatisk servermix med 5.000/12.000 IOPS-klasser.
- Komplet indkøbsliste med servere, rackskabe, switches, patchpaneler og kabler.
- Rack-for-rack plan med brugte og ledige U.
- Beregning af serverforbindelser, switchporte, uplinks og nødvendig båndbredde.
- Router og firewall medregnes både i indkøbslisten og rackforbruget.
- Redigerbart hardwarekatalog i programmet.
- Planer gemmes i en separat `nis_planner_v1.db` database.
- Gemte planer kan åbnes, redigeres, genberegnes og gemmes som en ny revision.

Originaldatabasen `nis_operations.db` bevares urørt og bruges ikke af v1.

## Beregningsforudsætninger

- Rack: 47U.
- Lille server: 5.000 IOPS og 3U.
- Stor server: 12.000 IOPS og 7U.
- 20.000 IOPS svarer til cirka 1 Gbps trafik.
- Balanceret design reserverer 10 % ekstra IOPS.
- Redundant design reserverer 15 % og giver hver server to switchforbindelser.

Alle hardwareværdier kan ændres under **Hardwarekatalog** uden at omskrive programmet.

## Nyheder i v1.1 – XP og hele butikken

- Indtast din aktuelle XP på den nye plan.
- **Brug kun oplåst udstyr** er slået til som standard.
- Ved et nyt spil og 0 XP bruges kun System X 3U 5.000 IOPS-serveren.
- Låste serverfamilier, routere og firewalls giver en klar besked med nødvendigt XP-niveau.
- Indkøbslisten viser stykpris, totalpris og XP-krav.
- Siden **Butik og unlocks** indeholder hele det butikssortiment, der fremgår af de fire skærmbilleder:
  servere, fire switches, router, firewall, racks, tre patchpaneler, otte kabler og fire SFP-modulpakker.
- Butikssiden markerer oplåste/låste varer ud fra samme XP-felt som planlæggeren.

Kabelprisen er registreret som prisen for kabelrullen i butikken. Værktøjet viser samtidig det
beregnede antal kabelføringer, men ganger ikke rulleprisen med antallet af forbindelser.

### Server-unlocks

| Familie | 5.000 IOPS | 12.000 IOPS |
|---|---:|---:|
| System X | 0 XP | 2.200 XP |
| RISC | 100 XP | 3.000 XP |
| Mainframe | 480 XP | 6.500 XP |
| GPU | 350 XP | 5.500 XP |

## Nyheder i v1.2 - netværks- og firewallguide

- Ny indstilling: **Subnet/IP-plan**.
- Indtast Customer CIDR og Customer VLAN direkte fra kundepanelet for hver aktiv App.
- Automatisk custom subnet, maske, gateway, VLAN og unik IP til hver server.
- Fast og genkendelig navngivning af router, firewall og servere.
- Routerguide med felterne fra spillets `Subnet/VLAN Creation` og `Routes`.
- Firewallguide med regelrækkefølge, source, destination, port, protocol, bi-directional og action.
- Kabelguide for Customer closet, router, server-switches, DMZ, ISP og firewall.
- Kontroltjekliste til spillets Service Request-evaluator.
- Hent hele kundens guide som en formateret PDF.

App-rækkefølgen bruges sådan:

| App | Serverfamilie |
|---:|---|
| 0 | System X |
| 1 | RISC |
| 2 | Mainframe |
| 3 | GPU |

Customer CIDR og Customer VLAN skal aflæses i den aktuelle save. De kan ikke udledes sikkert
af kundenavnet alene. Ved Internet/Firewall føres DMZ/ISP gennem firewallen til routeren, mens
Customer closet fortsat forbindes direkte til routeren.

---

## Historik fra v0.6.x

## Vigtig ændring

Netværk ligger nu pr. serverfamilie/app — ikke kun pr. kunde.

En kunde kan derfor have:

- System X med eget subnet, gateway, maske og VLAN
- RISC med eget subnet, gateway, maske og VLAN
- Mainframe med eget subnet, gateway, maske og VLAN
- GPU med eget subnet, gateway, maske og VLAN

Eksempel:

System X:
- Krav: 100.000 IOPS
- Gateway: 10.2.13.1
- Maske: 255.255.255.224 (/27)
- VLAN: 182

RISC:
- Krav: 50.000 IOPS
- Gateway: 10.2.14.1
- Maske: 255.255.255.240 (/28)
- VLAN: 183

Hver familie får automatisk sin egen IP-liste.

## Installation

1. Pak ZIP-filen ud i en ny mappe.
2. Kør `install.bat`.
3. Kør `run.bat`.

v0.6 bruger en ændret databasestruktur. Start derfor med databasen i v0.6-mappen.


## Hotfix v0.6.1

Rettet en fejl, hvor knappen `Opret kunde` ikke åbnede dialogen.

Årsag:
- VLAN blev flyttet fra kundeniveau til serverfamilie/app-niveau i v0.6.
- Dialogen forsøgte stadig at finde næste VLAN i den gamle customer-tabel.

Rettelse:
- Næste VLAN læses nu korrekt fra workload/app-netværkene.

## Hotfix v0.6.2

Rettet fejlen `no such column: subnet`.

Årsagen var ikke, at subnet-feltet manglede i databasen. Subnet, prefix, maske, gateway og VLAN ligger korrekt i tabellen `workloads`, fordi hvert servermiljø/app-netværk har sine egne netværksdata. En gammel forespørgsel søgte stadig efter subnet i tabellen `customers`.

Derudover er de interne plan-objekter rettet, så hver serverfamilie kan gemme sit eget subnet, gateway, maske, VLAN og IP-liste.
