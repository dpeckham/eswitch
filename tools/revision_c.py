"""Revision C circuit: independent latching breakers before both fuse positions.

Values are checked independently by channel_isolation_analysis.py. No firmware
or 3V3 supply is needed to enable, trip, or reset a branch breaker.
"""
from design import R0603, C0805, SOT23, CHANNELS

W, H = 334.0, 172.0
CX = [136., 160., 184., 208., 244., 268., 292., 316.]
MOUNTS = [(85, 82), (5, 75), (328, 6), (328, 166),
          (118, 90), (226, 90), (226, 166), (118, 166),
          (5, 166), (5, 90), (118, 6), (226, 6)]
FAULT_PINS = ['9', '10', '11', '28', '29', '30', '32', '33']
SHUNT_COUNT = {n: 1 for n in range(1, 9)}
SHUNT_MOHM = {n: (2 if n == 8 else 4 if n <= 2 else 8) for n in range(1, 9)}


def apply(parts_list, add):
    p = {x.ref: x for x in parts_list}
    p['J4'].footprint = 'eswitch:USB4105_NPTH_0p2'
    p['R20'].value = '0.5mR 1% 5W'
    p['R20'].fields.update(MPN='CSS4J-4026R-L500F',
        Note='Four-terminal common backup limit; coordinated above one branch fault plus 40A healthy load')
    p['C18'].value = '12nF 50V C0G 5%'
    p['C18'].fields.update(MPN='C0805C123J5GACTU',Manufacturer='KEMET')
    p['R17'].value = '8.25k 0.1%'
    p['R17'].fields.update(MPN='RT0603BRD078K25L', Manufacturer='YAGEO')
    p['R18'].value = '1k 0.1%'
    p['R18'].fields.update(MPN='RT0603BRD071KL', Manufacturer='YAGEO')
    p['U14'].pins.update({'6':'MAIN_IMON', '8':'MAIN_PG_N', '9':'MAIN_FLT_N'})
    p['U14'].fields['Note'] = 'Common bus backup current/power limit; branch breakers provide output-fault isolation'
    p['U10'].pins.pop('7')
    p['U10'].pins.update({'8':'IN1', '5':'ADC_IMON', '7':'ADC_BUS', '35':'MAIN_FLT_N'})
    for n, pin in enumerate(FAULT_PINS, 1):
        p['U10'].pins[pin] = f'BR_FLT{n}'
    for i, xy in enumerate(MOUNTS[4:], 5):
        add(f'H{i}', 'Mechanical:MountingHole', 'M3',
            'MountingHole:MountingHole_3.2mm_M3', {}, (650+(i-5)*12.7, 400))

    # PG is active LOW. Invert from the always-available 4V reference, so the
    # main bus charges before branch startup and BYPASS survives an MCU fault.
    add('Q6', 'Transistor_BJT:MMBT3906', 'MMBT3906LT1G', SOT23,
        {1:'BR_ENABLE_BASE', 2:'HS_REF', 3:'BR_ENABLE'}, (650, 240),
        MPN='MMBT3906LT1G', Manufacturer='onsemi',
        Datasheet='https://www.onsemi.com/pdf/datasheet/mmbt3906lt1-d.pdf')
    def resistor(ref, value, pins, xy, **kw):
        return add(ref, 'Device:R', value, R0603, pins, xy, **kw)
    resistor('R21','10k',{1:'MAIN_PG_N',2:'BR_ENABLE_BASE'},(620,270))
    resistor('R22','47k',{1:'BR_ENABLE_BASE',2:'HS_REF'},(640,270))
    resistor('R23','47k',{1:'BR_ENABLE',2:'GND'},(660,270))
    resistor('R24','10k',{1:'+3V3',2:'MAIN_FLT_N'},(680,270))
    resistor('R25','47k',{1:'MAIN_IMON',2:'ADC_IMON'},(620,310))
    resistor('R26','115k 0.1%',{1:'+12V',2:'BUS_DIV'},(640,310))
    resistor('R27','10k 0.1%',{1:'BUS_DIV',2:'GND'},(660,310))
    resistor('R28','47k',{1:'BUS_DIV',2:'ADC_BUS'},(680,310))
    for ref, net, x in [('C23','ADC_IMON',620),('C24','ADC_BUS',650)]:
        add(ref,'Device:C','10nF 50V',C0805,{1:net,2:'GND'},(x,345))
    for ref, net, x in [('D8','ADC_IMON',680),('D9','ADC_BUS',710)]:
        add(ref,'Diode:BAT54S','BAT54S',SOT23,{1:'GND',2:'+3V3',3:net},(x,345))
    add('C25','Device:C','12nF 50V C0G 5%',C0805,
        {1:'HS_TIMER',2:'GND'},(720,270),MPN='C0805C123J5GACTU',Manufacturer='KEMET',
        Note='C18/C25/C28 in parallel: common timer 36nF')
    add('C28','Device:C','12nF 50V C0G 5%',C0805,
        {1:'HS_TIMER',2:'GND'},(740,270),MPN='C0805C123J5GACTU',Manufacturer='KEMET',
        Note='C18/C25/C28 in parallel: common timer 36nF')
    for n in range(1,9):
        x, y = 35 + ((n-1)%4)*250, 465 + ((n-1)//4)*170.18
        feed, sense = f'CHFEED{n}', f'BR_SENSE{n}'
        p[f'F{n}'].pins['2'] = feed
        p[f'F{n}'].fields['Note'] = f'CH{n}: both AUTO and BYPASS are downstream of independent hardware latch'
        add(f'U{20+n}', 'eswitch:TPS2492', 'TPS2492 (CHANNEL LATCH)',
            'Package_SO:TSSOP-14_4.4x5mm_P0.65mm',
            {1:f'BR_EN{n}',2:f'BR_REF{n}',3:f'BR_PROG{n}',4:f'BR_TIMER{n}',
             5:'GND',7:'GND',9:f'BR_FLT{n}',11:f'BR_OUT{n}',12:f'BR_GATE{n}',
             13:sense,14:'+12V'}, (x+55,y),
            MPN='TPS2492PWR',Manufacturer='Texas Instruments',
            Datasheet='https://www.ti.com/lit/ds/symlink/tps2492.pdf',
            Note=f'CH{n} local latch; reset only with SW{n+2}; OV handled by U14')
        add(f'Q{10+n}','eswitch:PSMN1R8-80SSE','PSMN1R8-80SSE',
            'Package_TO_SOT_SMD:LFPAK88',
            {1:f'BR_GS{n}',2:feed,3:feed,4:feed,5:sense},(x+115,y),
            MPN='PSMN1R8-80SSEJ',Manufacturer='Nexperia',
            Datasheet='https://assets.nexperia.com/documents/data-sheet/PSMN1R8-80SSE.pdf',
            Note=f'CH{n}: enhanced SOA, one device carries all branch linear stress')
        for k in range(3):
            add(f'C{n}{14+k}','Device:C_Polarized','120uF 35V polymer',
                'Capacitor_SMD:CP_Elec_10x12.6', {1:'+12V',2:'GND'},(x+100+k*22.86,y+130),
                MPN='35SVPF120M',Manufacturer='Panasonic Industry',
                Datasheet='https://industrial.panasonic.com/ww/products/pt/os-con/models/35SVPF120M',
                Note='Common reservoir: 24 parallel 120uF/18mOhm capacitors distributed along bus')
        milliohms=SHUNT_MOHM[n]
        add(f'R{n}20','Device:R',f'{milliohms}mR 1% 3W',
            'eswitch:WSLP2512_8m' if milliohms==8 else 'eswitch:WSLP2512_2m',
            {1:'+12V',2:sense},(x,y+45.72),
            MPN=f'WSLP2512{milliohms}L000FEA',Manufacturer='Vishay Dale',
            Datasheet='https://www.vishay.com/docs/30122/wslp.pdf',
            Note='Independent Kelvin pickup at both shunt lands; no series PCB interconnect in the sensed resistance')
        for ref, value, pins, xx in [
            (f'R{n}11','100R',{1:f'BR_GATE{n}',2:f'BR_GS{n}'},x),
            (f'R{n}12','7.5k' if n==8 else '2.2k' if n in range(3,8) else '4.7k',
                {1:f'BR_REF{n}',2:f'BR_PROG{n}'},x+20.32),
            (f'R{n}13','1k',{1:f'BR_PROG{n}',2:'GND'},x+40.64),
            (f'R{n}14','47k',{1:'BR_ENABLE',2:f'BR_EN{n}'},x+60.96),
            (f'R{n}15','10k',{1:'+3V3',2:f'BR_FLT{n}'},x+81.28),
        ]:
            fields={}
            if ref==f'R{n}11': fields=dict(MPN='RC0603FR-07100RL',Manufacturer='YAGEO')
            if ref==f'R{n}12':
                mpn,maker={'7.5k':('RT0603BRD077K5L','YAGEO'),
                    '4.7k':('RT0603BRD074K7L','YAGEO'),
                    '2.2k':('RG1608P-222-B-T5','Susumu')}[value]
                fields=dict(MPN=mpn,Manufacturer=maker); value+=' 0.1%'
            if ref==f'R{n}13':
                fields=dict(MPN='RT0603BRD071KL',Manufacturer='YAGEO'); value+=' 0.1%'
            resistor(ref,value,pins,(xx,y+73.66),**fields)
        add(f'Q{30+n}', 'Transistor_BJT:MMBT3906', 'FMMT720TA', SOT23,
            {1:f'BR_GATE{n}',2:f'BR_GS{n}',3:f'BR_PULL{n}'},(x+175,y),
            MPN='FMMT720TA',Manufacturer='Diodes Incorporated',
            Datasheet='https://www.diodes.com/assets/Datasheets/FMMT720.pdf',
            Note='PNP boosts gate discharge during a live short; 40V, 4A pulse')
        resistor(f'R{n}16','10R',{1:f'BR_PULL{n}',2:feed},(x+150,y+30.48))
        resistor(f'R{n}17','10R',{1:feed,2:f'BR_OUT{n}'},(x+150,y+82))
        add(f'D{n}12','Diode:BAT54S','BAT54S',SOT23,
            {1:'GND',3:f'BR_OUT{n}'},(x+175,y+112),
            Note='One Schottky junction protects OUT sense from local freewheel undershoot')
        for k in (1,2):
            add(f'C{n}{10+k}','Device:C','100nF 50V U2J 5%',
                'Capacitor_SMD:C_1206_3216Metric',
                {1:f'BR_TIMER{n}',2:'GND'},(x+(k-1)*22.86,y+104.14),
                MPN='C1206C104J5JACAUTO',Manufacturer='KEMET',
                Datasheet='https://www.yageogroup.com/component-documentation/download/specsheet/C1206C104J5JACAUTO',
                Note='Class I stable dielectric; pair gives 200nF; include U2J temperature coefficient')
        add(f'C{n}13','Device:C','100nF 50V',C0805,
            {1:'+12V',2:'GND'},(x+45.72,y+104.14))
        add(f'SW{n+2}','Switch:SW_Push',f'RESET CH{n}',
            'Button_Switch_SMD:SW_SPST_PTS645Sx43SMTR92',
            {1:'GND',2:f'BR_EN{n}'},(x+78.74,y+104.14),rot=90,
            MPN='PTS645SM43SMTR92',Note='Local manual reset; hardware protection needs no firmware')
        add(f'D{n}11','eswitch:STPS41L60C','STPS41L60CG','Package_TO_SOT_SMD:TO-263-2',
            {1:'GND',2:feed,3:'GND'},(x+130,y+60.96),
            MPN='STPS41L60CG-TR',Manufacturer='STMicroelectronics',
            Datasheet='https://www.st.com/resource/en/datasheet/stps41l60c.pdf',
            Note='Local freewheel clamp; both anodes grounded, common cathode on branch feed')
        # Reverse protection for the output indicator. BAT54S's two series
        # junctions conduct GND -> LED anode; midpoint intentionally unused.
        add(f'D{n}03','Diode:BAT54S','BAT54S',SOT23,
            {1:'GND',2:f'LEDK{n}'},(x+130,y+104.14),
            Note='Antiparallel series Schottky pair across output LED')
    tpnets = ['GND','BATT_RAW','BATT_MID','HS_VCC','HS_SENSE','HS_TIMER',
              'HGATE_MAIN','+12V','VIN','+3V3','MAIN_IMON','MAIN_FLT_N',
              'MAIN_PG_N','BR_ENABLE','ADC_IMON','ADC_BUS']
    tpnets += [f'BR_TIMER{n}' for n in range(1,9)]
    for i, net in enumerate(tpnets,1):
        add(f'TP{i}','Connector:TestPoint',net,
            'TestPoint:TestPoint_Pad_D1.5mm',{1:net},
            (620+((i-1)%8)*20.32, 30+((i-1)//8)*30.48),
            Note='Copper test pad; no purchased component')
