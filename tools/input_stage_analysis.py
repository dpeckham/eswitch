#!/usr/bin/env python3
"""Reproducible tolerance/startup screening; never a fabrication approval.

See docs/input-protection-review.md for manufacturer sources and limitations.
The ideal limiting model omits gate dynamics, wiring inductance and load UVLO.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

import design

ROOT = Path(__file__).resolve().parent.parent


def divider(top, bottom, tolerance, threshold, bias):
    values = [v * (1 + rt/rb) + i*rt
              for rt, rb, v, i in itertools.product(
                  (top*(1-tolerance), top*(1+tolerance)),
                  (bottom*(1-tolerance), bottom*(1+tolerance)), threshold, bias)]
    return [min(values), max(values)]


def charge_time(vin, capacitance, full_voltage_load_a, power_limit, current_limit, auxiliary_a=0):
    """Integrate C*dV/dt = min(Ilim, Plim/Vds) - V/R for a resistor load.

    Returns infinity if the ideal limit cannot carry the resistor through its
    maximum MOSFET-dissipation point. Integration is to the full supply voltage.
    """
    if full_voltage_load_a >= current_limit or vin*full_voltage_load_a/4 >= power_limit:
        return math.inf
    steps = 20000
    dv = vin/steps
    time = 0.0
    for index in range(steps):
        output = (index+.5)*dv
        available = min(current_limit, power_limit/(vin-output)) - full_voltage_load_a*output/vin - auxiliary_a
        if available <= 0:
            return math.inf
        time += capacitance*dv/available
    return time


def power_bounds(top_ohm):
    """TI power-engine +/-32% screen, including REF, divider, bias and shunt."""
    prog = [v*rb/(rt+rb) + bias*rt*rb/(rt+rb)
            for v, rt, rb, bias in itertools.product(
                (3.9, 4.1), (top_ohm*.99, top_ohm*1.01),
                (1000*.99, 1000*1.01), (-5e-6, 5e-6))]
    return ([min(prog), max(prog)],
            [.5*min(prog)/.00101*(17/25), .5*max(prog)/.00099*(33/25)])


def timer_bounds(capacitance):
    return [capacitance*.95*3.9/36e-6, capacitance*1.05*4.1/17e-6]


def constant_load_charge_time(vin, capacitance, load_a, power_limit, current_limit):
    """Conservative current-load envelope, including current at zero bus voltage."""
    if load_a >= min(current_limit, power_limit/vin):
        return math.inf
    dv = vin/20000
    return sum(capacitance*dv/(min(current_limit, power_limit/(vin-(n+.5)*dv))-load_a)
               for n in range(20000))


def resistor_power_equilibria(vin, full_voltage_load_a, power_limit):
    """Roots of Vout*(Vin-Vout)/R = Plim; low root blocks a rising output.

    Only describes the power-limit branch; current limit is checked separately.
    """
    if full_voltage_load_a <= 0 or power_limit > vin*full_voltage_load_a/4:
        return []
    delta = math.sqrt(max(0, vin**2 - 4*power_limit*vin/full_voltage_load_a))
    return [(vin-delta)/2, (vin+delta)/2]


def analyze():
    parts = {p.ref: p for p in design.build()}
    expected = {"R12": "115k 0.1%", "R13": "10k 0.1%", "R14": "56.2k 0.1%",
                "R15": "10k 0.1%", "R17": "8.25k 1%", "R18": "1k", "C18": "10nF 50V C0G 5%"}
    for ref, value in expected.items():
        assert parts[ref].value == value, f"Update analysis for changed {ref}"
    assert parts["R20"].fields["MPN"] == "CSS4J-4026R-1L00F"
    assert parts["U14"].fields["MPN"] == "TPS2492PWR"
    shunt = (.001*.99, .001*1.01)
    current = [.045/shunt[1], .055/shunt[0]]
    # 17/25 and 33/25 are the power-engine test-point ratios, NOT an additional
    # independent +/-10% current-limit tolerance. Do not count it twice.
    prog, power = power_bounds(8250)
    timer = timer_bounds(10e-9)
    cases = []
    for vin, load, cap in itertools.product((9.5, 12.0, 16.0), (0, 20, 30, 40), (470e-6, 1000e-6)):
        seconds = charge_time(vin, cap, load, power[0], current[0])
        cases.append(dict(input_v=vin, resistive_load_at_full_voltage_a=load, capacitance_uf=cap*1e6,
                          ideal_charge_ms=None if math.isinf(seconds) else seconds*1000,
                          result="stalls" if math.isinf(seconds) else
                          "exceeds_minimum_timer" if seconds >= timer[0] else "ideal_model_only_pass"))
    # Independent check against TI's unloaded piecewise closed-form equation.
    expected_time = .001*power[0]/(2*current[0]**2) + .001*16**2/(2*power[0])
    assert math.isclose(charge_time(16, .001, 0, power[0], current[0]), expected_time, rel_tol=1e-7)
    # Independent resistor-loaded closed form with power limit inactive.
    expected_loaded = -.001*16/40*math.log(1-40/current[0])
    assert math.isclose(charge_time(16, .001, 40, 10000, current[0]),
                        expected_loaded, rel_tol=1e-7)
    equilibria = resistor_power_equilibria(16, 40, power[0])
    for voltage in equilibria:
        assert math.isclose(voltage*(16-voltage)/.4, power[0], rel_tol=1e-12)
    startup_envelope = []
    for vin in (9.5, 12, 16):
        for load_kind, amps in (("resistive", 20), ("constant_current_upper_bound", 5)):
            fn = charge_time if load_kind == "resistive" else constant_load_charge_time
            auxiliary = 2 if load_kind == "resistive" else 0
            duration = fn(vin, 220e-6, amps, power[0], current[0], **({"auxiliary_a": auxiliary} if auxiliary else {}))
            budget = 10e-9*.95*(3.9-1.04)/36e-6
            assert duration*1.25 < budget
            startup_envelope.append(dict(input_v=vin, load_model=load_kind,
                                         full_voltage_load_a=amps, auxiliary_current_bound_a=auxiliary,
                                         maximum_total_capacitance_uf=220,
                                         ideal_charge_ms=duration*1000,
                                         timer_budget_at_1_04v_ms=budget*1000,
                                         timer_to_charge_ratio=budget/duration))
    alternatives = []
    for top, timer_nf in ((8250, 10), (6810, 100), (6190, 47), (5620, 33), (5110, 27)):
        _, limits = power_bounds(top)
        times = timer_bounds(timer_nf*1e-9)
        startup = charge_time(16, .001, 40, limits[0], current[0])
        alternatives.append(dict(
            r17_ohm=top, c18_nf=timer_nf,
            power_limit_screen_w=limits,
            timer_from_zero_ms=[t*1000 for t in times],
            ideal_16v_40a_1000uf_charge_ms=None if math.isinf(startup) else startup*1000,
            minimum_timer_to_ideal_charge_ratio=None if math.isinf(startup) else times[0]/startup,
            limited_fault_energy_screen_j=limits[1]*times[1],
            status="fitted_unqualified" if top == 8250 else "unselected_not_soa_approved"))
    return dict(
        status="engineering_screening_not_qualified",
        design_sha256=hashlib.sha256((ROOT/"tools/design.py").read_bytes()).hexdigest(),
        component_values={ref: parts[ref].value for ref in (*expected, "R20", "U14")},
        sources={"controller": "https://www.ti.com/lit/gpn/TPS2492",
                 "mosfet": "https://assets.nexperia.com/documents/data-sheet/PSMN1R8-80SSE.pdf",
                 "shunt": "https://bourns.com/docs/product-datasheets/css4j-4026.pdf",
                 "ti_power_accuracy_clarification": "https://e2e.ti.com/support/power-management-group/power-management/f/power-management-forum/1074250/tps2492-how-precise-is-the-constant-power-engine-what-measurement-method-will-best-match-the-designed-power-limit"},
        assumptions=["Initial resistor/capacitor tolerance; temperature drift and ageing not included",
                     "Controller min/max electrical characteristics across its specified temperature range",
                     "Power-engine 17/25..33/25 ratios extrapolated from published test points; not a guaranteed limit at this PROG setting",
                     "Resistive BYPASS load only; arbitrary constant-power loads and motors are not represented",
                     "Ideal instantaneous limiting; no gate-charge delay, parasitics, overshoot or timer residual charge"],
        current_limit_a=current,
        prog_v=prog,
        nominal_power_limit_w=.5*(4*1000/9250)/.001,
        power_limit_screen_w=power,
        timer_from_zero_ms=[t*1000 for t in timer],
        timer_residual_sensitivity=[dict(initial_timer_v=v,
                                        minimum_remaining_ms=10e-9*.95*(3.9-v)/36e-6*1000)
                                    for v in (0, 1.04, 2, 3)],
        startup_design_envelope=dict(
            status="prototype_validation_target_not_measured_rating",
            owner_decision="Lower startup load/latch-off accepted; 40 A continuous target retained",
            total_capacitance_definition="Maximum actual bus plus connected-load capacitance, including tolerance; not nominal part markings",
            load_models_are_alternatives_not_additive=True,
            initial_timer_v_max=1.04,
            note="Require TIMER at or below 1.04 V before evaluating successful startup; arbitrary rapid brownouts or residual charge above this may latch off. Gate dynamics require the separate transient review.",
            cases=startup_envelope),
        ov_rising_v=divider(115000, 10000, .001, (1.31, 1.39), (-1e-6, 1e-6)),
        uv_rising_v=divider(56200, 10000, .001, (1.31, 1.39), (-1e-6, 1e-6)),
        shunt_dissipation_at_40a_w=[1600*r for r in shunt],
        maximum_resistive_start_load_at_16v_a=4*power[0]/16,
        stall_example=dict(input_v=16, resistance_ohm=.4,
                           full_voltage_current_a=40,
                           peak_required_fet_power_w=160,
                           power_branch_equilibrium_output_v=equilibria,
                           low_equilibrium_load_a=equilibria[0]/.4,
                           note="Predicted by the ideal low-power model, not a measured board failure; real gate dynamics and timer can interrupt sooner"),
        unselected_setting_comparisons=alternatives,
        limited_fault_energy_screen_j=power[1]*timer[1],
        gate_charge_reference={"two_fet_max_qg_nc_at_datasheet_test_point": 816,
                               "q_over_minimum_source_current_ms": 816e-9/15e-6*1000,
                               "note": "Charge arithmetic only, not a startup duration bound; timer runs only while limiting"},
        startup_cases=cases,
        production_validation_required=["Measure the lower startup envelope; full 40 A startup is not required",
                          "Validate the separate single-FET SOA sensitivity study with measured gate/startup/live-short waveforms",
                          "Qualify clamps, negative OUT excursion and cable/load energy for the actual fixture and installation",
                          "Characterize UVEN/UVLO brownout latch reset and residual TIMER charge"],
    )


def plot(result):
    """Optional explanation artifact; matplotlib is not a verification dependency."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    volts = [i*16/400 for i in range(401)]
    watts = [v*(16-v)/.4 for v in volts]
    fig, ax = plt.subplots(figsize=(9, 5.2), layout="constrained")
    ax.plot(volts, watts, color="#164b73", linewidth=2.5,
            label="Pass-FET power needed by 0.4 Ω load")
    ax.axhline(result["power_limit_screen_w"][0], color="#b04434", linestyle="--",
               label="Current setting: screened low limit (137.9 W)")
    ax.axhline(result["nominal_power_limit_w"], color="#57926d", linestyle=":",
               label="Current setting: nominal limit (216.2 W)")
    eq = result["stall_example"]["power_branch_equilibrium_output_v"][0]
    ax.scatter([eq], [result["power_limit_screen_w"][0]], color="#b04434", zorder=5)
    ax.annotate(f"Rising output stalls here: {eq:.2f} V", (eq, 137.93),
                xytext=(.6, 177), arrowprops={"arrowstyle": "->", "color": "#b04434"})
    ax.set(xlim=(0, 16), ylim=(0, 235), xlabel="Output voltage during startup (V)",
           ylabel="Power dissipated in pass MOSFETs (W)",
           title="Why a board that carries 40 A can fail to start a 40 A load")
    ax.grid(alpha=.2)
    ax.legend(loc="lower center", fontsize=9)
    fig.supxlabel("16 V input • resistor load only • ideal screening model, not measured or qualified", fontsize=9)
    target = ROOT/"out/review/input-startup-stall.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=160)
    fig.savefig(target.with_suffix(".pdf"))
    plt.close(fig)
    print(target.relative_to(ROOT))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check saved calculations; does not approve the design")
    parser.add_argument("--plot", action="store_true", help="Export explanatory PNG and PDF")
    args = parser.parse_args()
    result = analyze()
    target = ROOT/"docs/input-stage-calculations.json"
    rendered = json.dumps(result, indent=2, allow_nan=False)+"\n"
    if args.check:
        if not target.exists() or target.read_text() != rendered:
            raise SystemExit("Input-stage calculation is stale; run tools/input_stage_analysis.py")
        print("Input-stage calculation matches fitted design; engineering blockers remain open")
    else:
        target.write_text(rendered)
        print(target.relative_to(ROOT))
    if args.plot:
        plot(result)
