# Solar Hosting Capacity of a 33-Bus Distribution Feeder

**v1.0.0 — completed voltage-only study, with explicit numerical limitations.**

Python + pandapower + an independently checked radial AC solver. Compare solar
placement and local inverter control across four synthetic days; inspect the
results, assumptions, and validation rather than relying on one headline number.

![Hosting comparison](reports/study/hosting_comparison.png)

## Main finding

Remote solar's largest tested voltage-feasible endpoint increased from **1.83 MW
to 3.02 MW** with Volt-VAR control. At equal 1.83 MW capacity, peak voltage fell,
but four-day loss energy increased approximately **5.6%**. These are scenario-based
simulation findings, not interconnection approvals or proven global optima.

| Placement | Control | Feasible lower endpoint (MW) | Infeasible upper endpoint (MW) | Unresolved sweep points |
| --- | --- | --- | --- | --- |
| distributed | unity_pf | 3.25062 | 3.27965 | 0 |
| distributed | volt_var | 4.81789 | 4.84691 | 0 |
| upstream | unity_pf | 5.34031 | 5.36934 | 0 |
| upstream | volt_var | 6.96562 | 6.99465 | 0 |
| remote | unity_pf | 1.82848 | 1.8575 | 0 |
| remote | volt_var | 3.01844 | 3.04746 | 5 |

**Caveat:** five high-capacity remote-control points remain unresolved due to
controller nonconvergence. Full sweeps retain and label failures. Both endpoints
of the reported local voltage-boundary brackets converged.

## Open these first

- [Engineering report](reports/study/engineering_report.md)
- [Original benchmark report](reports/baseline/report.md)
- [Upload guide](GITHUB_UPLOAD.md)
- [Hosting summary CSV](reports/study/hosting_summary.csv)
- [Validation CSV](reports/study/independent_solver_checks.csv)
- [Narrated video information](media/README.md)

## Reproduce

Python 3.12 was tested. From this folder on Windows:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-lock.txt
.venv/Scripts/python -m pip install --no-deps -e .
.venv/Scripts/python -m pytest -q
.venv/Scripts/python -m solar_hosting.cli
.venv/Scripts/python -m solar_hosting.study
.venv/Scripts/python tools/build_report.py
```

On Linux/macOS replace `.venv/Scripts/python` with `.venv/bin/python`.
The independent study sweep takes several minutes, depending on hardware.
`run-local.ps1` reuses the prepared environment on the original workspace machine.
It is not a portable environment; use the installation commands on other machines.

Core dependencies are pinned in requirements-lock.txt. Optional video tools are
listed separately in requirements-media.txt. No paid software or hardware is required.
The MP4 is a deliverable; rebuilding it requires the documented local voice and fonts.

## Model choices

- Original benchmark stays unmodified, with its original undervoltage documented.
- Solar study separately assumes 1.03 p.u. source voltage and synthetic demand.
- Study band: 0.95–1.05 p.u.; not a claim of regulatory compliance.
- Distributed PV follows load weights; upstream buses: 3, 4, 5; remote: 18, 22, 33.
- Inverter S/P=1.10; active-power priority; no nighttime Q; no curtailment.
- Control deadband 0.99–1.01; saturation at 0.95/1.05; explicit Q capability limit.
- 15-minute steps, four days, baseline gates, capacity-grid/refinement search.
- Sensitivities: demand ±10%, source ±0.01 p.u., inverter ratios 1.0/1.2, 5-minute steps.
- No thermal, protection, harmonic, unbalance, dynamic, or annual-performance claim.

## Validation

Nine tests passed locally. Independent radial/pandapower comparison covers 54
operating points, with maximum voltage difference 3.014e-11 p.u.
Checks include power balance, analytic two-bus approximation, 3 I² R losses,
no-load behavior, generator Q signs, control convergence, and capability clipping.
GitHub Actions is configured but has not been executed on GitHub by this release.

## Repository map

| Path | Purpose |
|---|---|
| `src/solar_hosting/model.py` | Benchmark and baseline numerical verification |
| `src/solar_hosting/cli.py` | Baseline CLI, tables and chart |
| `src/solar_hosting/study.py` | Profiles, AC solver, control, sweeps, sensitivities, plots |
| `tests/` | Physical behavior and numerical tests |
| `tools/build_report.py` | Generate report and README from actual results |
| `tools/make_video.py` | Entirely local narration and bilingual video rendering |
| `reports/baseline/` | Original unmodified feeder evidence |
| `reports/study/` | Full result tables, charts, metadata and engineering report |
| `data/README.md` | Data provenance |
| `media/` | Video, subtitles, script and asset credits |
| `release-manifest.json` | SHA-256 hashes of delivered repository files |

## Limitations and next research

Only selected scenarios and constraints are studied. Synthetic data are not field
measurements. Numerical controller convergence does not establish dynamic stability.
Resolve high-capacity controller failures before claiming a global maximum. Future
extensions include independent OpenDSS comparison, measured profiles, curtailment,
and equipment-rated unbalanced feeders. These are outside this release's core scope.

## License and references

Original code: MIT. Third-party software, data, fonts and voices retain their own
licenses. Arabic text is confined to the requested video translations; engineering
documentation is English. See data/README.md and media/README.md for attribution.

- Baran & Wu (1989): https://doi.org/10.1109/61.25627
- MATPOWER: https://matpower.org/docs/ref/matpower6.0/case33bw.html
- Pandapower: https://pandapower.readthedocs.io/en/v3.3.2/networks/power_system_test_cases.html
