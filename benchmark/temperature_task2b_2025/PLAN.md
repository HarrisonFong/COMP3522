# Task 2b temperature correction: controlling benchmark

Source: Canva design DAHa6VKHCZw, actual page 7, “Task 2a — Benchmark
Definition”, read on 2026-11-16 HKT. User confirmed the controlling valid
window is **HKT [00:00, next 00:00)**, not an afternoon-to-afternoon day.
Only temperature is redone. The rainfall publication is unchanged.

## Governing definition

- HKO Headquarters observations, 1 Jan–31 Dec 2025.
- Daily Tmax/Tmin in Celsius; same target date and HKT natural-day window.
- Compare nearest grid and bilinear alignment, record positions and heights.
- MAE primary, RMSE; by variable and lead; revision frequency, magnitude and
  RevisionGain = old absolute error minus new absolute error.
- Paired 95% intervals; if forecast missingness reaches 30%, no full-year
  superiority claim. Distinguish missing values from unavailable evidence.

## Implementation and evidence boundaries

The deck's temperature page (actual page 8) separately describes GFS 00 UTC
runs and an HKO 14:00 HKT forecast-selection cutoff. That cutoff is NOT the
valid-window start. It remains a separately labelled reproduction scenario;
all targets always start at HKT midnight. HKO bulletin and RSS times must
precede the cutoff, and issue date and actual forecast age are retained.

The local HKO source capture timestamps inspected so far are 2026 historical
backfills. They cannot establish 2025 archive-confirmed availability. Verify
this across selected records, show the strict availability gate, and never
claim the deck's “archive-confirmed” wording has been verified by these dates.
Previously printed slide numbers are hypotheses to reconcile, not inputs to
force the new calculations to match.

GFS four-neighbor values are obtained again from original NOAA TMP messages,
not manufactured from the previously stored single point. Store only four-cell
extracts, source URLs/index lines/byte ranges, hashes and native metadata;
hold raw global messages in worker memory and never import into the database.
Runs: every 00 UTC initialization needed by target dates and calendar leads
1–7. Common three-hour outputs +15 to +186 cover the entire relevant sequence
of HKT days, including both midnight brackets.

Interpolate instantaneous temperature spatially FIRST, then reconstruct a
continuous piecewise-linear time trajectory and restrict it to each exact
HKT window. Max/min of this trajectory are explicitly labelled temporal
proxies, not native exact GFS daily extrema. No spatial interpolation of
cell-specific daily extrema is substituted for extrema of interpolated
temperature. Never extrapolate in time or space. Report native sampled
extrema as a temporal sensitivity and disclose the finite-output limitation.

The valid window can be aligned exactly even though temperature between model
outputs remains approximated. Consequently there is no claim of an exact
operational daily-extremum benchmark, even if every proxy case is complete.
The strict historical-availability comparison is reported separately from
the retrospective timestamp-proxy experiment.
Use the existing nearest-point native TMAX/TMIN intervals as a separate temporal
diagnostic, preserving conditional encoding padding and cross-day envelopes.
Do not invent corresponding bilinear native intervals from one grid point.

Primary spatial contrast: bilinear AE minus nearest AE on identical dates,
leads, runs, temporal reconstruction and truth. HKO comparisons use the same
three-way intersection. Day-to-day revision comparisons hold target date,
variable, method and selection rule fixed, D7→D6 through D2→D1. Include no
change opportunities and report a common >=1 C threshold and rounding check.
Circular calendar block bootstrap: 2,000 replicates, seed 3522, seven-day
blocks; all leads/products on a target date resampled together. Fourteen-day
blocks are a sensitivity. Do not treat 2,555 cases as independent weather days.

The earlier 20:00/nearest-only analysis is retained as a superseded experiment,
not used as the Task 2b answer. Publish reproducible corrected evidence and
plain-language conclusions; no Canva edits or rainfall recomputation.
