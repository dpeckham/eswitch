#!/usr/bin/env python3
"""PROFET IS resistor screen at explicit manufacturer characterization points."""
import hashlib
import json
from pathlib import Path
import circuit

HERE=Path(__file__).resolve().parent
DATA={
    'BTS7004-1EPP':dict(ratio=20000,test_a=10,ratio_tolerance=.05,page=49,revision='1.11, 2024-07-29'),
    'BTS7008-1EPR':dict(ratio=14500,test_a=5.5,ratio_tolerance=.08,page=48,revision='1.00, 2024-10-01'),
    'BTS7002-1EPP':dict(ratio=22900,test_a=22,ratio_tolerance=.06,page=49,revision='1.11, 2024-07-29'),
}


def screen():
    parts={p.ref:p for p in circuit.build()}
    rows=[]
    for n,(fuse,device,mpn,value) in enumerate(circuit.CHANNELS,1):
        ref=f'R{n}04';p=parts[ref];d=DATA[device]
        assert p.value==value and p.fields['MPN']==circuit.SENSE_MPN[value]
        assert p.pins=={'1':f'ISP{n}','2':'GND'}
        resistance=float(value[:-1])*1000 if value.endswith('k') else float(value)
        upper=d['test_a']*resistance*1.01/(d['ratio']*(1-d['ratio_tolerance']))
        lower=d['test_a']*resistance*.99/(d['ratio']*(1+d['ratio_tolerance']))
        assert upper<2.5,(ref,upper)
        # Maximum specified IS fault source is 10 mA. Include the 4.7k path
        # to the ~3 V diode clamp. Ignore output compliance for conservatism.
        fault_v=(.010+3.25/(4700*.99))/(1/(resistance*1.01)+1/(4700*.99))
        fault_w=fault_v**2/(resistance*1.01)
        assert fault_w<.25*(155-85)/(155-70)
        rows.append(dict(channel=n,device=device,resistor_ref=ref,resistance_ohm=resistance,
                         nominal_volts_per_amp=round(resistance/d['ratio'],6),
                          nominal_voltage_at_fuse_max_v=round(fuse*resistance/d['ratio'],4),
                          sense_mpn=p.fields['MPN'],
                          fault_screen=dict(max_is_current_ma=10,assumed_clamp_v=3.25,
                                            sense_resistor_w=round(fault_w,4),
                                            series_resistor_w=round((fault_v-3.25)**2/(4700*.99),4),
                                            note='Conservative 0.25W at 70C ERJ-PA3 rating used; linear derating to 155C, screened at 85C. Clamp active, no external pin short.'),
                         published_test_current_a=d['test_a'],
                         voltage_bounds_at_published_test_current_v=[round(lower,4),round(upper,4)],
                         source=dict(url=f'https://www.infineon.com/assets/row/public/documents/10/49/infineon-{device.lower()}-datasheet-en.pdf',
                                     revision=d['revision'],page=d['page'],table=21)))
    return dict(status='normal_current_static_screen_passed_values_retained',
                circuit_sha256=hashlib.sha256((HERE/'circuit.py').read_bytes()).hexdigest(),
                resistor_tolerance_fraction=.01,channels=rows,
                limitations=['Tolerance bounds apply only at the listed datasheet test currents; no interpolation guarantee at fuse ratings',
                             'Nominal conversion ignores ADC error, ground offsets, filter loading and clamp leakage',
                             'Low-current ratio errors are larger; calibrate each assembled channel',
                              'Fault screen assumes active clamp; clamp dynamics, reverse polarity and transient behavior require bench tests'])


if __name__=='__main__':
    report=screen()
    path=HERE/'sense-screen.json';path.write_text(json.dumps(report,indent=2)+'\n')
    for r in report['channels']:
        print(f"CH{r['channel']} {r['device']} {r['resistance_ohm']:g} ohm: {r['nominal_voltage_at_fuse_max_v']} V nominal at fuse maximum")
