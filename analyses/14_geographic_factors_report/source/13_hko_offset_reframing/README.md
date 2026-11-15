# HKO-reference offset and geographical interpretation

This extension preserves the existing 2023/2024 validation choice, independently
reproduces the old 30-station results, and evaluates the same frozen method in
all 32 AWS and the 29 stations below 200 m. The 200 m and earlier 300 m cutoffs
select identical stations in this sample. HKO is the reference, not TMS.

Run from the outer project directory with the numerical Python environment:

```powershell
.\geographical-research\.venv\Scripts\python.exe geographical-research/analyses/13_hko_offset_reframing/run_analysis.py
.\geographical-research\.venv\Scripts\python.exe geographical-research/analyses/13_hko_offset_reframing/verify_analysis.py
.\geographical-research\.venv\Scripts\python.exe geographical-research/analyses/13_hko_offset_reframing/build_report.py
```

`qa_report.cjs` uses the installed Playwright runtime and local Chrome. The HTML
is written to `Z:/study/yr4/sem1/comp3522/5_Part1_Finalisation/COMP3522_Geographic_Factors/deepening/index.html`.
The earlier report remains available as `technical_appendix.html`.
The main report now uses connected, plain-language research prose from
`report_body.html`; `build_report.py` fills its tables and figures from the
verified results. The preceding structured evidence report is preserved as
`evidence_notes.html`. Editing the narrative does not refit the statistical models.
The report now establishes the HKO reference assumption and validates the offset
before interpreting geographical differences. These two opening substantive
sections are maintained in `reference_first_sections.html` and inserted into
`report_body.html`. Figure captions are numbered in reading order; image alt text
uses short descriptions rather than repeating the complete captions.
The formal report's main comparisons and cohort charts now show only all 32
stations and the 29 lowland stations. The original 30-station definition,
validation scores, reproduction provenance and test results are retained in the
`legacy30` appendix. Main validation tables use the actual 32/29-cohort scores;
the original frozen method choices and numerical analyses remain unchanged.

Inputs: local read-only CSV snapshots under `analysis/initial-reliability/all-data`,
eligible cases from analysis 11, station geography from analysis 12, and the
existing `tmp/COMP3522-review/analyses/09_geographic_temperature_v2/results`.
No database writes or additional data imputations are performed. Large case-level
audit files stay outside Git in `analysis/hko-offset-20261114`.

Offset = historical observed station temperature minus observed HKO temperature,
using monthly mean for Tmax and monthly median for Tmin. It is not a correction
fitted directly to forecast residuals. Fits stop in 2024. Test issue and valid dates
both fall in 2025. This is a retrospective hold-year extension, not a pristine
prospective test: earlier analyses have already examined 2025.

`benefits.csv` uses equal station-by-lead MAE; coast contrasts use equal
cross-group station pairs on their own date intersections. Confidence intervals
resample 14-day calendar blocks 2,000 times with seed 3536, holding fitted offsets
and stations fixed. The joint models control date effects and six geographical
features, with optional region controls. They estimate associations, not causes.

Independent checks reconstruct 2025 daily-latest cases from raw forecasts and
complete observations, verify selected offsets, compare all cohort/method MAEs,
recompute the lowland D3 coast estimates and bootstrap intervals, and refit every
joint model using weighted, date-demeaned least squares. Old 30-station scores
and 2,160 offset rows are also reproduced.

Official-source evidence distinguishes historical HQ indicator wording from the
current homepage's explicitly narrower current-day temperature display. Offset
effectiveness and lower HKO errors are compatible with the reference hypothesis;
they cannot establish the official historical nine-day forecast target definition.


Continuous coast and restored methods (2026-11-14):

- Run `analyze_continuous_coast.py` before rebuilding. It fits equal-station
  descriptive OLS, within-date linear models with direct km distance, six-factor
  and region-adjusted sensitivities, and leave-one-station-out slopes. It independently
  verifies 24 date-adjusted coefficient models and the site-slope intervals.
- Run `compare_existing_ml.py` to pair already-fitted predictions with frozen HKO
  observed offsets on identical 2025 cases. No new model fitting or 2025 selection.
- `report_extensions.py` regenerates the new coast scatter, urban counts and
  contrasts, six-factor correlation heatmaps, ML comparisons and factor-drop figures.
  Correlations are independently recomputed from station features; existing ML
  scores and lowland refits are reused from the verified analysis 11 outputs.
- The main report has 12 captioned figures. The original 30-station scope remains
  appendix-only. Direct-km coast associations are distinguished from the log-distance
  variables used in the previous ML experiments.
