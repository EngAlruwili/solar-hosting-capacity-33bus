"""Reproducible time-series study with an independently checked radial AC solver.

The vectorized solver is restricted to this balanced, series-only radial case.
It is cross-checked against pandapower Newton-Raphson at selected operating points.
"""
from pathlib import Path
from copy import deepcopy
import json
import hashlib
import platform
import importlib.metadata
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import networkx as nx
import pandapower as pp
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .model import benchmark, solve


def radial_data():
    net = benchmark()
    lines = net.line.loc[net.line.in_service]
    assert not lines.c_nf_per_km.any(), 'Series-only solver requires zero shunts'
    assert len(net.trafo) == 0 and len(net.shunt) == 0
    graph = nx.Graph()
    edge_lookup = {}
    for k, (_, row) in enumerate(lines.iterrows()):
        a, b = int(row.from_bus), int(row.to_bus)
        graph.add_edge(a, b)
        edge_lookup[frozenset((a, b))] = k
    path = np.zeros((32, 32))
    for bus in range(1, 33):
        route = nx.shortest_path(graph, 0, bus)
        for a, b in zip(route, route[1:]):
            path[edge_lookup[frozenset((a, b))], bus - 1] = 1
    z = ((lines.r_ohm_per_km.to_numpy() + 1j * lines.x_ohm_per_km.to_numpy())
         * lines.length_km.to_numpy() / 12.66**2)
    loads = net.load.groupby('bus')[['p_mw', 'q_mvar']].sum().reindex(range(1, 33), fill_value=0)
    return {'path': path, 'z': z, 'zbus': path.T @ (z[:, None] * path),
            'p': loads.p_mw.to_numpy(), 'q': loads.q_mvar.to_numpy(),
            'line_ids': lines.index.to_numpy()}


def ac_flow(data, s, source=1.03):
    """S is net consumption in MW+j MVAr, on a 1 MVA three-phase base."""
    s = np.atleast_2d(s)
    v = np.full(s.shape, complex(source))
    for iteration in range(150):
        if np.any(abs(v) < 0.3):
            raise RuntimeError('Radial AC solver encountered low voltage')
        new = source - np.conj(s / v) @ data['zbus'].T
        error = np.max(abs(new - v))
        v = new
        if error < 1e-10:
            break
    else:
        raise RuntimeError('Radial AC solver failed to converge')
    current = np.conj(s / v) @ data['path'].T
    losses = abs(current)**2 @ data['z']
    grid = s.sum(axis=1) + losses
    # Independent source current from the solved branch current at root edges.
    return v, current, losses, grid


def profiles(step=15):
    hours = np.arange(0, 24, step / 60)
    sun = np.maximum(0, np.sin(np.pi * (hours - 6) / 12)) ** 1.6
    morning = np.exp(-((hours - 8) / 2.0)**2)
    evening = np.exp(-((hours - 19) / 2.5)**2)
    rows = []
    for name in ['low_demand', 'high_demand', 'variable_solar', 'evening_peak']:
        demand = 0.48 + 0.10 * morning + 0.17 * evening
        solar = sun.copy()
        if name == 'low_demand': demand *= 0.75
        if name == 'high_demand': demand *= 1.20
        if name == 'variable_solar':
            solar *= 1 - 0.65 * np.exp(-((hours - 12) / 0.55)**2)
        if name == 'evening_peak':
            demand = 0.48 + 0.10 * morning + 0.32 * evening
        rows.extend(zip([name]*len(hours), hours, demand, solar))
    return pd.DataFrame(rows, columns=['day', 'hour', 'load_multiplier', 'solar_pu'])


def allocation(data, placement):
    weights = np.zeros(32)
    if placement == 'distributed': weights = data['p'].copy()
    elif placement == 'upstream': weights[np.array([3, 4, 5])-1-1] = 1
    elif placement == 'remote': weights[np.array([18, 22, 33])-1-1] = 1
    else: raise ValueError(placement)
    return weights / weights.sum()


def q_target(voltage, p, rating):
    cap = np.sqrt(np.maximum(0, rating**2 - p**2))
    fraction = np.where(voltage < .99, np.clip((.99-voltage)/.04, 0, 1),
                        -np.clip((voltage-1.01)/.04, 0, 1))
    return np.where(p > 1e-9, fraction * cap, 0.0)


def simulate(data, profile, placement, h, control, source=1.03, demand=1., ratio=1.1):
    rated = h * data['p'].sum() * allocation(data, placement)
    p = profile.solar_pu.to_numpy()[:, None] * rated
    load = profile.load_multiplier.to_numpy()[:, None] * demand
    q = np.zeros_like(p)
    previous_v = None
    for iteration in range(160 if control else 1):
        s = load * (data['p'] + 1j*data['q']) - p - 1j*q
        v, current, losses, grid = ac_flow(data, s, source)
        if not control: break
        target = q_target(abs(v), p, ratio * rated)
        q_error = float(np.max(abs(target-q)))
        v_error = np.inf if previous_v is None else float(np.max(abs(v-previous_v)))
        if q_error < 1e-6 and v_error < 1e-7: break
        previous_v = v.copy()
        q = .75*q + .25*target
    else:
        raise RuntimeError('Volt-VAR fixed-point iteration failed')
    return {'v': v, 'current': current, 'losses': losses, 'grid': grid,
            'p': p, 'q': q, 's': s, 'rated': rated, 'iterations': iteration+1,
            'q_residual': q_error if control else 0., 'source': source}


def metrics(result, profile, step):
    v = np.column_stack([np.full(len(profile), result['source']), abs(result['v'])])
    violations = (v < .95) | (v > 1.05)
    lower, upper = np.unravel_index(v.argmin(), v.shape), np.unravel_index(v.argmax(), v.shape)
    limit = lower if (.95-v.min()) > (v.max()-1.05) else upper
    return {'feasible': bool(not violations.any()), 'min_voltage_pu': float(v.min()),
            'max_voltage_pu': float(v.max()), 'limiting_bus': int(limit[1]+1),
            'limiting_day': str(profile.iloc[limit[0]].day),
            'limiting_hour': float(profile.iloc[limit[0]].hour),
            'violation_hours': float(violations.any(axis=1).sum()*step/60),
            'violation_bus_hours': float(violations.sum()*step/60),
            'four_day_loss_kwh': float(result['losses'].real.sum()*1000*step/60),
            'peak_current_a': float(abs(result['current']).max()*1000/(np.sqrt(3)*12.66)),
            'peak_import_mw': float(max(0, result['grid'].real.max())),
            'peak_export_mw': float(max(0, -result['grid'].real.min())),
            'reverse_flow_hours': float((result['grid'].real < 0).sum()*step/60),
            'peak_abs_q_mvar': float(abs(result['q']).max()),
            'control_iterations': result['iterations'], 'q_residual_mvar': result['q_residual']}


def sweep(data, profile, placement, control, source=1.03, demand=1., ratio=1.1, step=15, ceiling=4.):
    cache = {}
    def evaluate(h):
        h = round(float(h), 8)
        if h not in cache:
            try:
                result = simulate(data, profile, placement, h, control, source, demand, ratio)
                cache[h] = {'h': h, 'capacity_mw': h*data['p'].sum(), 'status': 'converged',
                            **metrics(result, profile, step)}
            except RuntimeError as error:
                cache[h] = {'h': h, 'capacity_mw': h*data['p'].sum(), 'status': str(error), 'feasible': False}
        return cache[h]
    coarse = np.arange(0, ceiling + .001, .25)
    for h in coarse: evaluate(h)
    for a, b in zip(coarse, coarse[1:]):
        if evaluate(a)['status'] != 'converged' or evaluate(b)['status'] != 'converged': continue
        if evaluate(a)['feasible'] != evaluate(b)['feasible']:
            while b-a > .01:
                mid = (a+b)/2
                m = evaluate(mid)
                if m['status'] != 'converged': break
                if m['feasible'] == evaluate(a)['feasible']: a=mid
                else: b=mid
    rows = sorted(cache.values(), key=lambda x:x['h'])
    baseline = evaluate(0)['feasible']
    passing = [r for r in rows if r['feasible']]
    # Report sampled intervals and all evaluations; no global monotonicity claim.
    best = passing[-1]['h'] if passing else None
    following = [r for r in rows if best is not None and r['h']>best]
    bound = following[0]['h'] if following and following[0]['status']=='converged' else None
    summary = {'placement': placement, 'control': 'volt_var' if control else 'unity_pf',
        'baseline_feasible': baseline, 'largest_tested_feasible_h': best,
        'next_tested_infeasible_h': bound, 'capacity_mw': best*data['p'].sum() if best is not None else None,
        'ceiling_reached': best == ceiling, 'unresolved_points': sum(r['status']!='converged' for r in rows),
        'source_pu':source, 'demand_factor':demand, 'inverter_ratio':ratio, 'step_minutes':step}
    return summary, pd.DataFrame(rows)


def crosscheck(data, profile, placement, h, control):
    result = simulate(data, profile, placement, h, control)
    indices = sorted(set([0, 32, 48, 76, 95, 144, 240, 336,
        int(np.argmax(abs(result['v']))//32), int(np.argmin(abs(result['v']))//32)]))
    rows=[]
    for t in indices:
        net=benchmark()
        net.ext_grid.vm_pu=1.03
        net.load.p_mw *= profile.iloc[t].load_multiplier
        net.load.q_mvar *= profile.iloc[t].load_multiplier
        for j in np.flatnonzero(result['rated']):
            pp.create_sgen(net, int(j+1), p_mw=float(result['p'][t,j]), q_mvar=float(result['q'][t,j]))
        solve(net)
        rows.append({'placement':placement, 'control':control, 'h':h, 'time_index':t,
            'voltage_error_pu':float(np.max(abs(net.res_bus.vm_pu.to_numpy()[1:]-abs(result['v'][t])))),
            'loss_error_mw':float(abs(net.res_line.pl_mw.sum()-result['losses'][t].real)),
            'source_error_mw':float(abs(net.res_ext_grid.p_mw.sum()-result['grid'][t].real))})
    return rows


def run(out=Path('reports/study')):
    out.mkdir(parents=True, exist_ok=True)
    data=radial_data(); profile=profiles()
    profile.to_csv(out/'synthetic_profiles.csv', index=False)
    summaries=[]; evaluations=[]; checks=[]; selected=[]
    for placement in ['distributed','upstream','remote']:
        for control in [False,True]:
            summary, table=sweep(data,profile,placement,control)
            summaries.append(summary)
            table['placement']=placement; table['control']=summary['control']; evaluations.append(table)
            h=summary['largest_tested_feasible_h']
            print(json.dumps(summary), flush=True)
            if h is not None:
                checks.extend(crosscheck(data,profile,placement,h,control))
                result=simulate(data,profile,placement,h,control)
                volt=pd.DataFrame(abs(result['v']), columns=[f'bus_{i}' for i in range(2,34)])
                volt=pd.concat([profile,volt],axis=1)
                volt.to_csv(out/f'{placement}_{summary["control"]}_voltages.csv',index=False)
                row={**summary, **metrics(result,profile,15)}; selected.append(row)
    pd.DataFrame(summaries).to_csv(out/'hosting_summary.csv',index=False)
    pd.concat(evaluations).to_csv(out/'capacity_sweep.csv',index=False)
    pd.DataFrame(selected).to_csv(out/'boundary_metrics.csv',index=False)
    check=pd.DataFrame(checks); check.to_csv(out/'independent_solver_checks.csv',index=False)
    assert check.voltage_error_pu.max()<1e-6 and check.loss_error_mw.max()<1e-6
    assert check.source_error_mw.max()<1e-6
    sensitivities=[]
    cases=[('reference',{}),('demand_minus_10',{'demand':.9}),('demand_plus_10',{'demand':1.1}),
        ('source_1_02',{'source':1.02}),('source_1_04',{'source':1.04}),
        ('inverter_1_00',{'ratio':1.}),('inverter_1_20',{'ratio':1.2}),('five_minute',{'step':5})]
    for name,kwargs in cases:
        p=profiles(kwargs.get('step',15))
        summary, table=sweep(data,p,'remote',True,**kwargs)
        summary['case']=name; sensitivities.append(summary)
        table.to_csv(out/f'sensitivity_{name}.csv',index=False)
        print('sensitivity '+name,flush=True)
    pd.DataFrame(sensitivities).to_csv(out/'sensitivities.csv',index=False)
    # Compare controls at exactly the same installed capacity, not their different boundaries.
    common_h=next(s['largest_tested_feasible_h'] for s in summaries if s['placement']=='remote' and s['control']=='unity_pf')
    pairs=[]
    for control in [False,True]:
        result=simulate(data,profile,'remote',common_h,control)
        pairs.append({'control':'volt_var' if control else 'unity_pf','h':common_h,**metrics(result,profile,15)})
        ts=profile.copy(); ts['loss_kw']=result['losses'].real*1000;ts['source_mw']=result['grid'].real
        ts['minimum_voltage_pu']=abs(result['v']).min(axis=1); ts['maximum_voltage_pu']=abs(result['v']).max(axis=1)
        ts['total_q_mvar']=result['q'].sum(axis=1)
        ts.to_csv(out/f'paired_{pairs[-1]["control"]}.csv',index=False)
    pd.DataFrame(pairs).to_csv(out/'paired_control_metrics.csv',index=False)
    metadata={'created_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),
        'versions':{p:importlib.metadata.version(p) for p in ['pandapower','numpy','pandas','matplotlib']},
        'study_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'assumptions':{'source_pu':1.03,'voltage_band':[.95,1.05],'inverter_ratio':1.1,
        'sweep_step_h':.25,'refinement_h':.01,'ceiling_h':4,'minutes':15,'night_q':False,
        'control':'local Volt-VAR, active-power priority, 0.99–1.01 deadband, saturation at 0.95/1.05',
        'profile_source':'deterministic synthetic formulas in profiles(); no measured data'},
        'validation_cases':len(check),'max_voltage_error_pu':float(check.voltage_error_pu.max())}
    (out/'run_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    plot_results(out,profile,summaries,sensitivities)


def plot_results(out, profile, summaries, sensitivities):
    plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'font.size':11})
    fig, axes=plt.subplots(2,1,figsize=(10,7),layout='constrained')
    for day,g in profile.groupby('day',sort=False):
        axes[0].plot(g.hour,g.load_multiplier,label=day.replace('_',' '))
        axes[1].plot(g.hour,g.solar_pu,label=day.replace('_',' '))
    axes[0].set(ylabel='Demand / nominal demand',title='Four synthetic operating days')
    axes[1].set(xlabel='Hour',ylabel='Solar / installed capacity');axes[0].legend(ncol=2)
    fig.savefig(out/'profiles.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    for i,control in enumerate(['unity_pf','volt_var']):
        group=[s for s in summaries if s['control']==control]
        ax.bar(np.arange(3)+(i-.5)*.34,[s['capacity_mw'] for s in group],.34,
               label=control.replace('_',' '),color=['#227C9D','#D99C38'][i])
        for j,s in enumerate(group):
            if s['ceiling_reached']: ax.text(j+(i-.5)*.34,s['capacity_mw']+.1,'lower bound',ha='center',fontsize=8)
    ax.set(xticks=np.arange(3),xticklabels=['Distributed','Upstream','Remote'],ylabel='Installed solar capacity (MW)',
           title='Voltage-feasible capacity | four synthetic days');ax.legend()
    fig.savefig(out/'hosting_comparison.png',dpi=170);plt.close(fig)
    remote=pd.read_csv(out/'remote_volt_var_voltages.csv')
    fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
    im=ax.imshow(remote.filter(like='bus_').to_numpy().T,aspect='auto',origin='lower',
                 extent=[0,96,1.5,33.5],vmin=.95,vmax=1.05,cmap='RdYlBu_r')
    ax.set(xlabel='Concatenated synthetic hours (four separate days)',ylabel='Source bus number',
           title='Remote solar + Volt-VAR | largest tested feasible capacity')
    fig.colorbar(im,ax=ax,label='Voltage (p.u.)');fig.savefig(out/'voltage_heatmap.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,5),layout='constrained')
    ax.barh([s['case'] for s in sensitivities],[s['capacity_mw'] or 0 for s in sensitivities],color='#227C9D')
    ax.set(xlabel='Largest tested voltage-feasible solar capacity (MW)',title='Remote Volt-VAR sensitivity study')
    fig.savefig(out/'sensitivity.png',dpi=170);plt.close(fig)
    fig,axes=plt.subplots(2,1,figsize=(10,6),layout='constrained')
    for control in ['unity_pf','volt_var']:
        t=pd.read_csv(out/f'paired_{control}.csv')
        axes[0].plot(np.arange(len(t))/4,t.source_mw,label=control)
        axes[1].plot(np.arange(len(t))/4,t.loss_kw,label=control)
    axes[0].set(ylabel='Grid power (MW)',title='Equal-capacity remote solar comparison (positive = import)')
    axes[1].set(xlabel='Concatenated synthetic hours',ylabel='Line losses (kW)');axes[0].legend()
    fig.savefig(out/'paired_power_losses.png',dpi=170);plt.close(fig)


if __name__=='__main__':
    run()
