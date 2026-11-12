"""Benchmark and independent numerical checks. Powers are three-phase totals."""
from copy import deepcopy

import numpy as np
import pandapower as pp
from pandapower.networks import case33bw
from pandapower.topology import create_nxgraph
import networkx as nx


def solve(net, algorithm="nr"):
    pp.runpp(net, algorithm=algorithm, init="flat", numba=False,
             tolerance_mva=1e-10, max_iteration=100)
    if not net.converged or not np.isfinite(net.res_bus.vm_pu).all():
        raise RuntimeError("Power flow did not produce finite converged voltages.")
    return net


def benchmark():
    net = case33bw()
    graph = create_nxgraph(net)
    if len(net.bus) != 33 or not nx.is_tree(graph):
        raise ValueError("Expected a connected radial 33-bus benchmark.")
    if list(net.bus.index) != list(range(33)):
        raise ValueError("Unexpected case33bw bus indexing; review source-label mapping.")
    # This bundled conversion uses indices/names 0..32; MATPOWER uses 1..33.
    net.bus["source_bus_label"] = net.bus.index + 1
    return net


def two_bus_check():
    """Small voltage drop: compare AC solution to an approximate hand calculation."""
    net = pp.create_empty_network()
    source = pp.create_bus(net, vn_kv=12.66)
    load_bus = pp.create_bus(net, vn_kv=12.66)
    pp.create_ext_grid(net, source, vm_pu=1.0)
    pp.create_line_from_parameters(net, source, load_bus, length_km=1.0,
        r_ohm_per_km=0.4, x_ohm_per_km=0.3, c_nf_per_km=0.0, max_i_ka=1.0)
    pp.create_load(net, load_bus, p_mw=0.1, q_mvar=0.04)
    solve(net)
    # R and X are per phase; P and Q are total three-phase powers.
    approximate_drop_pu = (0.4 * 100000 + 0.3 * 40000) / 12660**2
    simulated_drop_pu = 1.0 - float(net.res_bus.vm_pu.at[load_bus])
    current_a = float(net.res_line.i_ka.iloc[0]) * 1000
    independent_loss_mw = 3 * current_a**2 * 0.4 / 1e6
    return {
        "approximate_drop_pu": approximate_drop_pu,
        "simulated_drop_pu": simulated_drop_pu,
        "drop_relative_error": abs(simulated_drop_pu - approximate_drop_pu) / approximate_drop_pu,
        "independent_loss_mw": independent_loss_mw,
        "simulated_loss_mw": float(net.res_line.pl_mw.iloc[0]),
    }


def validation(net):
    other = deepcopy(net)
    solve(other, "bfsw")
    balance = (net.res_ext_grid.p_mw.sum() - net.res_load.p_mw.sum()
               - net.res_line.pl_mw.sum())
    return {
        "power_balance_residual_mw": float(balance),
        "max_solver_voltage_difference_pu": float(abs(net.res_bus.vm_pu - other.res_bus.vm_pu).max()),
        "two_bus": two_bus_check(),
    }
