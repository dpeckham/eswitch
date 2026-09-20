#!/usr/bin/env python3
"""Supplementary nine-controller, all-channel startup and fault study.

Uses the same TI model adaptation and parasitics as channel_isolation_transient,
with the most sensitive common controller and strongest local controllers.
Every branch includes its own 1000 uF maximum specified load capacitance.
"""
import concurrent.futures,hashlib,json,os,re,subprocess,sys
from pathlib import Path
import numpy as np
from channel_isolation_transient import ROOT,MODEL,MODEL_SHA,make_model,thermal_soa,sources as base_sources
from channel_isolation_analysis import analyze
OUT=ROOT/'out/all-channels-spice'
RESULT=ROOT/'docs/all-channels-transients.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def sources():return {**base_sources(),'tools/all_channels_transient.py':sha(Path(__file__))}

def model(corner,behavioral=True):
    original=MODEL.read_text();assert sha(MODEL)==MODEL_SHA
    text=make_model(original,corner).replace('2.2e-5','1.5e-5').replace('(14,22u)','(14,15u)')
    text=text.replace('V(YTD) > 0.5 ^ V(IN) > .5','(V(YTD)>0.5) != (V(IN)>.5)')
    text=text.replace('.param TPS=0','.param TPS=1').replace('SD_STRONG 0 125e-3','SD_STRONG 0 75e-3').replace('TH=8.35 HYS=0.1','TH=8.775 HYS=0.05')
    if behavioral:text=text.replace('G1 A C TABLE { V(A, C) } ( (-1,-1n)(0,0)(1m,1) (2m,10) (3m,1000) )',
        'G1 A C VALUE={IF(V(A,C)<-1,-1n,IF(V(A,C)<0,V(A,C)*1n,IF(V(A,C)<.001,V(A,C)*1000,IF(V(A,C)<.002,1+(V(A,C)-.001)*9000,IF(V(A,C)<.003,10+(V(A,C)-.002)*990000,1000)))))}')
    names=re.findall(r'^\.(?:subckt|model)\s+(\S+)',text,re.I|re.M)
    mapping={n.lower():corner+'_'+n for n in names}
    # Namespace every component model and subcircuit, retaining all equations.
    text=re.sub(r'(?<![\w])('+'|'.join(map(re.escape,sorted(names,key=len,reverse=True)))+r')(?![\w])',lambda m:mapping[m[0].lower()],text,flags=re.I)
    return text

def circuit(vin,kind,calc):
    rs=.0005*1.025;pm=calc['power_limit_screen_w'][0]
    lines=[f'All eight channels; common low corner, branches high; {vin} V {kind}',
        '.include controllers.lib',f'Vs source 0 PWL(0 0 100u 0 1m {vin+.21})',
        'Rsource source input_l 5m','Lsource input_l vin 1u','Cin vin 0 100n',
        f'Rm vin ms {rs}','Xm mref mflt mnc ov mgate mpg mprog mtimer vin mim ms uven bus 0 low_TPS2492_TRANS',
        'Ruv1 vin uven 56.2k','Ruv2 uven 0 10k','Rov1 vin ov 115k','Rov2 ov 0 10k',
        f'Bmprog mprog 0 V={2*rs*pm}*V(mref)/4','Cmt mtimer 0 34.02n',
        'Rmg1 mgate mg1 10','Rmg2 mgate mg2 10','Mma md1 mg1 bus bus fet','Mmb md2 mg2 bus bus fet',
        'Rmd1 ms md1 1.8m','Rmd2 ms md2 1.8m','Cmg1 mg1 bus 50n','Cmg2 mg2 bus 50n',
        'Cmgd1 mg1 md1 2n','Cmgd2 mg2 md2 2n','Cmds1 md1 bus 3n','Cmds2 md2 bus 3n',
        'Rbulk bus cap 2m',f'Cbulk cap 0 {3456 if kind=="start" else 2304}u','Cbus bus 0 22u','Dmain 0 bus clamp',
        'Baux bus 0 I=2*tanh(V(bus)/.1)','Rbase mpg qbase 10k','Rbe qbase mref 47k',
        'Qenable brenable qbase mref pnp','Renable brenable 0 47k','Rrefload mref 0 9.25k','Rmainflt mref mflt 10k']
    currents=[10,10,2,2,2,2,2,10] if kind!='short' else [10,10,4,4,4,4,4,0]
    for n,branch in enumerate(calc['branches'],1):
        rsb=branch['shunt_ohm']*.94;pb=branch['power_limit_screen_w'][1]
        lines += [f'Ren{n} brenable en{n} 47k',f'Rb{n} bus sense{n} {rsb}',
            f'Xb{n} ref{n} flt{n} nc{n} 0 gate{n} pg{n} prog{n} timer{n} bus im{n} sense{n} en{n} outs{n} 0 high_TPS2492_TRANS',
            f'Bprog{n} prog{n} 0 V={2*rsb*pb}*V(ref{n})/4',f'Ct{n} timer{n} 0 230n',f'Rg{n} gate{n} g{n} 100',
            f'Qboost{n} pull{n} gate{n} g{n} fastpnp',f'Rboost{n} pull{n} out{n} 10',f'Mb{n} drain{n} g{n} out{n} out{n} fet',
            f'Rdrain{n} sense{n} drain{n} 1.8m',f'Cgs{n} g{n} out{n} 50n',f'Cgd{n} g{n} drain{n} 2n',f'Cds{n} drain{n} out{n} 3n',
            f'Db{n} 0 out{n} clamp',f'Ro{n} out{n} outs{n} 10',f'Do{n} 0 outs{n} signalclamp',
            f'Rflt{n} mref flt{n} 10k',f'Rload{n} out{n} 0 {vin/currents[n-1] if currents[n-1] else 1e6}',f'Cload{n} out{n} 0 1000u']
    if kind!='start':
        when=.1 if kind=='live' else 0
        lines += ['Lfault out8 short_in 100n','Rfault short_in swfault 10m','Sfault swfault 0 fault_ctrl 0 sw',
            f'Vfault fault_ctrl 0 PWL(0 0 {when} 0 {when+1e-7} 1)','.model sw SW(Ron=.0001 Roff=1e12 Vt=.5 Vh=.1)']
    lines += ['.model fet NMOS(level=1 VTO=2.2 KP=120 LAMBDA=0)','.model pnp PNP(IS=1e-14 BF=100 VAF=80)',
        '.model fastpnp PNP(IS=1e-13 BF=60 VAF=40 TF=2n TR=500n CJC=25p)',
        '.model clamp D(IS=10u N=1.2 RS=.005 CJO=500p BV=60)','.model signalclamp D(IS=200n N=1.05 RS=2 CJO=10p BV=30)',
        '.options method=gear maxord=2 itl4=500 reltol=1e-3 abstol=1e-8 vntol=1e-5 rshunt=1e12 cshunt=10p']
    vectors=['vin','bus','mflt','mtimer','ms','mgate']+[f'{node}{n}' for n in range(1,9) for node in ('out','flt','timer','sense','drain','g')]
    expressions=' '.join(f'v({v})' for v in vectors)
    lines += ['.save '+expressions,'.control','set wr_singlescale','set wr_vecnames','tran 2u 200m','wrdata wave.tsv '+expressions,'quit','.endc','.end']
    return '\n'.join(lines)+'\n',vectors

def simulate(case):
    vin,kind=case;name=f'{kind}_{vin}';folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
    calc=analyze();net,vectors=circuit(vin,kind,calc)
    lib=ROOT/'out/ngspice-local/usr/lib/x86_64-linux-gnu'
    env=dict(os.environ,LD_LIBRARY_PATH=str(lib),SPICE_SCRIPTS=str(ROOT/'out/isolation-spice'))
    completed=False
    old_net=(folder/'case.cir').read_text() if (folder/'case.cir').exists() else ''
    old_models=(folder/'controllers.lib').read_text() if (folder/'controllers.lib').exists() else ''
    old_result=json.loads((folder/'result.json').read_text()) if (folder/'result.json').exists() else {}
    variants=[]
    for behavioral in (False,True):
        models=model('low',behavioral)+'\n'+model('high',behavioral)
        for method,uic in [('trap',False),('gear',False),('gear',True),('trap',True)]:
            candidate=re.sub(r'\.options method=.*',f'.options method={method} maxord=2 itl4=500 reltol=1e-3 abstol=1e-8 vntol=1e-5 rshunt=1e12 cshunt=10p',net)
            if uic:candidate=candidate.replace('tran 2u 200m','tran 2u 200m uic')
            variants.append((behavioral,method,uic,models,candidate))
    cached=next((v for v in variants if v[3]==old_models and v[4]==old_net and
        old_result.get('netlist_sha256')==hashlib.sha256(old_net.encode()).hexdigest() and
        old_result.get('model_sha256')==hashlib.sha256(old_models.encode()).hexdigest() and
        (folder/'wave.tsv').exists()),None)
    if cached:
        behavioral,method,uic,models,candidate=cached;completed=True
    else:
        for behavioral,method,uic,models,candidate in variants:
            (folder/'controllers.lib').write_text(models)
            (folder/'case.cir').write_text(candidate);(folder/'wave.tsv').unlink(missing_ok=True)
            with (folder/'run.log').open('w') as log:
                subprocess.run([str(ROOT/'out/ngspice-local/usr/bin/ngspice'),'-b','case.cir'],cwd=folder,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
            log=(folder/'run.log').read_text()
            if (folder/'wave.tsv').exists() and 'aborted' not in log:
                completed=True;break
            print(name,'numerical attempt failed',behavioral,method,uic,flush=True)
    log=(folder/'run.log').read_text();assert 'No. of Data Rows' in log and (folder/'wave.tsv').exists(),name+' did not finish'
    data=np.loadtxt(folder/'wave.tsv',skiprows=1);t=data[:,0];assert t[-1]>=.1999
    d={key:data[:,index+1] for index,key in enumerate(vectors)}
    healthy=range(1,9) if kind=='start' else range(1,8)
    result=dict(case=name,vin=vin,kind=kind,common_latched=bool(d['mflt'][-1]<1),
        healthy_final_outputs_v={str(n):float(d[f'out{n}'][-1]) for n in healthy},
        healthy_latched=[n for n in healthy if d[f'flt{n}'][-1]<1],
        branch8_final_output_v=float(d['out8'][-1]),branch8_latched=bool(d['flt8'][-1]<1),
        netlist_sha256=sha(folder/'case.cir'),model_sha256=sha(folder/'controllers.lib'))
    result['numerical_options']=dict(method=method,initially_uncharged_uic=uic,timer_behavioral=behavioral)
    soa=json.loads((ROOT/'docs/evidence/input-mosfet-soa.json').read_text());derate=(175-soa['mounting_base_limit_c'])/150*.9
    stress=[('common',np.maximum(0,d['ms']-d['bus']),np.maximum(0,(d['vin']-d['ms'])/(.0005*1.025)))]
    stress += [(f'channel{n}',np.maximum(0,d[f'drain{n}']-d[f'out{n}']),
        np.maximum(0,(d['bus']-d[f'sense{n}'])/(calc['branches'][n-1]['shunt_ohm']*.94))) for n in range(1,9)]
    result['soa']={}
    for label,vds,current in stress:
        linear=(vds>=1)&(current>.01)
        def util(curve,mask):
            return max((current[i]/(derate*thermal_soa(soa['curves'][curve],vds[i])) for i in np.flatnonzero(linear&mask)),default=0)
        allpoints=np.ones(len(t),dtype=bool)
        combined=util('100ms',allpoints)
        if kind=='live':combined=max(util('100ms',t<.1),util('10us',(t>=.1)&(t<.10001))+util('100us',(t>=.10001)&(t<.1001))+util('100ms',t>=.1001))
        duration=0
        for start,end in ([(0,.1),(.1,.2)] if kind=='live' else [(0,.2)]):
            mask=(t>=start)&(t<=end)
            indices=np.flatnonzero(mask&linear&(vds*current>1))
            if len(indices) and util('DC',mask)>1:duration=max(duration,float(t[indices[-1]]-start))
        result['soa'][label]=dict(combined_utilization=float(combined),event_ms_if_dc_exceeded=duration*1000)
    good=not result['common_latched'] and not result['healthy_latched'] and min(result['healthy_final_outputs_v'].values())>.85*vin
    if kind!='start':good=good and result['branch8_latched'] and result['branch8_final_output_v']<1
    good=good and all(x['combined_utilization']<1 and x['event_ms_if_dc_exceeded']<100 for x in result['soa'].values())
    if kind=='live':
        mask=t>=.1
        result['bus_min_during_fault_v']=float(d['bus'][mask].min())
        result['healthy_min_during_fault_v']=min(float(d[f'out{n}'][mask].min()) for n in healthy)
        result['healthy_fault_during_fault']=any(np.any(d[f'flt{n}'][mask]<1) for n in healthy)
        good=good and result['bus_min_during_fault_v']>8.8 and result['healthy_min_during_fault_v']>.85*vin and not result['healthy_fault_during_fault']
    result['passes']=bool(good)
    (folder/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(name,result['passes'],flush=True)
    return result

def main():
    if '--check' in sys.argv:
        j=json.loads(RESULT.read_text());assert j['sources']==sources() and len(j['cases'])==6 and all(c['passes'] for c in j['cases']);print('All-channel evidence: six cases PASS');return
    cases=[(vin,kind) for vin in (9.5,16) for kind in ('start','short','live')]
    if os.environ.get('ALL_CHANNELS_CASE'):
        cases=[case for case in cases if f'{case[1]}_{case[0]}'==os.environ['ALL_CHANNELS_CASE']]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(simulate,cases))
    report=dict(sources=sources(),cases=results,passes=all(c['passes'] for c in results),
        scope='Nine controllers, worst opposite common/local corners, 1000uF on every output; 40A total resistive loads plus 2A auxiliary before fault',
        limitation='Supplementary startup/isolation check; approximate same semiconductor/parasitic models as primary study, not hardware qualification')
    if len(results)==6:RESULT.write_text(json.dumps(report,indent=2)+'\n')
    assert report['passes'],'All-channel startup/fault case failed'
if __name__=='__main__':main()
