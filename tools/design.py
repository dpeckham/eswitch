"""Circuit definition for the eswitch board: parts, nets, and schematic placement.

Coordinates are schematic sheet millimetres (A2 sheet, 594 x 420). All symbol origins
sit on the 1.27 mm grid so that library pin ends land on grid too.
"""
from dataclasses import dataclass, field

N_CH = 8
GRID = 1.27

# Per-channel rating -> PROFET variant (all PG-TSDSO-14, identical pinout) and sense resistor.
# CH8 (last cell, far from the stud) is the 20 A channel: it gets extra inner-layer copper.
CHANNELS = {
    1: (10, "BTS7004-1EPP", "2.2k 1%"),
    2: (10, "BTS7004-1EPP", "2.2k 1%"),
    3: (5, "BTS7008-1EPR", "3.3k 1%"),
    4: (5, "BTS7008-1EPR", "3.3k 1%"),
    5: (5, "BTS7008-1EPR", "3.3k 1%"),
    6: (5, "BTS7008-1EPR", "3.3k 1%"),
    7: (5, "BTS7008-1EPR", "3.3k 1%"),
    8: (20, "BTS7002-1EPP", "1.2k 1%"),
}
PROFET_MPN = {"BTS7002-1EPP": "BTS70021EPPXUMA1", "BTS7004-1EPP": "BTS70041EPPXUMA1",
              "BTS7008-1EPR": "BTS70081EPRXUMA1"}
OUTPUT_REFS = ["J1", "J6", "J7", "J8", "J9", "J10", "J11", "J12"]
OUTPUT_FOOTPRINT = "eswitch:TerminalBlock_1x02_P7.62mm_Wuerth_2184"
INPUT_FOOTPRINT = "eswitch:ScrewTerminal_Wuerth_74650195_M5"
BUILD_QUANTITY = 3
CONTINUOUS_TOTAL_TARGET_A = 40
ASSEMBLY_METHOD = "Manual; paste and hot air/hot plate for exposed pads; iron for THT"


def g(v):
    """Snap to the 1.27 mm schematic grid."""
    return round(round(v / GRID) * GRID, 4)


@dataclass
class Part:
    ref: str
    lib_id: str            # "Lib:Symbol" (standard KiCad library or "eswitch:...")
    value: str
    footprint: str
    pins: dict             # pin number -> net name
    at: tuple = (0.0, 0.0)  # sheet position
    rot: int = 0
    fields: dict = field(default_factory=dict)  # extra properties (MPN, Note, ...)
    hidden_pins_connected: bool = False


PARTS: list[Part] = []


def add(ref, lib_id, value, footprint, pins, at, rot=0, **fields):
    p = Part(ref, lib_id, value, footprint, {str(k): v for k, v in pins.items()},
             (g(at[0]), g(at[1])), rot, fields)
    PARTS.append(p)
    return p


# Footprint shorthands
R0603 = "Resistor_SMD:R_0603_1608Metric"
R0805 = "Resistor_SMD:R_0805_2012Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C1210 = "Capacitor_SMD:C_1210_3225Metric"
LED0603 = "LED_SMD:LED_0603_1608Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
SOT236 = "Package_TO_SOT_SMD:SOT-23-6"
SMA = "Diode_SMD:D_SMA"
SMB = "Diode_SMD:D_SMB"

# ESP32-S3-WROOM-1 module pin numbers used
ESP_IS = ["39", "15", "4", "38", "6", "18", "12", "17"]      # IO1 IO3 IO4 IO2 IO6 IO10 IO8 IO9 (all ADC1)
ESP_IN = ["7", "19", "20", "21", "22", "23", "24", "25"]     # IO7 IO11 IO12 IO13 IO14 IO21 IO47 IO48
ESP_DEN = "31"     # IO38
ESP_STAT = "34"    # IO41
ESP_IO_NAMES = {"39": "IO1", "15": "IO3", "4": "IO4", "38": "IO2", "6": "IO6", "7": "IO7", "12": "IO8",
                "17": "IO9", "18": "IO10", "19": "IO11", "20": "IO12", "21": "IO13", "22": "IO14",
                "23": "IO21", "24": "IO47", "25": "IO48", "31": "IO38", "34": "IO41"}


def build():
    PARTS.clear()
    # ------------------------------------------------------------------ channels
    for n in range(1, N_CH + 1):
        c, r = (n - 1) % 4, (n - 1) // 4
        bx, by = 12.7 + c * 72.39, 22.86 + r * 82.55
        VS, LOAD, IN, INR, DENR = f"VS{n}", f"LOAD{n}", f"IN{n}", f"INR{n}", f"DENR{n}"
        ISP, IS, UGND, LEDK = f"ISP{n}", f"IS{n}", f"UGND{n}", f"LEDK{n}"
        rating, profet, rsense = CHANNELS[n]
        add(f"F{n}", "eswitch:FuseHolder_ATO_3pos", f"ATO {rating}A",
            "eswitch:Fuseholder_ATO_3pos_Keystone_3557",
            {1: VS, 2: "+12V", 3: LOAD}, (bx + 12.7, by + 12.7),
            MPN="Keystone 3557 (x3)", Note=f"CH{n} {rating} A; AUTO: fuse in COM-SW; BYPASS: fuse in COM-LOAD")
        add(f"U{n}", f"eswitch:{profet}", profet, "Package_SO:Infineon_PG-TSDSO-14-22",
            {1: UGND, 2: INR, 3: DENR, 4: ISP, 8: LOAD, 15: VS}, (bx + 50.8, by + 12.7),
            MPN=PROFET_MPN[profet], Note=f"CH{n} {rating} A")
        row2 = by + 35.56
        xs = [bx + 5.08 + i * 10.16 for i in range(6)]
        add(f"R{n}01", "Device:R", "4.7k", R0603, {1: IN, 2: INR}, (xs[0], row2), Note="RIN")
        add(f"R{n}02", "Device:R", "4.7k", R0603, {1: "DEN", 2: DENR}, (xs[1], row2), Note="RDEN")
        add(f"R{n}03", "Device:R", "47R", R0805, {1: UGND, 2: "GND"}, (xs[2], row2), Note="RGND (ReverseON)")
        add(f"R{n}04", "Device:R", rsense, R0603, {1: ISP, 2: "GND"}, (xs[3], row2), Note="RSENSE")
        add(f"R{n}05", "Device:R", "4.7k", R0603, {1: ISP, 2: IS}, (xs[4], row2), Note="RADC")
        add(f"C{n}03", "Device:C", "220pF 50V", C0603, {1: IS, 2: "GND"}, (xs[5], row2), Note="CSENSE")
        row3 = by + 58.42
        add(f"D{n}01", "Diode:BAT54S", "BAT54S", SOT23, {1: "GND", 2: "+3V3", 3: IS},
            (bx + 10.16, row3), Note="ADC clamp")
        add(f"C{n}01", "Device:C", "100nF 50V", C0805, {1: VS, 2: "GND"}, (bx + 25.4, row3), Note="CVS")
        add(f"R{n}06", "Device:R", "47k", R0603, {1: LOAD, 2: "GND"}, (bx + 35.56, row3), Note="RPD")
        add(f"C{n}02", "Device:C", "10nF 50V", C0805, {1: LOAD, 2: "GND"}, (bx + 45.72, row3), Note="COUT")
        add(f"R{n}07", "Device:R", "10k", R0603, {1: LOAD, 2: LEDK}, (bx + 55.88, row3),
            Note="RLED; <=78.4 mW at 28 V even with LED shorted")
        add(f"D{n}02", "Device:LED", "GREEN", LED0603, {1: "GND", 2: LEDK}, (bx + 66.04, row3), rot=90,
            Note="load ON indicator")

    # ------------------------------------------------------------------ MCU
    mx, my = 381.0, 80.01
    esp_pins = {"1": "GND", "40": "GND", "41": "GND", "2": "+3V3", "3": "EN", "27": "IO0",
                "13": "USB_D-", "14": "USB_D+", "37": "TXD0", "36": "RXD0", ESP_DEN: "DEN", ESP_STAT: "STAT"}
    for i in range(N_CH):
        esp_pins[ESP_IS[i]] = f"IS{i + 1}"
        esp_pins[ESP_IN[i]] = f"IN{i + 1}"
    add("U10", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1-N8", "RF_Module:ESP32-S3-WROOM-1",
        esp_pins, (mx, my), MPN="ESP32-S3-WROOM-1-N8")
    yr = my + 45.72
    xs = [335.28 + i * 10.16 for i in range(9)]
    add("C9", "Device:C", "10uF 10V", C0805, {1: "+3V3", 2: "GND"}, (xs[0], yr))
    add("C10", "Device:C", "100nF", C0603, {1: "+3V3", 2: "GND"}, (xs[1], yr))
    add("R5", "Device:R", "10k", R0603, {1: "+3V3", 2: "EN"}, (xs[2], yr))
    add("C11", "Device:C", "1uF", C0603, {1: "EN", 2: "GND"}, (xs[3], yr))
    add("SW1", "Switch:SW_Push", "RESET", "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92",
        {1: "GND", 2: "EN"}, (xs[4], yr), rot=90, MPN="PTS645SM43SMTR92")
    add("R6", "Device:R", "10k", R0603, {1: "+3V3", 2: "IO0"}, (xs[5], yr))
    add("SW2", "Switch:SW_Push", "BOOT", "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92",
        {1: "GND", 2: "IO0"}, (xs[6], yr), rot=90, MPN="PTS645SM43SMTR92")
    add("R9", "Device:R", "1k", R0603, {1: "STAT", 2: "STATK"}, (xs[7], yr))
    add("D5", "Device:LED", "BLUE", LED0603, {1: "GND", 2: "STATK"}, (xs[8], yr), rot=90, Note="status LED IO41")
    # USB
    add("J4", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C", 
        "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
        {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "SH": "GND",
         "A4": "VBUS", "A9": "VBUS", "B4": "VBUS", "B9": "VBUS", "A5": "CC1", "B5": "CC2",
         "A6": "USB_D+", "B6": "USB_D+", "A7": "USB_D-", "B7": "USB_D-"},
        (340.36, 176.53), MPN="GCT USB4105-GF-A")
    add("U11", "Power_Protection:SRV05-4", "SRV05-4HTG-D", SOT236,
        {1: "USB_D+", 6: "USB_D+", 3: "USB_D-", 4: "USB_D-", 2: "GND", 5: "VBUS"}, (391.16, 165.1),
        MPN="SRV05-4HTG-D", Manufacturer="Littelfuse",
        Datasheet="https://www.littelfuse.com/assetdocs/littelfuse-tvs-diode-array-srv05-4htg-d-datasheet?assetguid=d716fc4c-0484-4b67-97d8-cf719554d89a",
        Note="Four independent steering channels; pair 1+6 and 3+4 externally; pin 2 GND, pin 5 VBUS; placement review open")
    add("R7", "Device:R", "5.1k", R0603, {1: "CC1", 2: "GND"}, (411.48, 176.53))
    add("R8", "Device:R", "5.1k", R0603, {1: "CC2", 2: "GND"}, (421.64, 176.53))
    add("J5", "Connector_Generic:Conn_01x04", "UART", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
        {1: "GND", 2: "+3V3", 3: "TXD0", 4: "RXD0"}, (436.88, 80.01), Note="GND 3V3 TX RX")

    # ------------------------------------------------------------------ power
    yr = 240.03
    xs = [335.28 + i * 10.16 for i in range(7)]
    add("F9", "Device:Fuse", "2A 1206", "Fuse:Fuse_1206_3216Metric", {1: "+12V", 2: "V12F"}, (xs[0], yr),
        MPN="Littelfuse 0466002.NR", Note="logic supply fuse")
    add("D1", "Device:D_Schottky", "B360A", SMA, {2: "V12F", 1: "VIN"}, (xs[1], yr), rot=90, Note="12V -> VIN")
    add("D2", "Device:D_Schottky", "B360A", SMA, {2: "VBUS", 1: "VIN"}, (xs[2], yr), rot=90, Note="USB -> VIN; low-VBUS margin unresolved")
    add("D3", "Device:D_Zener", "SMBJ26A", SMB, {1: "+12V", 2: "GND"}, (xs[3], yr), rot=270, Note="bus TVS")
    add("C1", "Device:C", "4.7uF 50V", C1210, {1: "VIN", 2: "GND"}, (xs[4], yr))
    add("C2", "Device:C", "4.7uF 50V", C1210, {1: "VIN", 2: "GND"}, (xs[5], yr))
    add("C3", "Device:C", "100nF 50V", C0603, {1: "VIN", 2: "GND"}, (xs[6], yr))
    yr = 274.32
    add("U9", "Regulator_Switching:TPS54360DDA", "TPS54360B", "Package_SO:TI_SO-PowerPAD-8_ThermalVias",
        {1: "BOOT", 2: "VIN", 4: "RT", 5: "FB", 6: "COMP", 7: "GND", 8: "SW", 9: "GND"}, (350.52, yr),
        MPN="TPS54360BDDAR")
    xs = [383.54 + i * 10.16 for i in range(5)]
    add("R1", "Device:R", "200k 1%", R0603, {1: "RT", 2: "GND"}, (xs[0], yr), Note="fsw 500 kHz")
    add("C4", "Device:C", "100nF 25V", C0603, {1: "BOOT", 2: "SW"}, (xs[1], yr))
    add("R4", "Device:R", "3.9k", R0603, {1: "COMP", 2: "COMPZ"}, (xs[2], yr))
    add("C5", "Device:C", "27nF", C0603, {1: "COMPZ", 2: "GND"}, (xs[3], yr))
    add("C6", "Device:C", "150pF", C0603, {1: "COMP", 2: "GND"}, (xs[4], yr))
    yr = 299.72
    add("L1", "Device:L", "10uH 4A", "Inductor_SMD:L_Bourns_SRP7028A_7.3x6.6mm", {1: "SW", 2: "+3V3"},
        (340.36, yr), rot=90, MPN="Bourns SRP7028A-100M")
    add("D4", "Device:D_Schottky", "B360A", SMA, {1: "SW", 2: "GND"}, (355.6, yr), rot=270, Note="catch diode")
    add("R2", "Device:R", "31.6k 1%", R0603, {1: "+3V3", 2: "FB"}, (365.76, yr))
    add("R3", "Device:R", "10.2k 1%", R0603, {1: "FB", 2: "GND"}, (375.92, yr))
    add("C7", "Device:C", "47uF 6.3V X7R", C1210, {1: "+3V3", 2: "GND"}, (386.08, yr))
    add("C8", "Device:C", "47uF 6.3V X7R", C1210, {1: "+3V3", 2: "GND"}, (396.24, yr))

    # ------------------------------------------------------------------ I/O, mechanical, flags
    for n in range(1, N_CH + 1):
        col, row = (n - 1) % 4, (n - 1) // 4
        add(OUTPUT_REFS[n - 1], "Connector:Screw_Terminal_01x02", "691218410002", OUTPUT_FOOTPRINT,
            {1: "GND", 2: f"LOAD{n}"}, (340.36 + 30.48 * col, 373.38 + 15.24 * row),
            MPN="691218410002", Datasheet="https://www.we-online.com/components/products/datasheet/691218410002.pdf",
            Note=f"CH{n}: pin 1 GND, pin 2 LOAD+; direct-entry screw clamp; 30 A per pole; 24-10 AWG")
    for ref, net, y in (("J2", "+12V", 340.36), ("J3", "GND", 350.52)):
        add(ref, "Connector:Screw_Terminal_01x01", net + " IN", INPUT_FOOTPRINT,
            {1: net}, (386.08, y), MPN="74650195", Manufacturer="Wurth Elektronik",
            Datasheet="https://www.we-online.com/components/products/datasheet/74650195.pdf",
            Note="M5 ring-lug terminal, 85 A at 20 C component rating; PCB/wire/ambient limit applies; screw not included")
    for i in range(4):
        add(f"H{i + 1}", "Mechanical:MountingHole", "M3", "MountingHole:MountingHole_3.2mm_M3", {},
            (406.4 + i * 10.16, 340.36))
    for i, net in enumerate(["+12V", "GND", "VBUS", "VIN", "+3V3"]):
        add(f"#FLG{i + 1}", "power:PWR_FLAG", "PWR_FLAG", "", {1: net}, (406.4 + i * 10.16, 358.14))
    apply_revision_b()
    from revision_c import apply as apply_revision_c
    apply_revision_c(PARTS, add)
    apply_part_numbers()
    return PARTS


def apply_revision_b():
    """Protected 9.5–16 V input and USB-capable logic supply.

    Keep reference designators stable where a part retains its function. Removed
    discrete buck parts are intentionally not reused for unrelated functions.
    """
    removed = {"D2", "D4", "L1", "C4", "C5", "C6", "R2", "R3", "R4", "#FLG5"}
    PARTS[:] = [p for p in PARTS if p.ref not in removed]
    parts = {p.ref: p for p in PARTS}
    parts["U10"].footprint = "eswitch:ESP32-S3-WROOM-1_Edge"
    parts["J2"].pins["1"] = "BATT_RAW"
    parts["J2"].value = "BATT+ 9.5-16V"
    parts["D3"].value = "SMCJ24CA"
    parts["D3"].footprint = "Diode_SMD:D_SMC"
    parts["D3"].pins = {"1": "BATT_RAW", "2": "GND"}
    parts["D3"].fields = dict(MPN="SMCJ24CA", Manufacturer="Littelfuse",
                              Note="Bidirectional input clamp; upstream fuse required")
    parts["U9"].lib_id = "eswitch:TPSM63603V3"
    parts["U9"].value = "TPSM63603V3"
    parts["U9"].footprint = "eswitch:TI_RDH0030A_TPSM63603"
    parts["U9"].pins = {str(p): "VIN" for p in (2, 3, 4, 18, 19)}
    parts["U9"].pins.update({str(p): "GND" for p in (5, 6, 16, 17, 28, 29)})
    parts["U9"].pins.update({str(p): "+3V3" for p in (7, 8, 9, 10, 12, 13, 14, 15, 22, 25, 30)})
    parts["U9"].pins.update({"1": "RT", "23": "VCC_BUCK", "24": "AGND_BUCK", "27": "AGND_BUCK"})
    parts["U9"].fields = dict(MPN="TPSM63603V3RDHR", Manufacturer="Texas Instruments",
        Datasheet="https://www.ti.com/lit/ds/symlink/tpsm63603.pdf",
        Note="3.3 V fixed module, 800 kHz; startup requires VIN >=3.95 V; internal inductor/compensation")
    parts["R1"].value = "16.5k 1%"
    parts["R1"].pins["2"] = "AGND_BUCK"
    parts["R1"].fields = dict(Note="800 kHz per TPSM63603 table 7-4")
    # Four 47 uF X7R parts; exact bias/temperature model and engineering reserve
    # are checked by buck_analysis.py. Bench stability/startup still need testing.
    for ref, x in (("C12", 416.56), ("C13", 426.72)):
        add(ref, "Device:C", "47uF 6.3V X7R", C1210, {1: "+3V3", 2: "GND"}, (x, 299.72))
    add("C14", "Device:C", "1uF", C0603, {1: "VCC_BUCK", 2: "GND"}, (405.13, 274.32))
    add("NT1", "Device:NetTie_2", "AGND STAR", "NetTie:NetTie-2_SMD_Pad0.5mm",
        {1: "AGND_BUCK", 2: "GND"}, (426.72, 274.32),
        Note="Copper-only local AGND/PGND star at U9; no purchased component")
    # USB data series resistors near the MCU; connector side remains USB_D+/-.
    parts["U10"].pins["13"] = "USB_MCU_D-"
    parts["U10"].pins["14"] = "USB_MCU_D+"
    for ref, sign, x in (("R10", "+", 447.04), ("R11", "-", 462.28)):
        add(ref, "Device:R", "22R", R0603,
            {1: "USB_D" + sign, 2: "USB_MCU_D" + sign}, (x, 176.53))
    parts["U11"].fields["Note"] = "ESD at USB connector; pair 1+6 and 3+4; pin 2 GND, pin 5 VBUS"
    # Reverse-blocking ideal diode. The separate TPS2492 pass stage below provides
    # current/power limiting and hardware latch-off, including BYPASS startup.
    fet_fp = "Package_SON:Infineon_PG-TDSON-8_6.15x5.15mm"
    fet_fields = dict(MPN="BSC016N06NSATMA1", Manufacturer="Infineon",
        Datasheet="https://www.infineon.com/assets/row/public/documents/24/49/infineon-bsc016n06ns-datasheet-en.pdf",
        Note="Drain-down NS package; do NOT substitute source-down NSSC variant")
    for ref, source, gate, xy in (
        ("Q1", "BATT_RAW", "DGATE_MAIN", (25.4, 238.76)),
        ("Q2", "BATT_RAW", "DGATE_MAIN", (76.2, 238.76)),
        ("Q5", "VBUS", "DGATE_USB", (254.0, 238.76)),
    ):
        drain = "VIN" if ref == "Q5" else "BATT_MID"
        add(ref, "eswitch:BSC016N06NS", "BSC016N06NS", fet_fp,
            {1: source, 2: source, 3: source, 4: gate, 5: drain},
            xy, **fet_fields)
    controller_fp = "Package_SON:WSON-12-1EP_3x3mm_P0.5mm_EP1.5x2.5mm"
    ctrl_fields = dict(MPN="LM74800QDRRRQ1", Manufacturer="Texas Instruments",
                       Datasheet="https://www.ti.com/lit/ds/symlink/lm7480-q1.pdf")
    add("U12", "eswitch:LM74800", "LM74800-Q1", controller_fp,
        {1: "DGATE_MAIN", 2: "BATT_RAW", 3: "BATT_MID", 4: "BATT_MID", 5: "GND",
         6: "BATT_RAW", 7: "GND", 9: "BATT_MID", 10: "BATT_MID",
         11: "CAP_MAIN", 12: "BATT_MID"}, (63.5, 279.4),
        Note="Main ideal-diode reverse block only; HGATE unused; exposed pad FLOATING", **ctrl_fields)
    for ref, gate, x in (("Q3", "GATE_Q3", 127.0), ("Q4", "GATE_Q4", 177.8)):
        add(ref, "eswitch:PSMN1R8-80SSE", "PSMN1R8-80SSE", "Package_TO_SOT_SMD:LFPAK88",
            {1: gate, 2: "+12V", 3: "+12V", 4: "+12V", 5: "BATT_SENSE"}, (x, 238.76),
            MPN="PSMN1R8-80SSEJ", Manufacturer="Nexperia",
            Datasheet="https://assets.nexperia.com/documents/data-sheet/PSMN1R8-80SSE.pdf",
            Note="Enhanced-SOA pass FET; evaluate ONE device taking all linear startup stress")
    add("U14", "eswitch:TPS2492", "TPS2492 (LATCH)", "Package_SO:TSSOP-14_4.4x5mm_P0.65mm",
        {1: "UV_MAIN", 2: "HS_REF", 3: "HS_PROG", 4: "HS_TIMER", 5: "OV_MAIN",
         7: "GND", 11: "+12V", 12: "HGATE_MAIN", 13: "HS_SENSE", 14: "HS_VCC"},
        (127, 279.4), MPN="TPS2492PWR", Manufacturer="Texas Instruments",
        Datasheet="https://www.ti.com/lit/ds/symlink/tps2492.pdf",
        Note="Hardware current/power limiter; timer fault latches until input UV/power cycle; NOT TPS2493")
    add("R20", "eswitch:Kelvin_Shunt", "1mR 1% 4W", "eswitch:Bourns_CSS4J_4026",
        {1: "BATT_MID", 2: "BATT_SENSE", 3: "HS_VCC", 4: "HS_SENSE"}, (177.8, 279.4),
        MPN="CSS4J-4026R-1L00F", Manufacturer="Bourns",
        Datasheet="https://bourns.com/docs/product-datasheets/css4j-4026.pdf",
        Note="Four-terminal shunt; 50 A nominal limit; dedicated sense leads; use conservative 4 W inventory rating")
    # Reuse the same available controller for the USB ideal diode. HGATE is unused;
    # OUT/VS/C sense the cathode, EN follows USB input, OV is disabled at GND.
    add("U13", "eswitch:LM74800", "LM74800-Q1", controller_fp,
        {1: "DGATE_USB", 2: "VBUS", 3: "VIN", 4: "VIN", 5: "GND", 6: "VBUS",
         7: "GND", 9: "VIN", 10: "VIN", 11: "CAP_USB", 12: "VIN"}, (228.6, 279.4),
        Note="USB ideal diode; no return current into host; exposed pad FLOATING", **ctrl_fields)
    for ref, value, pins, xy in (
        ("R12", "115k 0.1%", {1: "BATT_MID", 2: "OV_MAIN"}, (15.24, 312.42)),
        ("R13", "10k 0.1%", {1: "OV_MAIN", 2: "GND"}, (30.48, 312.42)),
        ("R14", "56.2k 0.1%", {1: "BATT_MID", 2: "UV_MAIN"}, (45.72, 312.42)),
        ("R15", "10k 0.1%", {1: "UV_MAIN", 2: "GND"}, (60.96, 312.42)),
        ("R16", "10R", {1: "HGATE_MAIN", 2: "GATE_Q3"}, (76.2, 312.42)),
        ("R17", "8.25k 1%", {1: "HS_REF", 2: "HS_PROG"}, (96.52, 312.42)),
        ("R18", "1k", {1: "HS_PROG", 2: "GND"}, (111.76, 312.42)),
        ("R19", "10R", {1: "HGATE_MAIN", 2: "GATE_Q4"}, (127, 312.42)),
    ):
        add(ref, "Device:R", value, R0603, pins, xy)
    for ref, value, footprint, pins, xy in (
        ("C15", "100nF 50V", C0805, {1: "BATT_RAW", 2: "GND"}, (15.24, 340.36)),
        ("C16", "100nF 50V", C0805, {1: "BATT_MID", 2: "GND"}, (30.48, 340.36)),
        ("C17", "4.7uF 50V", C1210, {1: "CAP_MAIN", 2: "BATT_MID"}, (45.72, 340.36)),
        ("C18", "10nF 50V C0G 5%", C0805, {1: "HS_TIMER", 2: "GND"}, (60.96, 340.36)),
        ("C19", "100nF 50V", C0805, {1: "+12V", 2: "GND"}, (76.2, 340.36)),
        ("C20", "100nF 50V", C0805, {1: "VBUS", 2: "GND"}, (203.2, 312.42)),
        ("C21", "100nF 50V", C0805, {1: "VIN", 2: "GND"}, (218.44, 312.42)),
        ("C22", "4.7uF 50V", C1210, {1: "CAP_USB", 2: "VIN"}, (233.68, 312.42)),
    ):
        add(ref, "Device:C", value, footprint, pins, xy)
    add("D6", "Device:D_Zener", "SMCJ16A", "Diode_SMD:D_SMC",
        {1: "+12V", 2: "GND"}, (96.52, 340.36),
        MPN="SMCJ16A", Manufacturer="Littelfuse", Note="Secondary protected-bus clamp, 26 V at specified pulse current")
    add("D7", "eswitch:STPS41L60C", "STPS41L60CG", "Package_TO_SOT_SMD:TO-263-2",
        {1: "GND", 2: "+12V", 3: "GND"}, (142.24, 340.36),
        MPN="STPS41L60CG-TR", Manufacturer="STMicroelectronics",
        Datasheet="https://www.st.com/resource/en/datasheet/stps41l60c.pdf",
        Note="Both anodes grounded; common cathode/tab on protected bus; negative-output freewheel clamp")
    add("#FLG9", "power:PWR_FLAG", "PWR_FLAG", "", {1: "HS_VCC"}, (510.54, 358.14))
    for n in range(1, 9):
        c, r = (n-1) % 4, (n-1) // 4
        bx, by = 12.7 + c * 72.39, 22.86 + r * 82.55
        add(f"C{n}04", "Device:C", "47nF 50V", C0805,
            {1: f"VS{n}", 2: f"UGND{n}"}, (bx + 25.4, by + 72.39), Note="VS-to-device-GND EMC capacitor")
        add(f"R{n}08", "Device:R", "47k", R0603,
            {1: f"INR{n}", 2: f"UGND{n}"}, (bx + 45.72, by + 72.39), Note="Explicit OFF bias during MCU reset")
    add("#FLG6", "power:PWR_FLAG", "PWR_FLAG", "", {1: "BATT_RAW"}, (480.06, 358.14))
    add("#FLG7", "power:PWR_FLAG", "PWR_FLAG", "", {1: "BATT_MID"}, (490.22, 358.14))
    add("#FLG8", "power:PWR_FLAG", "PWR_FLAG", "", {1: "AGND_BUCK"}, (500.38, 358.14))


# Manufacturer / MPN by (value, footprint). Applied to every part after build(); explicit
# MPN= arguments in add() take precedence.
PART_NUMBERS = {
    ("115k 0.1%", R0603): ("YAGEO", "RT0603BRD07115KL"),
    ("56.2k 0.1%", R0603): ("YAGEO", "RT0603BRD0756K2L"),
    ("8.25k 1%", R0603): ("YAGEO", "RC0603FR-078K25L"),
    ("10R", R0603): ("YAGEO", "RC0603FR-0710RL"),
    ("10nF 50V C0G 5%", C0805): ("KEMET", "C0805C103J5GACTU"),
    ("16.5k 1%", R0603): ("YAGEO", "RC0603FR-0716K5L"),
    ("127k 0.1%", R0603): ("YAGEO", "RT0603BRD07127KL"),
    ("59k 0.1%", R0603): ("YAGEO", "RT0603BRD0759KL"),
    ("10k 0.1%", R0603): ("YAGEO", "RT0603BRD0710KL"),
    ("22R", R0603): ("Panasonic Industry", "ERJ-3EKF22R0V"),
    ("100R", R0603): ("YAGEO", "RC0603FR-07100RL"),
    ("47nF 50V", C0805): ("Samsung Electro-Mechanics", "CL21B473KBCNNNC"),
    ("4.7k", R0603): ("YAGEO", "RC0603FR-074K7L"),
    ("10k", R0603): ("YAGEO", "RC0603FR-0710KL"),
    ("1k", R0603): ("YAGEO", "RC0603FR-071KL"),
    ("5.1k", R0603): ("Panasonic", "ERJ-3EKF5101V"),
    ("2.2k", R0603): ("YAGEO", "RC0603FR-072K2L"),
    ("47k", R0603): ("YAGEO", "RC0603FR-0747KL"),
    ("1.2k 1%", R0603): ("YAGEO", "RC0603FR-071K2L"),
    ("2.2k 1%", R0603): ("YAGEO", "RC0603FR-072K2L"),
    ("3.3k 1%", R0603): ("YAGEO", "RC0603FR-073K3L"),
    ("3.9k", R0603): ("YAGEO", "RC0603FR-073K9L"),
    ("200k 1%", R0603): ("Panasonic", "ERJ-3EKF2003V"),
    ("31.6k 1%", R0603): ("YAGEO", "RC0603FR-0731K6L"),
    ("10.2k 1%", R0603): ("YAGEO", "RC0603FR-0710K2L"),
    ("47R", R0805): ("YAGEO", "RC0805FR-0747RL"),
    # ±5 % is a reviewed, tighter-tolerance substitute for the formerly selected
    # ±10 % CC0603KRX7R9BB104, which went out of stock at DigiKey on 2026-09-15.
    ("100nF 50V", C0603): ("YAGEO", "CC0603JRX7R9BB104"),
    ("100nF 25V", C0603): ("YAGEO", "CC0603JRX7R9BB104"),
    ("100nF", C0603): ("YAGEO", "CC0603JRX7R9BB104"),
    ("1uF", C0603): ("YAGEO", "CC0603KRX7R7BB105"),
    ("220pF 50V", C0603): ("Samsung Electro-Mechanics", "CL10C221JB8NFNC"),
    ("27nF", C0603): ("YAGEO", "CC0603KRX7R9BB273"),
    ("150pF", C0603): ("Samsung Electro-Mechanics", "CL10C151JB8NNNC"),
    ("100nF 50V", C0805): ("Samsung Electro-Mechanics", "CL21B104KBCNNNC"),
    ("10nF 50V", C0805): ("Samsung Electro-Mechanics", "CL21B103KBANNNC"),
    ("10uF 10V", C0805): ("YAGEO", "CC0805KKX5R6BB106"),
    ("4.7uF 50V", C1210): ("Murata", "GRM32ER71H475KA88L"),
    ("47uF 6.3V X7R", C1210): ("Murata", "GCM32ER70J476KE19L"),
    ("B360A", SMA): ("Diodes Incorporated", "B360A-13-F"),
    ("SMBJ26A", SMB): ("Littelfuse", "SMBJ26A"),
    ("BAT54S", SOT23): ("Nexperia", "BAT54S-QR"),
    ("GREEN", LED0603): ("Wurth Elektronik", "150060GS75000"),
    ("BLUE", LED0603): ("Wurth Elektronik", "150060BS75000"),
}
MANUFACTURERS = {
    "BTS70081EPRXUMA1": "Infineon", "BTS70041EPPXUMA1": "Infineon", "BTS70021EPPXUMA1": "Infineon", "ESP32-S3-WROOM-1-N8": "Espressif", "TPS54360BDDAR": "Texas Instruments",
    "USBLC6-2SC6": "STMicroelectronics", "Keystone 3557 (x3)": "Keystone Electronics",
    "Keystone 8196": "Keystone Electronics", "691218410002": "Wurth Elektronik",
    "GCT USB4105-GF-A": "GCT", "Bourns SRP7028A-100M": "Bourns", "Littelfuse 0466002.NR": "Littelfuse",
    "PTS645SM43SMTR92": "C&K",
}
MPN_CLEAN = {"Keystone 3557 (x3)": "3557", "Keystone 8196": "8196", "GCT USB4105-GF-A": "USB4105-GF-A",
             "PTS645SM43SMTR92": "PTS645SM43SMTR92 LFS",
             "Bourns SRP7028A-100M": "SRP7028A-100M", "Littelfuse 0466002.NR": "0466002.NR"}


def apply_part_numbers():
    for p in PARTS:
        if p.ref.startswith("#") or p.ref.startswith("H"):
            continue
        if p.fields.get("MPN"):
            raw = p.fields["MPN"]
            p.fields["Manufacturer"] = MANUFACTURERS.get(raw, p.fields.get("Manufacturer", ""))
            p.fields["MPN"] = MPN_CLEAN.get(raw, raw)
            if raw == "Keystone 3557 (x3)":
                p.fields["Note"] = "3 clips per position; " + p.fields.get("Note", "")
            continue
        key = (p.value, p.footprint)
        if key in PART_NUMBERS:
            p.fields["Manufacturer"], p.fields["MPN"] = PART_NUMBERS[key]
        elif p.ref == "J5":
            p.fields["Manufacturer"], p.fields["MPN"] = "Wurth Elektronik", "61300411121"


def nets():
    """net name -> set of (ref, pin)."""
    out = {}
    for p in PARTS:
        for pin, net in p.pins.items():
            out.setdefault(net, set()).add((p.ref, pin))
    return out


if __name__ == "__main__":
    build()
    print(len(PARTS), "parts,", len(nets()), "nets")
