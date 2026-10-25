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
    # Compact-board DC screen. Credit F.Cu only: In2 has signal crossings.
    # Filled spine samples retain >4.9mm; reserve 4.5mm effective width.
    # Return uses In1 only with an assumed 20mm effective width, not a solved
    # spreading-resistance/temperature model.
    rho20=.0175  # ohm mm2 / metre
    rho80=rho20*(1+.00393*60)
    spine_length,bus_length,return_length=.030,.075,.100
    raw_r=rho80*(spine_length/(4.5*.070)+bus_length/(14*.070))
    ground_r=rho80*return_length/(20*.061)
    return dict(status='analytical_screen_requires_transient_and_bench_validation',
                input_scope='Correct polarity, 9.5–16V continuous; no electronic reverse/OV disconnect',
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
                trunk_screen=dict(copper_temperature_c=80,board_mm=[136,104],
                                  raw_spine_length_m=spine_length,raw_spine_width_mm=4.5,
                                  raw_bus_length_m=bus_length,raw_bus_width_mm=14,
                                  return_length_m=return_length,return_effective_width_mm=20,
                                  raw_single_layer_r_ohm=raw_r,ground_plane_r_ohm=ground_r,
                                  drop_at_40a_v=40*(raw_r+ground_r),
                                  full_length_40a_loss_w=40**2*(raw_r+ground_r),
                                  caveats=['Conservative full 40A over full length, actual current is distributed',
                                           'Excludes contact, fuse, via, spreading and unsampled local neck resistance',
                                           'No inner-layer current-sharing credit; inner raw copper has signal crossings',
                                           'Compact VS heat-spreader area is smaller; junction temperature remains unqualified',
                                           'Final filled geometry must preserve the assumed conductor paths']),
                sources=['https://www.ti.com/lit/ds/symlink/tla431.pdf',
                         'https://www.infineon.com/assets/row/public/documents/10/49/infineon-bts7004-1epp-datasheet-en.pdf',
                         'https://www.infineon.com/assets/row/public/documents/10/49/infineon-bts7008-1epr-datasheet-en.pdf',
                         'https://www.infineon.com/assets/row/public/documents/10/49/infineon-bts7002-1epp-datasheet-en.pdf'])


if __name__=='__main__':
    result=analyze()
    (HERE/'electrical-screen.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['logic_shunt'],indent=2))
