#!/usr/bin/env python3
"""TI controller + deliberately approximate MOSFET sensitivity study.

Not a manufacturer MOSFET model, parasitic extraction, or production qualification.
Run with --run; --check checks saved evidence without requiring SPICE or numpy.
"""
import argparse
import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out/input-spice"
RESULT = ROOT / "docs/input-transient-calculations.json"
MODEL = ROOT / "out/datasheets/tps2492-model.lib"
MODEL_URL = "https://www.ti.com/lit/zip/slum134"
MODEL_SHA = "994c38cb2283deb80f90b42911a60f20f5f6d670d7d07c9b60672d16b5f993cb"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    return {name: digest(ROOT/name) for name in
            ("tools/design.py", "tools/input_stage_transient.py",
             "docs/evidence/input-mosfet-soa.json", "docs/input-stage-calculations.json")}


def soa_current(curve, voltage):
    points = curve["vector_points_v_a"]
    for (v1, i1), (v2, i2) in zip(points, points[1:]):
        if v1 <= voltage <= v2 and v2 > v1:
            return math.exp(math.log(i1) + math.log(voltage/v1)/math.log(v2/v1)*math.log(i2/i1))
    raise ValueError(f"Outside extracted SOA graph: {voltage}")


def make_model(original, corner):
    fast = corner == "low"
    pairs = [("2.7e-6", "1.5e-6"), ("29.7e-6", "37.5e-6" if fast else "18.5e-6"),
             ("TH=2.5 HYS=3.0", "TH=2.43 HYS=2.94" if fast else "TH=2.57 HYS=3.06"),
             (")),0.05)", ")),0.045)" if fast else ")),0.055)")]
    for old, new in pairs:
        assert old in original, old
        original = original.replace(old, new)
    return original


def run(ngspice):
    import numpy as np
    OUT.mkdir(parents=True, exist_ok=True)
    if not MODEL.exists():
        archive = OUT/"ti-model.zip"
        urllib.request.urlretrieve(MODEL_URL, archive)
        with zipfile.ZipFile(archive) as z:
            MODEL.parent.mkdir(parents=True, exist_ok=True)
            MODEL.write_bytes(z.read("TPS2492_PSPICE_TRANS/TPS2492_TRANS.LIB"))
    assert digest(MODEL) == MODEL_SHA, "TI model changed; review before using"
    original = MODEL.read_text()
    env = dict(os.environ)
    local = ROOT/"out/ngspice-local/usr/lib/x86_64-linux-gnu"
    if local.exists():
        env["LD_LIBRARY_PATH"] = str(local)
        env["SPICE_SCRIPTS"] = str(OUT)
        (OUT/"spinit").write_text("set ngbehavior=ps\n" + "\n".join(
            "codemodel " + str(p) for p in sorted(local.rglob("*.cm"))) + "\n")
    else:
        raise SystemExit("Configure ngspice PSpice compatibility/codemodels before running this study")
    calculation = json.loads((ROOT/"docs/input-stage-calculations.json").read_text())
    soa = json.loads((ROOT/"docs/evidence/input-mosfet-soa.json").read_text())
    cases = []
    for corner in ("low", "high"):
        for kind in ("20a_resistor", "40a_resistor", "short", "5a_current"):
            cases.append(dict(name=corner+"_"+kind, corner=corner, kind=kind,
                              vin=16, cgs_nf=50, kp=8, gate_ua=15))
    cases += [dict(name="slow_high_short", corner="high", kind="short", vin=16,
                   cgs_nf=100, kp=4, gate_ua=15),
              dict(name="fast_high_short", corner="high", kind="short", vin=16,
                   cgs_nf=35, kp=20, gate_ua=35),
              dict(name="slow_low_20a", corner="low", kind="20a_resistor", vin=16,
                   cgs_nf=100, kp=4, gate_ua=15),
              dict(name="low_voltage_20a", corner="low", kind="20a_resistor", vin=9.5,
                   cgs_nf=100, kp=4, gate_ua=15)]

    def simulate(case):
        name = case["name"]
        low = case["corner"] == "low"
        shunt = .00101 if low else .00099
        power = calculation["power_limit_screen_w"][0 if low else 1]
        model = make_model(original, case["corner"])
        model = model.replace("2.2e-5", str(case["gate_ua"]*1e-6))
        model = model.replace("(14,22u)", f"(14,{case['gate_ua']}u)")
        (OUT/(name+".lib")).write_text(model)
        load = {"20a_resistor": f"Rl bus 0 {case['vin']/20}",
                "40a_resistor": f"Rl bus 0 {case['vin']/40}",
                "short": "Rl bus 0 .001",
                "5a_current": "Bl bus 0 I=5*tanh(V(bus)/.1)"}[case["kind"]]
        if case["kind"].endswith("resistor"):
            load += "\nBaux bus 0 I=2*tanh(V(bus)/.1)"
        circuit = f"""Input-stage sensitivity only; NOT manufacturer MOSFET model
.param TPS=1
.include {name}.lib
Vin vin 0 PWL(0 0 100u 0 101u {case['vin']})
Rs vin sense {shunt}
Xu vref flt nc ov gate pg prog timer vin imon sense uven bus 0 TPS2492_TRANS
Ruv1 vin uven 56.2k
Ruv2 uven 0 10k
Rov1 vin ov 115k
Rov2 ov 0 10k
* Effective PROG scales the power-engine corner; not a fitted resistor change.
Vprog prog 0 {2*shunt*power}
Ct timer 0 {9.5e-9 if low else 10.5e-9}
Rg1 gate g1 10
Rg2 gate g2 10
M1 d1 g1 bus bus fet1
M2 d2 g2 bus bus fet2
Rd1 sense d1 1.9m
Rd2 sense d2 1.9m
Cgs1 g1 bus {case['cgs_nf']}n
Cgs2 g2 bus {case['cgs_nf']}n
Cgd1 g1 d1 2n
Cgd2 g2 d2 2n
.model fet1 NMOS level=1 VTO=1.6 KP={case['kp']} LAMBDA=0
.model fet2 NMOS level=1 VTO=2.2 KP={case['kp']} LAMBDA=0
Cl bus 0 220u
{load}
Rflt vref flt 100k
Rpg vref pg 100k
.options method=trap reltol=1e-3 abstol=1e-8 vntol=1e-5 rshunt=1e12 cshunt=1e-12
.control
set wr_singlescale
set wr_vecnames
tran 2u 200m
wrdata {name}.tsv v(bus) v(gate) v(timer) i(Vin) v(sense) v(d1) v(d2)
quit
.endc
.end
"""
        (OUT/(name+".cir")).write_text(circuit)
        logfile = OUT/(name+".log")
        with logfile.open("w") as log:
            subprocess.run([str(ngspice), "-b", name+".cir"], cwd=OUT, env=env,
                           stdout=log, stderr=log, timeout=120, check=True)
        log = logfile.read_text()
        assert "aborted" not in log and "Error" not in log, logfile
        x = np.loadtxt(OUT/(name+".tsv"), skiprows=1)
        t, v, gate, timer, source_i, sense, d1, d2 = x.T
        assert abs(t[-1]-.2) < 1e-9, "Incomplete transient"
        current = np.maximum(0, (2*sense-d1-d2)/.0019)
        vds = np.maximum(0, sense-v)
        power_w = vds*current
        # Deliberately attribute ALL pass current to ONE device, independent of model sharing.
        k = (175-soa["mounting_base_limit_c"])/150*.9
        mask = (vds >= 1) & (current > .01)
        dc_ratio = np.zeros(len(t))
        pulse_ratio = np.zeros(len(t))
        for index in np.flatnonzero(mask):
            dc_ratio[index] = current[index]/(k*soa_current(soa["curves"]["DC"], vds[index]))
            pulse_ratio[index] = current[index]/(k*soa_current(soa["curves"]["100ms"], vds[index]))
        above_dc = np.flatnonzero(dc_ratio > 1)
        # If DC is exceeded, count the WHOLE event from t=0, including gate delay
        # and preheating below DC. Never use just the above-DC interval as pulse width.
        stress = np.flatnonzero(power_w > 1)
        span_ms = 0 if len(above_dc) == 0 else t[stress[-1]]*1000
        on = bool(v[-1] > case["vin"]*.9)
        expect_on = case["kind"] in ("20a_resistor", "5a_current") or (not low and case["kind"]=="40a_resistor")
        assert on == expect_on, (name, v[-1], expect_on)
        assert pulse_ratio.max() < 1 and span_ms < 100, (name, pulse_ratio.max(), span_ms)
        return dict(**case, final_bus_v=float(v[-1]), starts=on,
                    peak_total_pass_power_w=float(power_w.max()), peak_source_current_a=float((-source_i).max()),
                    peak_timer_v=float(timer.max()), total_pass_energy_200ms_j=float(np.trapezoid(power_w,t)),
                    max_single_fet_100ms_soa_utilization=float(pulse_ratio.max()),
                    entire_event_window_if_dc_exceeded_ms=float(span_ms), completed_simulation_s=float(t[-1]),
                    netlist_sha256=digest(OUT/(name+".cir")), modified_model_sha256=digest(OUT/(name+".lib")))

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(simulate, cases))
    record = dict(status="prototype_design_screen_pass_not_hardware_qualification",
                  sources=sources(), controller_model_url=MODEL_URL, controller_model_sha256=MODEL_SHA,
                  simulator=subprocess.check_output([str(ngspice), "--version"], env=env, text=True).strip(),
                  mounting_base_limit_c=60, total_bus_capacitance_uf=220,
                  auxiliary_current_on_resistive_cases_a=2, cases=results,
                  limitations=["Level-1 MOSFET approximations with deliberately increased fixed capacitances; not manufacturer models or guaranteed parameter bounds",
                               "KP 4..20 A/V^2, Cgs 35..100 nF per device, Cgd 2 nF; thresholds 1.6/2.2 V. These are sensitivity assumptions",
                               "Level-1 on-resistance does not reproduce the selected part; no steady-state thermal rating inferred",
                               "TI nominal PSpice model ported to ngspice; controller corners deliberately perturbed; temperature effects absent in original model",
                               "Ideal source and 1 milliohm startup short; no extracted wiring, fault-current overshoot, live short or negative-bus waveform qualification",
                               "SOA comparison uses total pass-stage current on one FET, 60 C mounting base and 10% graph reserve; below 1 V excluded from graph comparison",
                               "No production release or installation transient rating; first-board scope and thermal measurements remain required"])
    RESULT.write_text(json.dumps(record, indent=2)+"\n")
    for r in results:
        print(f"{r['name']}: {'starts' if r['starts'] else 'latches'}; peak {r['peak_total_pass_power_w']:.1f} W; "
              f"SOA use {r['max_single_fet_100ms_soa_utilization']:.3f}; full event window {r['entire_event_window_if_dc_exceeded_ms']:.2f} ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--ngspice", type=Path, default=ROOT/"out/ngspice-local/usr/bin/ngspice")
    args = parser.parse_args()
    if args.run:
        run(args.ngspice.resolve())
    else:
        record = json.loads(RESULT.read_text())
        assert record["sources"] == sources(), "Transient evidence is stale"
        assert len(record["cases"]) == 12
        assert all(r["completed_simulation_s"] == .2 and r["max_single_fet_100ms_soa_utilization"] < 1
                   and r["entire_event_window_if_dc_exceeded_ms"] < 100 for r in record["cases"])
        print("Transient sensitivity evidence matches design; hardware qualification remains open")
