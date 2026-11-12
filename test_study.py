import numpy as np
import pytest
from solar_hosting.study import radial_data, ac_flow, profiles, allocation, q_target, simulate, metrics, crosscheck


def test_independent_radial_solver_against_pandapower():
    rows=crosscheck(radial_data(),profiles(),'remote',.5,True)
    assert max(r['voltage_error_pu'] for r in rows)<1e-6
    assert max(r['loss_error_mw'] for r in rows)<1e-6
    assert max(r['source_error_mw'] for r in rows)<1e-6


def test_no_load_radial_limit():
    v,i,loss,grid=ac_flow(radial_data(),np.zeros((1,32),complex))
    assert np.allclose(v,1.03)
    assert np.allclose(i,0) and np.allclose(loss,0) and np.allclose(grid,0)


def test_inverter_capability_and_sign():
    q=q_target(np.array([.95,1.,1.05,1.06]),np.array([1.,1.,1.,0.]),np.array([1.1]*4))
    assert q[0]>0 and q[1]==0 and q[2]<0 and q[3]==0
    assert np.all(abs(q)<=np.sqrt(1.1**2-np.array([1.,1.,1.,0.])**2)+1e-12)
    assert q_target(np.array([.94]),np.array([1.]),np.array([1.]))[0]==0


def test_profiles_allocations_and_baseline():
    data=radial_data();p=profiles()
    assert len(p)==384 and len(profiles(5))==1152
    assert p.solar_pu.between(0,1).all()
    for place in ['distributed','upstream','remote']:
        assert allocation(data,place).sum()==pytest.approx(1)
    assert np.flatnonzero(allocation(data,'remote')).tolist()==[16,20,31]
    r=simulate(data,p,'distributed',0,False)
    assert metrics(r,p,15)['feasible']


def test_control_fixed_point_and_limits():
    data=radial_data(); p=profiles();r=simulate(data,p,'remote',.8,True)
    target=q_target(abs(r['v']),r['p'],r['rated']*1.1)
    assert np.max(abs(target-r['q']))<1e-6
    assert np.all(r['p']**2+r['q']**2 <= (r['rated']*1.1)**2+1e-10)
    assert np.all(r['q'][p.solar_pu.to_numpy()==0]==0)
