"""Reproduce the unmodified feeder baseline and save English-language artifacts."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .model import benchmark, solve, validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/benchmark.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/baseline"))
    args = parser.parse_args()
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    low, high = cfg["voltage_min_pu"], cfg["voltage_max_pu"]
    if not 0 < low < high:
        raise ValueError("Voltage limits must be positive and ordered.")
    for key in ("power_balance_tolerance_mw", "solver_voltage_tolerance_pu"):
        if cfg[key] <= 0:
            raise ValueError(f"{key} must be positive.")
    net = solve(benchmark())
    checks = validation(net)
    two = checks["two_bus"]
    checks["passed"] = bool(
        abs(checks["power_balance_residual_mw"]) < cfg["power_balance_tolerance_mw"]
        and checks["max_solver_voltage_difference_pu"] < cfg["solver_voltage_tolerance_pu"]
        and two["drop_relative_error"] < 0.01
        and abs(two["independent_loss_mw"] - two["simulated_loss_mw"]) < 1e-9
    )
    buses = net.res_bus.copy()
    # Source bus labels are retained explicitly; do not confuse them with zero-based indices.
    buses.insert(0, "source_bus_label", net.bus["source_bus_label"].astype(str))
    buses["below_study_limit"] = buses.vm_pu < low
    buses["above_study_limit"] = buses.vm_pu > high
    worst = buses.vm_pu.idxmin()
    summary = {
        "case": "Unmodified Baran-Wu case33bw; no solar; fixed original source voltage",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "versions": {x: importlib.metadata.version(x) for x in ["pandapower", "numpy", "pandas", "scipy", "matplotlib"]},
        "configuration": cfg,
        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest(),
        "bus_count": len(net.bus),
        "active_line_count": int(net.line.in_service.sum()),
        "load_mw": float(net.res_load.p_mw.sum()),
        "load_mvar": float(net.res_load.q_mvar.sum()),
        "source_mw": float(net.res_ext_grid.p_mw.sum()),
        "line_losses_kw": float(net.res_line.pl_mw.sum() * 1000),
        "minimum_voltage_pu": float(buses.vm_pu.min()),
        "maximum_voltage_pu": float(buses.vm_pu.max()),
        "minimum_voltage_source_bus": str(buses.at[worst, "source_bus_label"]),
        "undervoltage_bus_count": int(buses.below_study_limit.sum()),
        "overvoltage_bus_count": int(buses.above_study_limit.sum()),
        "baseline_voltage_feasible": bool(not (buses.below_study_limit | buses.above_study_limit).any()),
        "validation": checks,
    }
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    buses.to_csv(out / "bus_results.csv", index_label="pandapower_bus_index")
    # Omit loading_percent because source thermal ratings are not established here.
    net.res_line[["p_from_mw", "q_from_mvar", "p_to_mw", "q_to_mvar", "pl_mw", "i_ka"]].to_csv(
        out / "line_results.csv", index_label="pandapower_line_index")
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    fig, ax = plt.subplots(figsize=(10, 5.2), layout="constrained")
    ax.plot(range(1, len(buses) + 1), buses.vm_pu, "o-", color="#176B87", ms=4,
            label="Simulated baseline voltage")
    ax.axhspan(low, high, color="#43AA8B", alpha=0.12, label="Assumed study band")
    ax.axhline(low, color="#B23A48", ls="--", lw=1)
    ax.axhline(high, color="#B23A48", ls="--", lw=1)
    ax.set(xticks=range(1, 34, 2), xlabel="Source bus number (not physical distance)",
           ylabel="Voltage magnitude (p.u.)", title="33-bus feeder | Original baseline, no solar")
    ax.grid(alpha=0.2)
    ax.legend(loc="lower left")
    fig.savefig(out / "voltage_profile.png", dpi=180)
    fig.savefig(out / "voltage_profile.svg")
    plt.close(fig)
    report = f"""# Baseline engineering report

Status: simulated baseline milestone, not a completed hosting-capacity study.

## Model and assumptions

Unmodified Baran-Wu 33-bus case from pandapower {summary['versions']['pandapower']}.
Balanced steady-state AC power flow, constant PQ demand, original radial topology,
original source voltage, no solar and no controller. The {low:.2f}–{high:.2f} p.u.
voltage band is an assessment assumption, not a claimed regulatory requirement.

## Simulated results

| Metric | Value |
|---|---:|
| Total demand | {summary['load_mw']:.4f} MW |
| Reactive demand | {summary['load_mvar']:.4f} MVAr |
| Source real power | {summary['source_mw']:.6f} MW |
| Line losses | {summary['line_losses_kw']:.3f} kW |
| Minimum voltage | {summary['minimum_voltage_pu']:.6f} p.u. |
| Minimum-voltage source bus | {summary['minimum_voltage_source_bus']} |
| Buses below study band | {summary['undervoltage_bus_count']} |
| Buses above study band | {summary['overvoltage_bus_count']} |
| Baseline within study band | {summary['baseline_voltage_feasible']} |

![Baseline voltage](voltage_profile.png)

## Numerical verification

- Power-balance residual: {checks['power_balance_residual_mw']:.3e} MW.
- Maximum Newton-Raphson / backward-forward sweep voltage difference: {checks['max_solver_voltage_difference_pu']:.3e} p.u.
- Independent two-bus voltage-drop approximation relative error: {two['drop_relative_error']:.3%}.
- Two-bus calculated 3 I^2 R loss: {two['independent_loss_mw']:.9f} MW.
- Two-bus simulated loss: {two['simulated_loss_mw']:.9f} MW.
- Numerical checks passed: {checks['passed']}.

Solver agreement is a cross-check within one library, not independent software validation.
The voltage-drop approximation is used only for a lightly loaded two-bus case.

## Interpretation and next step

Numerical correctness and voltage acceptability are different checks. If the baseline
is outside the assumed band, that is a pre-existing issue, not an effect of solar.
Do not infer a solar hosting capacity from this baseline. Next, define a separate,
explicit study configuration and test its no-solar feasibility before solar sweeps.
No limits, loads, or source settings have been silently changed to obtain compliance.

Thermal compliance, protection, unbalance, harmonics, and dynamic behavior are not
assessed. Line currents are exported, but thermal loading percentages are omitted.
This is a synthetic benchmark, not a model of a named utility feeder.

## Provenance

- https://pandapower.readthedocs.io/en/v3.3.2/networks/power_system_test_cases.html
- https://matpower.org/docs/ref/matpower6.0/case33bw.html
- Baran and Wu (1989), DOI: 10.1109/61.25627.

See summary.json for configuration, versions, timestamp, and numerical checks.
"""
    (out / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if not checks["passed"]:
        raise SystemExit("Numerical validation failed; review saved diagnostics.")


if __name__ == "__main__":
    main()
