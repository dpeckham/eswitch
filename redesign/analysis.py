#!/usr/bin/env python3
"""Transparent DC/energy screens for the simple design; no fabricated bench data."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def analyze():
    # TLA431A: initial limits, full I-grade 17mV drift allowance, and a 30mA
    # current swing times 0.5ohm maximum dynamic impedance as a DC screen.
    low,high=2.470-.017-.5*.03,2.520+.017+.5*.03
    bias_min=(3.3*.99-high)/(2200*1.01)-high/(47000*.99)
    assert bias_min>.0002,(bias_min,'Insufficient shunt bias')
    # 0.65V is an engineering forward-drop allowance at a few mA, including
    # cold operation. Validate exact diode/ADC pin levels on the prototype.
    adc_high=high+.65
    assert adc_high<3.3*.99
    # Maximum continuous input is 16V. Ignore sense-shunt diversion and diode
    # drop to overestimate rail injection. This is not an input surge bound.
    injection=8*(16-low)/(4700*.99)
    assert injection<.03 and injection<.1
    # Known X7R initial tolerances: 100nF K and 47nF K, conservatively +10%.
    cap=(100e-9+47e-9)*1.1
    # RDS(on), 150C maxima from each selected PROFET datasheet. Fuse amperage
    # is a screening current, NOT a continuous fuse/load qualification.
    channels=[]
    for n,(amps,rds,rsense) in enumerate([(10,.008,2200),(10,.008,2200),
                                        *[(5,.016,3300)]*5,(20,.0048,1200)],1):
        channels.append(dict(channel=n,fuse_max_a=amps,screen_current_a=amps,
                             profet_hot_rds_max_ohm=rds,profet_loss_at_screen_a_w=amps**2*rds,
                             disabled_is_voltage_screen_v=.5e-6*rsense*1.01,
                             fitted_vs_capacitance_max_f=cap,
                             fitted_vs_capacitor_energy_at_16v_j=.5*cap*16**2))
    return dict(status='analytical_screen_requires_transient_and_bench_validation',
                input_scope='9.5–16V continuous; shared LM74800 AUTO/logic cutoff; raw passive BYPASS is unprotected against overvoltage/reversal',
                logic_shunt=dict(part='TLA431AIDBZR',nominal_v=2.495,
                                 screened_min_v=low,screened_max_v=high,
                                 minimum_quiescent_cathode_bias_a=bias_min,
                                 adc_high_voltage_screen_v=adc_high,
                                 continuous_injection_bound_a=injection,
                                 clamp_dissipation_bound_w=high*injection,
                                 bias_input_power_at_3v3_w=3.3*(3.3-2.495)/2200,
                                 caveats=['DC screen only; startup/dynamic overshoot must be measured',
                                          'OFF-state ADC safety also depends on local DEN pull-downs and disabled IS leakage',
                                          'An abnormally driven sense pin can still feed an unpowered MCU through its internal pin clamp',
                                          'Diode cold forward-drop allowance is a screening assumption, not a guaranteed device limit',
                                          'No claim that arbitrary dead hardware is isolated by this clamp']),
                channels=channels,
                trunk_screen=dict(status='requires_resistance_current_sharing_and_thermal_solution',
                                  geometry_report='power-copper-review.json',
                                  caveats=['The former 4.5mm feed / 20mm return lumped model is withdrawn',
                                           'Connected-path widths do not establish current capacity',
                                           'Include pad lands, plated barrels, fuse/contact resistance and simultaneous channel loads',
                                           '40A aggregate and 20A CH8 remain unqualified targets']),
                sources=['https://www.ti.com/lit/ds/symlink/tla431.pdf',
                         'https://www.infineon.com/assets/row/public/documents/10/49/infineon-bts7004-1epp-datasheet-en.pdf',
                         'https://www.infineon.com/assets/row/public/documents/10/49/infineon-bts7008-1epr-datasheet-en.pdf',
                         'https://www.infineon.com/assets/row/public/documents/10/49/infineon-bts7002-1epp-datasheet-en.pdf'])


if __name__=='__main__':
    result=analyze()
    (HERE/'electrical-screen.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['logic_shunt'],indent=2))
