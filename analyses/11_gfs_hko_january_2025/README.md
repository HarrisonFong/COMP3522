# January 2025 GFS–HKO comparison trial

Start with the [Traditional-Chinese findings](results/findings.md) and the
[fixed comparison protocol](PLAN.md). This extends the existing benchmark pilot
using the completed GFS acquisition. It does not change the database.

Target dates: 2025-01-01 through 2025-01-31. Temperature: matched D1–D7,
common 20:00 HKT cutoff, GFS nearest HQ grid point, daily endpoint reconstruction
midpoint proxy and explicitly assumed six-hour availability delay. Alternative
cutoffs/delays, temporal sensitivity ranges and instantaneous-sample extrema
are retained. RH and rainfall have HKO-only diagnostics and explicit external
data/definition gaps; no GFS RH/rainfall values are invented.

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s analyses/11_gfs_hko_january_2025 -p test_methods.py -v
.\.venv\Scripts\python.exe analyses/11_gfs_hko_january_2025/run_analysis.py
.\.venv\Scripts\python.exe analyses/11_gfs_hko_january_2025/verify_results.py
.\.venv\Scripts\python.exe analyses/11_gfs_hko_january_2025/build_report.py
```

`run_analysis.py --offline` reuses the ignored local snapshot; otherwise the root
`.env` connection is enforced read-only. `verify_results.py` independently
recomputes saved arithmetic/reconstructions and checks all selected forecast
versions with separate live read-only SQL. The exact source queries and input,
code and weight fingerprints are retained. The verifier checks selection under
stated delay assumptions; it cannot establish historical publication evidence.

The 31 weather dates do not support a whole-year or all-weather ranking. Images
are reproducible scientific figures in the established repository report format.
