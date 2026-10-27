"""LM74800-Q1 common-source cutoff prototype; hardware qualification pending.

Based on TI SNOSD95C section 10.3. The requirement is an 80 V surge on the
AUTO/logic branch, not a claim of qualification to the 200 V example waveform.
The raw BYPASS bus must never connect to the protected output of this circuit.
"""
from circuit import Part


def build():
    parts = []

    def add(ref, symbol, value, footprint, pins, xy, mpn, **fields):
        parts.append(Part(ref, symbol, value, footprint,
                          {str(k): v for k, v in pins.items()}, xy,
                          fields=dict(MPN=mpn, **fields)))

    add('F10', 'Device:Fuse', '40A AUTO/LOGIC ISOLATION',
        'eswitch:Fuse_Mersen_14x51_MR14_Wuerth_M5',
        {1: 'BATT_RAW', 2: 'AUTO_FUSED'}, (25.4, 426.72), 'FR14GG50V40',
        HardwareMPN='74650195', HardwareQuantity='2',
        ClipMPN='G098170', ClipQuantity='2',
        Note='One shared removable 14x51 fuse. MR14SPRING clips on M5 terminals with washers; 86 mm mount pitch. Removal isolates AUTO electronics, never BYPASS. First-article fit required.')
    for i in range(4):
        ref = f'Q{6+i}'
        add(ref, 'Transistor_FET:IPT012N08N5', 'IPT067N20NM6 200V',
            'Package_TO_SOT_SMD:Infineon_PG-HSOF-8-1',
            {1: f'HGATE_{ref}', 2: 'PROTECTION_COMMON_SOURCE', 3: 'AUTO_FUSED'},
            (63.5 + i * 30.48, 426.72), 'IPT067N20NM6ATMA1',
            Datasheet='https://www.infineon.com/assets/row/public/documents/24/49/infineon-ipt067n20nm6-datasheet-en.pdf')
        add(f'R{20+i}', 'Device:R', '10R', 'Resistor_SMD:R_0805_2012Metric',
            {1: 'HGATE_AUTO', 2: f'HGATE_{ref}'},
            (63.5 + i * 30.48, 452.12), 'RC0805FR-0710RL')
    for i in range(2):
        ref = f'Q{10+i}'
        add(ref, 'eswitch:BSC016N06NS', 'BSC016N06NS 60V',
            'Package_SON:Infineon_PG-TDSON-8_6.15x5.15mm',
            {1: 'PROTECTION_COMMON_SOURCE', 2: 'PROTECTION_COMMON_SOURCE',
             3: 'PROTECTION_COMMON_SOURCE', 4: f'DGATE_{ref}', 5: 'AUTO_PROTECTED'},
            (200.66 + i * 35.56, 426.72), 'BSC016N06NSATMA1')
        add(f'R{24+i}', 'Device:R', '10R', 'Resistor_SMD:R_0805_2012Metric',
            {1: 'DGATE_AUTO', 2: f'DGATE_{ref}'},
            (200.66 + i * 35.56, 452.12), 'RC0805FR-0710RL')
    add('U15', 'eswitch:LM74800', 'LM74800-Q1 AUTO CUTOFF',
        'Package_SON:WSON-12-1EP_3x3mm_P0.5mm_EP1.5x2.5mm',
        {1: 'DGATE_AUTO', 2: 'PROTECTION_COMMON_SOURCE',
         3: 'PROTECTION_COMMON_SOURCE', 4: 'PROTECTION_COMMON_SOURCE',
         5: 'OV_AUTO', 6: 'VS_CONTROLLER', 7: 'GND', 8: 'HGATE_AUTO',
         9: 'PROTECTION_COMMON_SOURCE', 10: 'VS_CONTROLLER',
         11: 'CAP_AUTO', 12: 'AUTO_PROTECTED'},
        (50.8, 505.46), 'LM74800QDRRRQ1',
        Note='Input-sensed cutoff, not linear surge clamping. Exposed pad FLOATING. No MCU enable dependency.')
    add('R26', 'Device:R', '4.7k 2W',
        'Resistor_THT:R_Axial_DIN0411_L9.9mm_D3.6mm_P15.24mm_Horizontal',
        {1: 'AUTO_FUSED', 2: 'VS_CONTROLLER'}, (25.4, 469.9), 'PR02000204701JA100')
    for ref, value, a, b, x, mpn in (
        ('R27', '49.9k 0.1%', 'AUTO_FUSED', 'OV_DIV_MID', 101.6, 'RT0805BRD0749K9L'),
        ('R28', '49.9k 0.1%', 'OV_DIV_MID', 'OV_AUTO', 121.92, 'RT0805BRD0749K9L'),
        ('R29', '7.87k 0.1%', 'OV_AUTO', 'GND', 142.24, 'RT0805BRD077K87L')):
        add(ref, 'Device:R', value, 'Resistor_SMD:R_0805_2012Metric',
            {1: a, 2: b}, (x, 482.6), mpn)
    for ref, value, a, b, xy, mpn in (
        ('D6', 'SMBJ150A', 'AUTO_FUSED', 'TVS_INPUT_MID', (177.8, 482.6), 'SMBJ150A'),
        ('D7', 'SMBJ33CA', 'TVS_INPUT_MID', 'GND', (198.12, 482.6), 'SMBJ33CA')):
        add(ref, 'Device:D_TVS', value, 'Diode_SMD:D_SMB',
            {1: a, 2: b}, xy, mpn)
    for ref, value, a, b, xy, mpn in (
        ('D8', '51V 2%', 'VS_CONTROLLER', 'GND', (101.6, 513.08), 'BZG03B51-M3_A-08'),
        ('D9', '82V', 'VS_CONTROLLER', 'PROTECTION_COMMON_SOURCE', (127, 513.08), 'BZG03C82-M3_A-08')):
        add(ref, 'Device:D_Zener', value, 'Diode_SMD:D_SMA',
            {1: a, 2: b}, xy, mpn)
    add('D10', 'Device:D_TVS', 'SMCJ16A LOCAL TRANSIENT', 'Diode_SMD:D_SMC',
        {1: 'AUTO_PROTECTED', 2: 'GND'}, (152.4, 513.08), 'SMCJ16A',
        Note='Downstream transient suppression only; not the sustained input-surge protection mechanism.')
    for ref, value, a, b, xy, fp, mpn in (
        ('C25', '100nF 250V', 'AUTO_FUSED', 'GND', (25.4, 548.64),
         'Capacitor_SMD:C_1210_3225Metric', 'C3225X7R2E104K200AA'),
        ('C26', '1uF 100V', 'VS_CONTROLLER', 'GND', (50.8, 548.64),
         'Capacitor_SMD:C_1210_3225Metric', 'GRM32CR72A105KA35L'),
        ('C27', '1uF 50V', 'CAP_AUTO', 'VS_CONTROLLER', (76.2, 548.64),
         'Capacitor_SMD:C_0805_2012Metric', 'GRM21BR71H105KA12L'),
        ('C28', '1uF 100V', 'PROTECTION_COMMON_SOURCE', 'GND', (101.6, 548.64),
         'Capacitor_SMD:C_1210_3225Metric', 'GRM32CR72A105KA35L'),
        ('C29', '4.7uF 50V', 'AUTO_PROTECTED', 'GND', (127, 548.64),
         'Capacitor_SMD:C_1210_3225Metric', 'GRM32ER71H475KA88L')):
        add(ref, 'Device:C', value, fp, {1: a, 2: b}, xy, mpn)
    return parts
