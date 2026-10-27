"""Fresh circuit definition. Does not call or mutate the revision-C design.

Reuses reviewed library symbols/footprints and the USB-capable converter circuit,
not the old power-distribution/protection architecture. Engineering draft.
"""
from dataclasses import dataclass, field


@dataclass
class Part:
    ref: str
    lib_id: str
    value: str
    footprint: str
    pins: dict
    at: tuple
    rot: int = 0
    fields: dict = field(default_factory=dict)


R0603 = "Resistor_SMD:R_0603_1608Metric"
C0805 = "Capacitor_SMD:C_0805_2012Metric"
C0603 = "Capacitor_SMD:C_0603_1608Metric"
C1210 = "Capacitor_SMD:C_1210_3225Metric"
SOT23 = "Package_TO_SOT_SMD:SOT-23"
R_MPN = {
    "4.7k": "RC0603FR-074K7L", "47k": "RC0603FR-0747KL",
    "10k": "RC0603FR-0710KL", "2.2k": "RC0603FR-072K2L",
    "3.3k": "RC0603FR-073K3L", "1.2k": "RC0603FR-071K2L",
    "1k": "RC0603FR-071KL", "22R": "ERJ-3EKF22R0V",
    "5.1k": "ERJ-3EKF5101V", "16.5k": "RC0603FR-0716K5L",
}
SENSE_MPN = {'2.2k': 'ERJ-PA3F2201V', '3.3k': 'ERJ-PA3F3301V', '1.2k': 'ERJ-PA3F1201V'}
C_PARTS = {
    "100nF 50V": (C0805, "CL21B104KBCNNNC"),
    "10nF 50V": (C0805, "CL21B103KBANNNC"),
    "47nF 50V": (C0805, "CL21B473KBCNNNC"),
    "1uF": (C0603, "CC0603KRX7R7BB105"),
    "10uF 10V": (C0805, "CC0805KKX5R6BB106"),
    "4.7uF 50V": (C1210, "GRM32ER71H475KA88L"),
    "47uF 6.3V X7R": (C1210, "GCM32ER70J476KE19L"),
}
# S3-WROOM-1 module pad, GPIO number; avoid strapping and USB pins.
ADC = [(39, 1), (38, 2), (15, 3), (4, 4), (5, 5), (6, 6), (7, 7), (12, 8)]
CONTROL = [(8, 15), (9, 16), (10, 17), (11, 18), (19, 11), (20, 12), (21, 13), (22, 14)]
DIAG = [(23, 21), (28, 35), (29, 36), (30, 37), (31, 38), (32, 39), (33, 40), (34, 41)]
CHANNELS = [
    (10, "BTS7004-1EPP", "BTS70041EPPXUMA1", "2.2k"),
    (10, "BTS7004-1EPP", "BTS70041EPPXUMA1", "2.2k"),
    *[(5, "BTS7008-1EPR", "BTS70081EPRXUMA1", "3.3k")] * 5,
    (20, "BTS7002-1EPP", "BTS70021EPPXUMA1", "1.2k"),
]


def build():
    parts = []

    def add(ref, lib, value, fp, pins, xy, mpn=None, rot=0, **fields):
        if mpn:
            fields["MPN"] = mpn
        parts.append(Part(ref, lib, value, fp, {str(k): v for k, v in pins.items()}, xy, rot, fields))

    def resistor(ref, value, a, b, xy):
        add(ref, "Device:R", value, R0603, {1: a, 2: b}, xy, R_MPN[value])

    def cap(ref, value, a, b, xy):
        fp, mpn = C_PARTS[value]
        add(ref, "Device:C", value, fp, {1: a, 2: b}, xy, mpn)

    def clamp(ref, net, xy):
        add(ref, "Diode:BAT54S", "BAT54S", SOT23, {1: "GND", 2: "ADC_CLAMP_2V5", 3: net}, xy, "BAT54S-QR")

    for n, (rating, device, mpn, sense) in enumerate(CHANNELS, 1):
        x, y = 12.7 + ((n - 1) % 4) * 76.2, 25.4 + ((n - 1) // 4) * 93.98
        vs, load, ugnd = "AUTO_PROTECTED", f"PROFET_OUT{n}", f"UGND{n}"
        add(f"F{n}", "eswitch:FuseHolder_ATO_3pos", f"ATO {rating}A MAX",
            "eswitch:Fuseholder_ATO_3pos_Keystone_3557", {1: load, 2: f"LOAD{n}", 3: "BATT_RAW"},
            (x + 12.7, y + 12.7), "3557", Quantity="3",
            Note="ONE fuse: AUTO OUT-LOAD; BYPASS RAW-LOAD; remove for OFF. Common clip is LOAD. Change unpowered.")
        add(f"U{n}", f"eswitch:{device}", device, "Package_SO:Infineon_PG-TSDSO-14-22",
            {1: ugnd, 2: f"INR{n}", 3: f"DENR{n}", 4: f"ISP{n}", 8: load, 15: vs},
            (x + 50.8, y + 12.7), mpn,
            Datasheet=f"https://www.infineon.com/assets/row/public/documents/10/49/infineon-{device.lower()}-datasheet-en.pdf")
        for k, value, a, b, dx in (
            (1, "4.7k", f"IN{n}", f"INR{n}", 5.08),
            (2, "4.7k", f"DEN{n}", f"DENR{n}", 15.24),
            (4, sense, f"ISP{n}", "GND", 35.56),
            (5, "4.7k", f"ISP{n}", f"IS{n}", 45.72),
        ):
            resistor(f"R{n}{k:02}", value, a, b, (x + dx, y + 35.56))
            if k == 4:
                parts[-1].fields['MPN'] = SENSE_MPN[value]
                parts[-1].fields['Note'] = 'High-power 0603 sense resistor; retain value, use ERJ-PA3 pulse-rated series for sustained IS fault current.'
        add(f"R{n}03", "Device:R", "47R", "Resistor_SMD:R_0805_2012Metric",
            {1: ugnd, 2: "GND"}, (x + 25.4, y + 35.56), "RC0805FR-0747RL")
        # 47 us nominal filtering, above Infineon's recommended 1 us minimum.
        cap(f"C{n}03", "10nF 50V", f"IS{n}", "GND", (x + 55.88, y + 35.56))
        clamp(f"D{n}01", f"IS{n}", (x + 5.08, y + 58.42))
        cap(f"C{n}01", "100nF 50V", vs, "GND", (x + 15.24, y + 58.42))
        cap(f"C{n}02", "10nF 50V", load, "GND", (x + 25.4, y + 58.42))
        resistor(f"R{n}06", "47k", load, "GND", (x + 35.56, y + 58.42))
        resistor(f"R{n}07", "10k", load, f"LEDK{n}", (x + 45.72, y + 58.42))
        add(f"D{n}02", "Device:LED", "GREEN", "LED_SMD:LED_0603_1608Metric",
            {1: "GND", 2: f"LEDK{n}"}, (x + 55.88, y + 58.42), "150060GS75000", rot=90)
        # Both digital pins have local OFF bias independent of firmware.
        cap(f"C{n}04", "47nF 50V", vs, ugnd, (x + 5.08, y + 78.74))
        resistor(f"R{n}08", "47k", f"INR{n}", ugnd, (x + 20.32, y + 78.74))
        resistor(f"R{n}09", "47k", f"DENR{n}", ugnd, (x + 35.56, y + 78.74))
        # D10 suppresses local transients on the shared protected supply.
        # All channel shunts stay on the PROFET side of the movable fuse:
        # no capacitor, indicator or TVS is connected to a raw BYPASS load.
        # LED negative-voltage clamp: second BAT54S diode GND -> LED anode;
        # first diode shorted. Normal positive LED voltage is not clamped.
        add(f"D{n}03", "Diode:BAT54S", "BAT54S", SOT23,
            {1: "GND", 2: f"LEDK{n}", 3: "GND"}, (x + 66.04, y + 78.74), "BAT54S-QR")

    esp = {1: "GND", 40: "GND", 41: "GND", 2: "+3V3", 3: "EN", 27: "IO0",
           13: "USB_MCU_D-", 14: "USB_MCU_D+", 37: "TXD0", 36: "RXD0", 35: "STATUS"}
    for n, (adc, control, diag) in enumerate(zip(ADC, CONTROL, DIAG), 1):
        esp[adc[0]], esp[control[0]], esp[diag[0]] = f"IS{n}", f"IN{n}", f"DEN{n}"
    add("U10", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1-N8",
        "eswitch:ESP32-S3-WROOM-1_Edge", esp, (381, 80.01), "ESP32-S3-WROOM-1-N8")
    cap("C9", "10uF 10V", "+3V3", "GND", (335.28, 137.16))
    cap("C10", "100nF 50V", "+3V3", "GND", (347.98, 137.16))
    resistor("R5", "10k", "+3V3", "EN", (360.68, 137.16))
    cap("C11", "1uF", "EN", "GND", (373.38, 137.16))
    resistor("R6", "10k", "+3V3", "IO0", (398.78, 137.16))
    for ref, net, x in (("SW1", "EN", 386.08), ("SW2", "IO0", 411.48)):
        add(ref, "Switch:SW_Push", "RESET" if ref == "SW1" else "BOOT",
            "Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92", {1: "GND", 2: net},
            (x, 137.16), "PTS645SM43SMTR92 LFS", rot=90)
    resistor("R9", "1k", "STATUS", "STATUS_K", (424.18, 137.16))
    add("D5", "Device:LED", "BLUE", "LED_SMD:LED_0603_1608Metric",
        {1: "GND", 2: "STATUS_K"}, (436.88, 137.16), "150060BS75000", rot=90)
    add("J5", "Connector_Generic:Conn_01x04", "UART",
        "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
        {1: "GND", 2: "+3V3", 3: "TXD0", 4: "RXD0"}, (436.88, 80.01), "61300411121")
    usb = {p: "GND" for p in ("A1", "A12", "B1", "B12", "SH")}
    usb.update({p: "VBUS" for p in ("A4", "A9", "B4", "B9")})
    usb.update({"A5": "CC1", "B5": "CC2", "A6": "USB_D+", "B6": "USB_D+", "A7": "USB_D-", "B7": "USB_D-"})
    add("J4", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C", "eswitch:USB4105_NPTH_0p2",
        usb, (340.36, 184.15), "USB4105-GF-A")
    add("U11", "Power_Protection:SRV05-4", "SRV05-4HTG-D", "Package_TO_SOT_SMD:SOT-23-6",
        {1: "USB_D+", 6: "USB_D+", 3: "USB_D-", 4: "USB_D-", 2: "GND", 5: "VBUS"},
        (391.16, 172.72), "SRV05-4HTG-D")
    for ref, value, a, b, x in (("R7", "5.1k", "CC1", "GND", 411.48), ("R8", "5.1k", "CC2", "GND", 424.18),
                              ("R10", "22R", "USB_D+", "USB_MCU_D+", 449.58), ("R11", "22R", "USB_D-", "USB_MCU_D-", 462.28)):
        resistor(ref, value, a, b, (x, 184.15))

    # Independent logic branch. Retain the already researched wide-input module
    # and USB ideal diode for this first draft; cost-optimize after power review.
    add("F9", "Device:Fuse", "2A LOGIC", "Fuse:Fuse_1206_3216Metric",
        {1: "AUTO_PROTECTED", 2: "LOGIC_FUSED"}, (25.4, 254), "0466002.NR")
    add("D1", "Device:D_Schottky", "B360A", "Diode_SMD:D_SMA",
        {2: "LOGIC_FUSED", 1: "VIN"}, (45.72, 254), "B360A-13-F", rot=90)
    add("D3", "Device:D_TVS", "SMCJ16A", "Diode_SMD:D_SMC",
        {1: "VIN", 2: "GND"}, (66.04, 254), "SMCJ16A")
    for ref, x in (("C1", 86.36), ("C2", 106.68)):
        cap(ref, "4.7uF 50V", "VIN", "GND", (x, 254))
    cap("C3", "100nF 50V", "VIN", "GND", (127, 254))
    buck = {p: "VIN" for p in (2, 3, 4, 18, 19)}
    buck.update({p: "GND" for p in (5, 6, 16, 17, 28, 29)})
    buck.update({p: "+3V3" for p in (7, 8, 9, 10, 12, 13, 14, 15, 22, 25, 30)})
    buck.update({1: "RT", 23: "VCC_BUCK", 24: "AGND_BUCK", 27: "AGND_BUCK"})
    add("U9", "eswitch:TPSM63603V3", "TPSM63603V3", "eswitch:TI_RDH0030A_TPSM63603",
        buck, (45.72, 302.26), "TPSM63603V3RDHR")
    resistor("R1", "16.5k", "RT", "AGND_BUCK", (86.36, 302.26))
    cap("C14", "1uF", "VCC_BUCK", "GND", (106.68, 302.26))
    add("NT1", "Device:NetTie_2", "AGND STAR", "NetTie:NetTie-2_SMD_Pad0.5mm",
        {1: "AGND_BUCK", 2: "GND"}, (127, 302.26))
    for ref, x in (("C7", 25.4), ("C8", 50.8), ("C12", 76.2), ("C13", 101.6)):
        cap(ref, "47uF 6.3V X7R", "+3V3", "GND", (x, 340.36))
    add("Q5", "eswitch:BSC016N06NS", "BSC016N06NS", "Package_SON:Infineon_PG-TDSON-8_6.15x5.15mm",
        {1: "VBUS", 2: "VBUS", 3: "VBUS", 4: "DGATE_USB", 5: "VIN"}, (190.5, 254), "BSC016N06NSATMA1")
    add("U13", "eswitch:LM74800", "LM74800-Q1", "Package_SON:WSON-12-1EP_3x3mm_P0.5mm_EP1.5x2.5mm",
        {1: "DGATE_USB", 2: "VBUS", 3: "VIN", 4: "VIN", 5: "GND", 6: "VBUS", 7: "GND",
         9: "VIN", 10: "VIN", 11: "CAP_USB", 12: "VIN"}, (190.5, 302.26), "LM74800QDRRRQ1",
        Note="USB reverse blocking. HGATE and exposed pad FLOATING, per datasheet.")
    for ref, value, a, b, x in (("C20", "100nF 50V", "VBUS", "GND", 165.1),
                              ("C21", "100nF 50V", "VIN", "GND", 190.5),
                              ("C22", "4.7uF 50V", "CAP_USB", "VIN", 215.9)):
        cap(ref, value, a, b, (x, 340.36))
    # Divert diagnostic fault current into an independent 2.5V shunt reference,
    # not the ESP32 supply. TLA431 is stable with all capacitive loads.
    add("U14", "Reference_Voltage:TL431DBZ", "TLA431AIDBZR", SOT23,
        {1: "ADC_CLAMP_2V5", 2: "ADC_CLAMP_2V5", 3: "GND"}, (254, 302.26), "TLA431AIDBZR",
        Datasheet="https://www.ti.com/lit/ds/symlink/tla431.pdf",
        Note="2.495V shunt for ADC clamp diodes; pins 1 cathode, 2 REF, 3 anode. TLA431 all-capacitor stability required.")
    resistor("R14", "2.2k", "+3V3", "ADC_CLAMP_2V5", (279.4, 299.72))
    resistor("R15", "47k", "ADC_CLAMP_2V5", "GND", (292.1, 299.72))
    cap("C24", "100nF 50V", "ADC_CLAMP_2V5", "GND", (279.4, 320.04))
    for n in range(1, 9):
        add(f"J{n+10}", "Connector:Screw_Terminal_01x02", f"CH{n} OUTPUT",
            "eswitch:TerminalBlock_1x02_P7.62mm_Wuerth_2184", {1: f"LOAD{n}", 2: "GND"},
            (340.36 + (n-1) % 4 * 30.48, 269.24 + (n-1) // 4 * 25.4), "691218410002")
    for ref, net, y in (("J2", "BATT_RAW", 330.2), ("J3", "GND", 350.52)):
        add(ref, "Connector:Screw_Terminal_01x01", net, "eswitch:ScrewTerminal_Wuerth_74650195_M5",
            {1: net}, (340.36, y), "74650195")
    for i in range(1, 9):
        add(f"H{i}", "Mechanical:MountingHole", "M3 mounting / 10mm standoff",
            "MountingHole:MountingHole_3.2mm_M3", {}, (355.6 + (i-1)*12.7, 350.52),
            "R30-1001002", Note="BOM item is the M3 standoff; hole itself is unplated")
    # PWR_FLAG documents external supply and passive paths, not additional parts.
    from input_protection import build as protection_parts
    parts.extend(protection_parts())
    for i, net in enumerate(["BATT_RAW", "GND", "VBUS", "VIN", "AGND_BUCK", "AUTO_PROTECTED", "AUTO_FUSED", "PROTECTION_COMMON_SOURCE", "VS_CONTROLLER", *[f"UGND{n}" for n in range(1, 9)]]):
        add(f"#FLG{i+1}", "power:PWR_FLAG", "PWR_FLAG", "", {1: net},
            (12.7 + i * 20.32, 386.08))
    return parts
