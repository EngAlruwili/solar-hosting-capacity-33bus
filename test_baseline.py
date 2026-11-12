from copy import deepcopy

import pandapower as pp
import pytest

from solar_hosting.model import benchmark, solve, two_bus_check, validation


def test_benchmark_and_balance():
    net = solve(benchmark())
    assert net.line.in_service.sum() == 32
    assert net.load.p_mw.sum() == pytest.approx(3.715)
    assert net.load.q_mvar.sum() == pytest.approx(2.3)
    assert net.bus.source_bus_label.tolist() == list(range(1, 34))
    assert net.bus.at[net.ext_grid.bus.iloc[0], "source_bus_label"] == 1
    check = validation(net)
    assert abs(check["power_balance_residual_mw"]) < 1e-6
    assert check["max_solver_voltage_difference_pu"] < 1e-5


def test_two_bus_independent_calculation():
    check = two_bus_check()
    assert check["drop_relative_error"] < 0.01
    assert check["simulated_loss_mw"] == pytest.approx(check["independent_loss_mw"], abs=1e-9)


def test_no_load_limit():
    net = benchmark()
    net.load.loc[:, ["p_mw", "q_mvar"]] = 0.0
    solve(net)
    assert max(abs(net.res_bus.vm_pu - 1.0)) < 1e-8
    assert abs(net.res_line.pl_mw.sum()) < 1e-8


def test_reactive_power_sign():
    net = pp.create_empty_network()
    a = pp.create_bus(net, vn_kv=12.66)
    b = pp.create_bus(net, vn_kv=12.66)
    pp.create_ext_grid(net, a)
    pp.create_line_from_parameters(net, a, b, 1, 0.4, 0.3, 0, 1)
    pp.create_load(net, b, p_mw=0.1, q_mvar=0.04)
    pp.create_sgen(net, b, p_mw=0.02, q_mvar=0)
    base_voltage = solve(net).res_bus.vm_pu.at[b]
    inject, absorb = deepcopy(net), deepcopy(net)
    inject.sgen.q_mvar = 0.02
    absorb.sgen.q_mvar = -0.02
    assert solve(inject).res_bus.vm_pu.at[b] > base_voltage
    assert solve(absorb).res_bus.vm_pu.at[b] < base_voltage
