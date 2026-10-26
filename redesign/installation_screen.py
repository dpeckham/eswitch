#!/usr/bin/env python3
"""Cable-drop and prospective-fault screening, not fuse series qualification."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    path = HERE / 'requirements.json'
    requirements = json.loads(path.read_text())
    installation = requirements['installation']
    supply_length = 2 * installation['battery_to_board_one_way_m']
    pump_length = 2 * installation['board_to_pump_one_way_m']
    supply_area = installation['proposed_battery_feed']['area_mm2']
    pump_area = 4.0
    # Standard copper engineering approximation. Real cable resistance, splices,
    # fuse contacts, the board and pump pigtails must be measured separately.
    rho20 = .01724  # ohm mm2 / m
    alpha = .00393  # /degree C
    drops = []
    for temperature in (20, 75):
        rho = rho20 * (1 + alpha * (temperature - 20))
        supply_r = rho * supply_length / supply_area
        pump_r = rho * pump_length / pump_area
        common_drop = supply_r * requirements['aggregate_continuous_target_a']
        pump_drop = pump_r * 4.8
        drops.append(dict(copper_temperature_c=temperature,
                          supply_loop_resistance_ohm=supply_r,
                          pump_loop_resistance_ohm=pump_r,
                          supply_drop_at_40a_v=common_drop,
                          pump_drop_at_4_8a_v=pump_drop,
                          total_wire_only_drop_v=common_drop + pump_drop))
    # Deliberately ideal voltage source; omit source/BMS/contact resistance rather
    # than inventing an unpublished battery short-circuit specification. These
    # scenarios show why a 40 A fuse is not a 40 A instantaneous current ceiling.
    # They do NOT establish the actual source fault current or a certified bound.
    faults = []
    for temperature in (0, 20):
        resistance = rho20 * (1 + alpha * (temperature - 20)) * supply_length / supply_area
        for voltage in (14.6, requirements['input_voltage_v']['maximum']):
            faults.append(dict(source_voltage_v=voltage, copper_temperature_c=temperature,
                               ideal_source_wire_only_fault_current_a=voltage / resistance))
    report = dict(
        status='wire_drop_screened_fuse_coordination_unresolved',
        requirements_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        input=dict(supply_loop_m=supply_length, pump_loop_m=pump_length,
                   supply_area_mm2=supply_area, pump_area_mm2=pump_area,
                   common_current_a=40, pump_current_a=4.8),
        drops=drops, ideal_source_fault_scenarios=faults,
        installed_fuse_interrupting_ratings_a=dict(logic_0466002_NR=50, branch_287_ATOF=1000),
        conclusion='Cable lengths alone do not establish fault current below either onboard fuse interrupting rating. Require a documented source bound/series combination, or change protection architecture.',
        exclusions=['cable ampacity certification', 'fuse/terminal/PCB voltage drop',
                    'pump startup and locked-rotor current', 'transient voltage and inductance',
                    'BMS protection timing', 'fuse let-through energy and selectivity'],
    )
    destination = HERE / 'installation-screen.json'
    destination.write_text(json.dumps(report, indent=2) + '\n')
    print(destination)
    print('Wire-only drop at 75 C: %.3f V' % drops[-1]['total_wire_only_drop_v'])
    print('Ideal-source fault scenarios: %.0f to %.0f A' % (
        min(f['ideal_source_wire_only_fault_current_a'] for f in faults),
        max(f['ideal_source_wire_only_fault_current_a'] for f in faults)))


if __name__ == '__main__':
    main()
