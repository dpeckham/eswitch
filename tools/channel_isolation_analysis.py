#!/usr/bin/env python3
"""Revision C coordination and SOA screen from exact fitted circuit values.

Analytical tolerance screen, not measured short-circuit or thermal qualification.
"""
import itertools
import json
import math
import sys
from pathlib import Path
import design
from revision_c import SHUNT_MOHM
from input_stage_analysis import charge_time, constant_load_charge_time, divider
from input_stage_transient import soa_current

ROOT=Path(__file__).resolve().parent.parent


def power(top,rs,tol):
    v=[ref*rb/(rt+rb)+ib*rt*rb/(rt+rb)
       for ref,rb,rt,ib in itertools.product((3.9,4.1),(990,1010),
                                            (top*.99,top*1.01),(-5e-6,5e-6))]
    return [.5*min(v)/(rs*(1+tol))*.68,.5*max(v)/(rs*(1-tol))*1.32]


def timer(cap,tol):
    return [cap*(1-tol)*3.9/36e-6,cap*(1+tol)*4.1/17e-6]


def analyze():
    p={x.ref:x for x in design.build()}
    assert p['R20'].fields['MPN']=='CSS4J-4026R-L500F'
    assert p['R17'].value=='8.25k 0.1%'
    assert p['R17'].fields['MPN']=='RT0603BRD078K25L'
    assert p['R18'].fields['MPN']=='RT0603BRD071KL'
    assert p['C18'].value==p['C25'].value==p['C28'].value=='12nF 50V C0G 5%'
    assert p['U14'].pins['8']=='MAIN_PG_N'
    assert p['Q6'].pins=={'1':'BR_ENABLE_BASE','2':'HS_REF','3':'BR_ENABLE'}
    # Shunt tolerance includes full -55..155C terminal temperature range.
    # 0.5m Bourns: 1% + 100ppm/K * 130K -> reserve 2.5%.
    # Worst WSLP2m: 1% + 275ppm/K * 130K; reserve 6% with local Kelvin lands.
    common_r=.0005
    common_i=[.045/(common_r*1.025),.055/(common_r*.975)]
    common_p=power(8250,common_r,.025)
    # PROG remains within the specified 0.4..4V range including bias/tolerance.
    assert 3.9*990/(8250*1.01+990)-5e-6*1000 > .4
    common_t=timer(36e-9,.055)
    soa=json.loads((ROOT/'docs/evidence/input-mosfet-soa.json').read_text())
    derate=(175-60)/150*.9
    common_soa=common_p[1]/16/(soa_current(soa['curves']['10ms'],16)*derate)
    assert common_t[1]<.01 and common_soa<1, 'Common backup fault exceeds single-FET 10ms SOA'
    common_start=[]
    for v in (9.5,12,16):
        dt=constant_load_charge_time(v,3480e-6,2,common_p[0],common_i[0])
        budget=36e-9*.945*(3.9-1.04)/36e-6
        assert dt*1.25<budget,(v,dt,budget)
        common_start.append(dict(input_v=v,capacitance_uf=3480,load_current_a=2,
                                 ideal_charge_ms=dt*1000,minimum_timer_residual_ms=budget*1000))
    branches=[]
    for n in range(1,9):
        rating=design.CHANNELS[n][0]; rs=.001*SHUNT_MOHM[n]
        assert p[f'R{n}20'].fields['MPN']==f'WSLP2512{SHUNT_MOHM[n]}L000FEA'
        assert p[f'F{n}'].pins['2']==f'CHFEED{n}'
        assert p[f'Q{10+n}'].pins['5']==f'BR_SENSE{n}'
        assert p[f'U{20+n}'].pins['1']==f'BR_EN{n}'
        assert p[f'SW{n+2}'].pins=={'1':'GND','2':f'BR_EN{n}'}
        assert p[f'R{n}12'].value==('7.5k' if n==8 else '2.2k' if rating==5 else '4.7k')+' 0.1%'
        assert p[f'R{n}13'].fields['MPN']=='RT0603BRD071KL'
        for k in (1,2): assert p[f'C{n}{10+k}'].fields['MPN']=='C1206C104J5JACAUTO'
        currents=[.045/(rs*1.06),.055/(rs*.94)]
        powers=power(7500 if n==8 else 2200 if rating==5 else 4700,rs,.06)
        # U2J -750 +/-120ppm/K; <9% over specified temperature excursion,
        # plus initial 5%. Use +/-15% total, no Class-II DC-bias dependence.
        times=timer(200e-9,.15)
        residual=200e-9*.85*(3.9-1.04)/36e-6
        cases=[]
        for v in (9.5,12,16):
            startup_rating=10 if n==8 else rating
            dt=charge_time(v,.001,startup_rating,powers[0],currents[0])
            assert dt*1.25<residual,(n,v,dt,residual)
            # Compare all branch current to ONE FET, at 60C mounting base,
            # with 10% margin to the digitized 100ms datasheet SOA curve.
            util=(powers[1]/v)/(soa_current(soa['curves']['100ms'],v)*derate)
            assert util<1,(n,v,util)
            cases.append(dict(input_v=v,startup_load_a=startup_rating,load_model='resistor at stated startup current plus 1000uF actual',
                              ideal_charge_ms=dt*1000,minimum_residual_timer_ms=residual*1000,
                              single_fet_100ms_power_limit_soa_utilization=util))
        healthy_fault=40+currents[1]
        assert healthy_fault<common_i[0]
        branches.append(dict(channel=n,fuse_a=rating,shunt_ohm=rs,
            current_limit_a=currents,power_limit_screen_w=powers,
            timer_from_zero_ms=[x*1000 for x in times],
            healthy_40a_plus_one_fault_a=healthy_fault,
            common_trip_headroom_a=common_i[0]-healthy_fault,
            shunt_dissipation_at_rating_w=rating**2*rs,
            startup_cases=cases))
    return dict(status='prototype_engineering_screen_not_measured_rating',revision='C',
        current_limit_a=common_i,power_limit_screen_w=common_p,
        nominal_power_limit_w=.5*(4/9.25)/common_r,
        common_backup_single_fet_10ms_soa_utilization=common_soa,
        timer_from_zero_ms=[x*1000 for x in common_t],
        ov_rising_v=divider(115000,10000,.001,(1.31,1.39),(-1e-6,1e-6)),
        uv_rising_v=divider(56200,10000,.001,(1.31,1.39),(-1e-6,1e-6)),
        common_startup=common_start,branches=branches,
        imon_volts_per_amp=48*common_r,bus_divider_ratio=10000/125000,
        assumptions=[
          '9.5..16V at board input under the specified load; 40A total continuous target remains a bench qualification item',
          'One output fault; healthy aggregate current <=40A; no common supply or ground fault',
          'Common 3480uF maximum actual capacitance includes 24x120uF +20% and board/logic capacitance',
          'PG blocks branch startup during common capacitor charging; its 5..15ms deglitch filters short disturbances',
          '1000uF maximum actual branch load capacitance, resistor startup load: 10A CH1/2/8, 5A CH3..7',
          'PROG divider resistors: 0.1%, 25ppm/K; 1% total resistance budget covers initial tolerance, temperature and aging reserve',
          'Each single shunt uses a conservative 6% resistance budget including terminal TCR and Kelvin land pickup; verify effective resistance on first board',
          'TI power-engine +/-32% is a test-point extrapolation, not a guaranteed PROG-range bound',
          'Ideal charge calculations omit gate dynamics; separate SPICE sensitivity study is required',
          'Common backup trip is about 88..113A; it is not a 40A continuous thermal limiter',
          'Current coordination prevents a sustained single-branch fault from reaching the input trip; overshoot and bus dips require transient validation',
          'Local latch resets only through its UVEN switch or loss of the shared enable/input; no MCU action is required'],
        sources={'controller':'https://www.ti.com/lit/gpn/tps2492',
                 'shunt':'https://www.vishay.com/docs/30122/wslp.pdf',
                 'mosfet':'https://assets.nexperia.com/documents/data-sheet/PSMN1R8-80SSE.pdf'})


if __name__=='__main__':
    result=analyze()
    target=ROOT/'docs/channel-isolation-calculations.json'
    if '--check' in sys.argv:
        assert json.loads(target.read_text())==result, 'Stale channel-isolation calculations'
    else:
        target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(target)
