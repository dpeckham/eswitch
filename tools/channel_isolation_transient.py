#!/usr/bin/env python3
"""Three-controller revision C transient sensitivity study using TI TPS2492 model.

Includes source and short-loop parasitics, common PG interlock, finite gate
charge, local freewheel clamps and separate healthy load. This is prototype
design evidence, not a measured guarantee for unspecified installation wiring.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from input_stage_transient import MODEL,MODEL_SHA,make_model,soa_current
from channel_isolation_analysis import analyze

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'out/isolation-spice'
RESULT=ROOT/'docs/channel-isolation-transients.json'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def thermal_soa(curve,vds):
    # The rising left edge is RDS(on) at the hot junction, not a thermal
    # failure boundary for a cooler FET. Project low-VDS points to the knee:
    # the same current at a HIGHER voltage is a conservative SOA comparison.
    knee=max(curve['vector_points_v_a'],key=lambda p:p[1])[0]
    return soa_current(curve,max(vds,knee))


def sources():
    return {str(p):sha(ROOT/p) for p in ['tools/design.py','tools/revision_c.py',
            'tools/channel_isolation_analysis.py','tools/channel_isolation_transient.py',
            'docs/evidence/input-mosfet-soa.json']}


def run():
    OUT.mkdir(parents=True,exist_ok=True)
    original=MODEL.read_text(); assert sha(MODEL)==MODEL_SHA
    calc=analyze(); soa=json.loads((ROOT/'docs/evidence/input-mosfet-soa.json').read_text())
    env=dict(os.environ)
    lib=ROOT/'out/ngspice-local/usr/lib/x86_64-linux-gnu'
    env['LD_LIBRARY_PATH']=str(lib); env['SPICE_SCRIPTS']=str(OUT)
    (OUT/'spinit').write_text('set ngbehavior=ps\n'+'\n'.join(
        'codemodel '+str(p) for p in sorted(lib.rglob('*.cm')))+'\n')
    ng=ROOT/'out/ngspice-local/usr/bin/ngspice'
    cases=[dict(n=n,corner=corner,kind=kind,vin=16,cgs_nf=50,gate_ua=15)
           for n in (1,3,8) for corner in ('low','high') for kind in ('start','short','live')]
    cases += [dict(n=n,corner='high',kind='live',vin=9.5,cgs_nf=100,gate_ua=15)
              for n in (1,3,8)]
    cases += [dict(n=8,corner='high',kind='live',vin=16,cgs_nf=35,gate_ua=35)]
    cases += [dict(n=8,corner='high',kind='live',vin=9.5,cgs_nf=50,gate_ua=15)]
    if os.environ.get('ISOLATION_CASE'):
        cases=[c for c in cases if f"ch{c['n']}_{c['corner']}_{c['kind']}_{c['vin']}_{c['cgs_nf']}"==os.environ['ISOLATION_CASE']]
        assert cases

    def sim(c):
        n=c['n']; name=f"ch{n}_{c['corner']}_{c['kind']}_{c['vin']}_{c['cgs_nf']}"
        low=c['corner']=='low'; idx=0 if low else 1
        branch=calc['branches'][n-1]
        rs=branch['shunt_ohm']*(1.06 if low else .94)
        rms=.0005*(1.025 if low else .975)
        pm=calc['power_limit_screen_w'][idx]; pb=branch['power_limit_screen_w'][idx]
        model=make_model(original,c['corner']).replace('2.2e-5',str(c['gate_ua']*1e-6)).replace('(14,22u)',f"(14,{c['gate_ua']}u)")
        # PSpice '^' means Boolean XOR here; ngspice interprets it as power.
        # Explicit unequal Boolean operands preserve both monostable truth tables.
        assert model.count('V(YTD) > 0.5 ^ V(IN) > .5') == 2
        model=model.replace('V(YTD) > 0.5 ^ V(IN) > .5',
                            '(V(YTD)>0.5) != (V(IN)>.5)')
        model=model.replace('.param TPS=0','.param TPS=1')
        model=model.replace('SD_STRONG 0 125e-3','SD_STRONG 0 75e-3')
        model=model.replace('TH=8.35 HYS=0.1','TH=8.775 HYS=0.05')
        native_table_model=model
        # Same continuous piecewise-linear I/V law and endpoint clamps;
        # use the behavioral-source solver instead of XSPICE TABLE.
        model=model.replace('G1 A C TABLE { V(A, C) } ( (-1,-1n)(0,0)(1m,1) (2m,10) (3m,1000) )',
                'G1 A C VALUE={IF(V(A,C)<-1,-1n,IF(V(A,C)<0,V(A,C)*1n,IF(V(A,C)<.001,V(A,C)*1000,IF(V(A,C)<.002,1+(V(A,C)-.001)*9000,IF(V(A,C)<.003,10+(V(A,C)-.002)*990000,1000)))))}')
        model_path=OUT/(name+'.lib')
        models=[native_table_model,model]
        model_matches=model_path.exists() and model_path.read_text() in models
        rating=10 if n==8 else branch['fuse_a']; healthy=40-rating if c['kind']=='start' else 40
        # Start: channel-rated resistive load plus maximum actual 1000uF.
        # Short/live: output cable and 10mOhm short; fault loop closes before
        # turn-on or at 100ms. Controller fault must not reset the common bus.
        when='0' if c['kind']=='short' else '.1'
        load=f'Rload out 0 {c["vin"]/rating}\nCload out 0 1000u'
        if c['kind']!='start':
            load=f'''Rload out 0 1meg
Lfault out short_in 100n
Rfault short_in swfault 10m
Sfault swfault 0 fault_ctrl 0 sw
Vfault fault_ctrl 0 PWL(0 0 {when} 0 {float(when)+1e-7} 1)
.model sw SW(Ron=.0001 Roff=1e12 Vt=.5 Vh=.1)'''
        text=f'''Two TPS2492 independent channel isolation sensitivity
.include {name}.lib
Vs source 0 PWL(0 0 100u 0 1m {c['vin']+.005*(healthy+2)})
Rsource source input_l 5m
Lsource input_l vin 1u
Cin vin 0 100n
Rm vin main_sense {rms}
Xm mref mflt mnc ov mgate mpg mprog mtimer vin mim main_sense uven bus 0 TPS2492_TRANS
Ruv1 vin uven 56.2k
Ruv2 uven 0 10k
Rov1 vin ov 115k
Rov2 ov 0 10k
Vmprog mprog 0 {2*rms*pm}
Cmt mtimer 0 {36e-9*(.945 if low else 1.055)}
Rmg1 mgate mg1 10
Rmg2 mgate mg2 10
Mma md1 mg1 bus bus fet
Mmb md2 mg2 bus bus fet
Rmd1 main_sense md1 1.8m
Rmd2 main_sense md2 1.8m
Cmg1 mg1 bus {c['cgs_nf']}n
Cmg2 mg2 bus {c['cgs_nf']}n
Cmgd1 mg1 md1 2n
Cmgd2 mg2 md2 2n
Cmds1 md1 bus 3n
Cmds2 md2 bus 3n
Rbulk bus cap 2m
Cbulk cap 0 {3456 if c['kind']=='start' else 2304}u
Cbus bus 0 22u
Dmain 0 bus clamp
Bhealthy bus 0 I={(healthy-10)/c['vin']}*V(bus)*min(1,max(0,(V(brenable)-2)*10))
Baux bus 0 I=2*tanh(V(bus)/.1)
* Actual PG inverter and reference loading; no MCU or 3V3 dependency.
Rbase mpg qbase 10k
Rbe qbase mref 47k
Qenable brenable qbase mref pnp
Renable brenable 0 47k
Ren brenable en 47k
Rrefload mref 0 9.25k
Rb bus bsense {rs}
Xb bref bflt bnc 0 bgate bpg bprog btimer bus bim bsense en out_s 0 TPS2492_TRANS
Rout out out_s 10
Dout 0 out_s signalclamp
Vbprog bprog 0 {2*rs*pb}
Cbt btimer 0 {200e-9*(.85 if low else 1.15)}
Rbg bgate bg 100
Qboost pull bgate bg fastpnp
Rboost pull out 10
Mb bd bg out out fet
Rbd bsense bd 1.8m
Cbg bg out {c['cgs_nf']}n
Cbgd bg bd 2n
Cbds bd out 3n
Db 0 out clamp
Rflt mref bflt 10k
Rmainflt mref mflt 10k
* Representative healthy 10A branch: actual controller, gate and load.
Rh bus hsense {.004*(1.06 if low else .94)}
Xh href hflt hnc 0 hgate hpg hprog htimer bus him hsense en hout_s 0 TPS2492_TRANS
Vhprog hprog 0 {2*.004*(1.06 if low else .94)*calc['branches'][0]['power_limit_screen_w'][idx]}
Cht htimer 0 {200e-9*(.85 if low else 1.15)}
Rhg hgate hg 100
Qhboost hpull hgate hg fastpnp
Rhboost hpull hout 10
Mh hd hg hout hout fet
Rhd hsense hd 1.8m
Chg hg hout {c['cgs_nf']}n
Chgd hg hd 2n
Chds hd hout 3n
Dh 0 hout clamp
Rho hout hout_s 10
Dho 0 hout_s signalclamp
Rhload hout 0 {c['vin']/10}
Chload hout 0 100u
Rhflt mref hflt 10k
{load}
.model fet NMOS(level=1 VTO=2.2 KP=120 LAMBDA=0)
.model pnp PNP(IS=1e-14 BF=100 VAF=80)
.model fastpnp PNP(IS=1e-13 BF=60 VAF=40 TF=2n TR=500n CJC=25p)
.model clamp D(IS=10u N=1.2 RS=.005 CJO=500p BV=60)
.model signalclamp D(IS=200n N=1.05 RS=2 CJO=10p BV=30)
.options method=trap reltol=1e-3 abstol=1e-8 vntol=1e-5 rshunt=1e12 cshunt=1e-12
.save v(vin) v(bus) v(out) v(mgate) v(bgate) v(mtimer) v(btimer) v(mflt) v(bflt) v(brenable) v(main_sense) v(md1) v(md2) v(bsense) v(bd) v(hout) v(hflt) v(out_s) v(bg)
.control
set wr_singlescale
set wr_vecnames
tran 2u 200m
wrdata {name}.tsv v(vin) v(bus) v(out) v(mgate) v(bgate) v(mtimer) v(btimer) v(mflt) v(bflt) v(brenable) v(main_sense) v(md1) v(md2) v(bsense) v(bd) v(hout) v(hflt) v(out_s) v(bg)
quit
.endc
.end
'''
        netpath,logpath=OUT/(name+'.cir'),OUT/(name+'.log')
        previous=netpath.read_text() if netpath.exists() else ''
        candidates=[text,text.replace('method=trap','method=gear'),
                    text.replace('method=trap','method=gear maxord=2 itl4=200 trtol=1'),
                    text.replace('method=trap','method=gear itl4=200').replace('cshunt=1e-12','cshunt=1e-11'),
                    text.replace('method=trap','method=gear itl4=500').replace('reltol=1e-3','reltol=3e-3'),
                    text.replace('method=trap','method=gear itl4=500').replace('cshunt=1e-12','cshunt=1e-10')]
        if os.environ.get('SPICE_NUMERICAL_FALLBACK'): candidates=candidates[-1:]
        cached=model_matches and previous in candidates and logpath.exists() and (OUT/(name+'.tsv')).exists()
        if cached:
            log=logpath.read_text()
            cached='aborted' not in log and 'Error' not in log and 'ngspice-44.2 done' in log
        if not cached:
            completed=False
            for candidate_model in models:
                model_path.write_text(candidate_model)
                for candidate in candidates:
                    netpath.write_text(candidate)
                    try:
                        with logpath.open('w') as f:
                            subprocess.run([str(ng),'-b',name+'.cir'],cwd=OUT,env=env,
                                           stdout=f,stderr=f,timeout=360,check=True)
                    except subprocess.TimeoutExpired:
                        continue
                    log=logpath.read_text()
                    if 'aborted' not in log and 'Error' not in log:
                        completed=True
                        break
                if completed:break
            assert completed,name
        a=np.loadtxt(OUT/(name+'.tsv'),skiprows=1)
        t,vin,bus,out,mg,bg,mt,bt,mflt,bflt,en,ms,md1,md2,bs,bd,hout,hflt,outs,fetgate=a.T
        assert abs(t[-1]-.2)<1e-9,name
        mi=np.maximum(0,(2*ms-md1-md2)/.0018)
        bi=np.maximum(0,(bs-bd)/.0018)
        expected=c['kind']=='start'
        final_on=out[-1]>.85*c['vin']
        r=dict(**c,name=name,channel_on=bool(final_on),expected_on=expected,
               final_bus_v=float(bus[-1]),final_output_v=float(out[-1]),
               main_timer_peak_v=float(mt.max()),branch_timer_peak_v=float(bt.max()),
               common_latched=bool(mflt[-1]<1),branch_latched=bool(bflt[-1]<1),
               peak_common_current_a=float(mi.max()),peak_branch_current_a=float(bi.max()),
               completed_s=float(t[-1]),netlist_sha256=sha(OUT/(name+'.cir')),
               timer_clamp_implementation='table' if 'G1 A C TABLE' in model_path.read_text() else 'equivalent_behavioral_source',
               numerical_options=next(line for line in netpath.read_text().splitlines() if line.startswith('.options')),
               integration_method='gear' if 'method=gear' in netpath.read_text() else 'trap',
               model_sha256=sha(OUT/(name+'.lib')))
        r.update(healthy_channel_latched=bool(hflt[-1]<1),healthy_final_output_v=float(hout[-1]),
                 minimum_out_sense_v=float(outs.min()),maximum_gate_source_v=float((fetgate-out).max()),
                 peak_shunt_differential_v=float((bus-bs).max()))
        if c['kind']=='live':
            mask=t>.099
            r['healthy_bus_min_during_fault_v']=float(bus[mask].min())
            r['input_min_during_fault_v']=float(vin[mask].min())
            r['enable_min_during_fault_v']=float(en[mask].min())
            r['healthy_output_min_during_fault_v']=float(hout[mask].min())
            r['healthy_fault_asserted_during_fault']=bool(np.any(hflt[mask]<1))
        for label,vds,current in [('main',np.maximum(0,ms-bus),mi),('branch',np.maximum(0,bd-out),bi)]:
            k=(175-soa['mounting_base_limit_c'])/150*.9
            pulse=np.zeros(len(t));dc=np.zeros(len(t))
            for i in np.flatnonzero((vds>=1)&(current>.01)):
                pulse[i]=current[i]/(k*thermal_soa(soa['curves']['100ms'],vds[i]))
                dc[i]=current[i]/(k*thermal_soa(soa['curves']['DC'],vds[i]))
            power=vds*current
            # Live fault window starts at the fault; startup begins at t=0.
            # Count preheating/gate delay in the whole pulse window.
            # Ordinary fully enhanced I²R loss is continuous, not a linear-mode
            # SOA pulse. Check startup and the live fault separately: startup
            # stress must not make subsequent normal conduction a 100 ms fault.
            windows=[(0,.1),(.1,.2)] if c['kind']=='live' else [(0,.2)]
            duration=0
            for start,end in windows:
                window=(t>=start)&(t<=end)
                stress=np.flatnonzero(window&(vds>=1)&(power>1))
                if np.any(window&(dc>1)) and len(stress):
                    duration=max(duration,t[stress[-1]]-start)
            r[label+'_single_fet_100ms_soa_utilization']=float(pulse.max())
            r[label+'_whole_event_ms_if_dc_exceeded']=float(duration*1000)
            r[label+'_energy_j']=float(np.trapezoid(power,t))
            combined=float(pulse.max())
            if c['kind']=='live':
                burst=(t>=.1)&(t<.10001)
                settling=(t>=.10001)&(t<.1001)
                tail=t>=.1001
                rapid=max((current[i]/(k*thermal_soa(soa['curves']['10us'],vds[i]))
                           for i in np.flatnonzero(burst&(vds>=1)&(current>.01))),default=0)
                slow=float(pulse[tail].max())
                settle=max((current[i]/(k*thermal_soa(soa['curves']['100us'],vds[i]))
                           for i in np.flatnonzero(settling&(vds>=1)&(current>.01))),default=0)
                # Sum rectangular envelopes using published pulse durations:
                # first 10us, next 90us charged as a full 100us pulse, then
                # the limiting interval charged as a full 100ms pulse.
                combined=max(float(pulse[t<.1].max()),rapid+settle+slow)
                r[label+'_10us_surge_utilization']=float(rapid)
                r[label+'_100us_settling_utilization']=float(settle)
                r[label+'_100ms_tail_utilization']=slow
            r[label+'_combined_soa_utilization']=combined
        r['passes']=bool(final_on==expected and not r['common_latched'] and
            bus[-1]>.85*c['vin'] and (not expected or not r['branch_latched']) and
            (expected or r['branch_latched']) and
            all(r[l+'_combined_soa_utilization']<1 and r[l+'_whole_event_ms_if_dc_exceeded']<100 for l in ('main','branch')) and
            not r['healthy_channel_latched'] and r['healthy_final_output_v']>.85*c['vin'] and
            r['minimum_out_sense_v']>-1 and r['maximum_gate_source_v']<20 and r['peak_shunt_differential_v']<1.5 and
            (c['kind']!='live' or (r['healthy_bus_min_during_fault_v']>8.8 and
             r['healthy_output_min_during_fault_v']>.85*c['vin'] and not r['healthy_fault_asserted_during_fault'])))
        (OUT/(name+'.json')).write_text(json.dumps(r,indent=2)+'\n')
        print(name,'PASS' if r['passes'] else 'FAIL',flush=True)
        return r
    def evaluate(c):
        try:
            result=sim(c)
            result['simulation_completed']=True
            return result
        except (AssertionError,subprocess.SubprocessError) as exc:
            print(c,'SIMULATION INCOMPLETE',str(exc),flush=True)
            return dict(**c,simulation_completed=False,passes=False,diagnostic=str(exc))
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        result=list(pool.map(evaluate,cases))
    record=dict(status='prototype_transient_sensitivity_pass' if all(r['passes'] for r in result) else 'FAILED',
        sources=sources(),controller_model_sha256=MODEL_SHA,cases=result,
        limitations=['Not measured hardware or manufacturer MOSFET model',
          'Level-1 MOSFET KP=120,VTO=2.2,Rd=1.8m; fixed Cgs35..100nF,Cgd2nF sensitivity only',
          'Source5mOhm+1uH; fault10mOhm+100nH; common ESR2mOhm; no installation immunity claim',
          'Healthy load is resistive; constant-power converter brownout needs bench checking',
          'SOA attributes all parallel input current to one FET at 60C mounting base plus 10% graph reserve'])
    target=OUT/'single-case.json' if os.environ.get('ISOLATION_CASE') else RESULT
    target.write_text(json.dumps(record,indent=2)+'\n')
    assert record['status']=='prototype_transient_sensitivity_pass','See failing cases in '+str(RESULT)


if __name__=='__main__':
    if '--check' in sys.argv:
        result=json.loads(RESULT.read_text())
        assert result['status']=='prototype_transient_sensitivity_pass'
        assert result['sources']==sources(), 'Stale transient evidence'
        assert len(result['cases'])==23 and all(c['passes'] for c in result['cases'])
        assert result['controller_model_sha256']==MODEL_SHA
        print('23 channel-isolation sensitivity cases passed; source hashes match')
    else: run()
