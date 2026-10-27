#!/usr/bin/env python3
"""Reproducible static screens for the protection candidate, not surge validation."""
import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def screen():
    # TI LM7480-Q1 SNOSD95C tables 7.5 and 7.6: full-temperature thresholds.
    # Divider uses two 49.9k, 0.1% resistors above 7.87k, 0.1%; split upper
    # leg keeps each 0805's applied voltage below 100 V at a 200 V input.
    high, low, tolerance, leakage = 99800., 7870., .001, .2e-6

    def thresholds(vmin, vmax):
        values = [v * (1 + top / bottom) + current * top
                  for v, top, bottom, current in itertools.product(
                      (vmin, vmax), (high*(1-tolerance), high*(1+tolerance)),
                      (low*(1-tolerance), low*(1+tolerance)), (-leakage, leakage))]
        return [round(min(values), 3), round(max(values), 3)]

    rising, falling = thresholds(1.195, 1.267), thresholds(1.091, 1.159)
    assert rising[0] > 16, 'Cutoff tolerance overlaps normal input range'
    assert rising[1] < 17.8, 'Static threshold exceeds nominal 16V TVS minimum breakdown'
    # At 80 V, treat the 51V zener as ideal for a nominal power screen only.
    # This is NOT a worst-case zener voltage/temperature/dynamic-impedance bound.
    current = (80 - 51) / 4700
    # Vishay 86573 rev 1.0: 52.02 V maximum at IZT=10 mA,
    # maximum temperature coefficient 0.12 %/K. This extrapolation is
    # conditional: actual bias is below IZT and the layout's RthJA is unknown.
    hot_zener = 52.02 * (1 + .0012 * (150 - 25))
    rmin = 4700 * .95
    zener_power_bound = 80**2 / (4*rmin)  # max Vz*(80-Vz)/R
    high_fet_loss = 40**2 * .0067 / 4
    low_fet_loss = 40**2 * .0016 / 2
    return dict(
        status='candidate_static_screen_not_transient_or_thermal_qualification',
        sources=dict(controller='TI LM7480-Q1 SNOSD95C, sections 7.5, 7.6, 10.3',
                     high_fet='Infineon IPT067N20NM6, rev 2.1, 2023-10-10',
                     shared_fuse='Mersen FR14GG50V40: 40A, 250VDC, 100kA at L/R=15ms; MR14SPRING clips 63A'),
        cutoff_rising_v=rising, cutoff_falling_v=falling,
        nominal_cutoff_v=round(1.231*(1+high/low), 3),
        nominal_80v_controller_feed=dict(current_a=round(current, 6),
                                       resistor_w=round(current**2 * 4700, 3),
                                        zener_w=round(current * 51, 3)),
        controller_zener_screen=dict(
            mpn='BZG03B51-M3_A-08',
            source='Vishay 86573 rev 1.0, 2025-10-24, pages 1-2',
            conditional_150c_voltage_v=round(hot_zener, 3),
            margin_to_65v_operating_limit_v=round(65-hot_zener, 3),
            max_available_zener_power_at_80v_w=round(zener_power_bound, 3),
            assumed_rthja_k_per_w=150,
            conditional_85c_ambient_junction_c=round(85+150*zener_power_bound, 1),
            assumptions='80 V DC, 4.7k resistor at -5%, nonnegative controller current, no other feed into clamp. Temperature extrapolation uses datasheet coefficient at test current; actual below-test-current clamp voltage and board thermal resistance require confirmation.'),
        mosfet_40a_conduction_screen_25c_10v_gate=dict(
            high_bank_w=round(high_fet_loss, 3), low_bank_w=round(low_fet_loss, 3),
            total_w=round(high_fet_loss+low_fet_loss, 3),
            assumptions='Equal parallel current sharing; max datasheet RDS(on) at 25C. No hot resistance or copper loss included.'),
        high_bank_gate_charge_screen=dict(max_charge_nc=4*107,
                                         minimum_driver_source_ua=39,
                                         charge_time_ms=round(4*107e-9/39e-6*1000, 3),
                                          note='Charge/current estimate, not a startup/SOA simulation.'),
        charge_pump_capacitance_screen=dict(
            source='TI SNOSD95C section 10.3.2.1; IPT067N20NM6 Table 5; BSC016N06NS dynamic characteristics',
            high_bank_max_ciss_nf=4*7.3,low_bank_max_ciss_nf=2*6.5,
            recommended_effective_capacitance_nf=10*(4*7.3+2*6.5),
            selected_c27_nominal_nf=1000,
            required_minimum_fraction_of_nominal=.422,
            note='C27 increased from 100nF to 1uF 50V X7R. Verify >=422nF effective capacitance at 15V including bias, temperature and tolerance; startup scope check remains part of first article.'),
        source_sha256={str(p.relative_to(HERE.parent)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in [HERE/'input_protection.py', HERE/'circuit.py',
                                 HERE/'requirements.json', Path(__file__)]},
        pending=['first-article fuse fit, fastener engagement and contact heating',
                 'supply zener limits including temperature and PCB cooling',
                 'surge rise time, cutoff overshoot and MOSFET SOA',
                 'gate-drive startup, recovery and current sharing',
                 'PCB/terminal/fuse thermal tests and aggregate current',
                 'upstream-fuse selectivity is not established',
                 'current distributor stock and complete pricing'])


if __name__ == '__main__':
    output = HERE / 'protection-screen.json'
    output.write_text(json.dumps(screen(), indent=2) + '\n')
    print(output)
