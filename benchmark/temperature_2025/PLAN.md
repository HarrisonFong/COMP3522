# Frozen analysis plan: 2025 HKO–GFS temperature and revision comparison

Set on 2026-11-16 HKT, before computing annual scores. This extends the January
trial without changing it or the teammate's rainfall workflow results.
Execution refinements are explicitly recorded below: the +196 h horizon
qualification, chain-endpoint bounds, and interval-boundary diagnostics. This
working plan is not a preregistration; the project had already explored January.

- Target: 2025-01-01 through 2025-12-31 HKT calendar-day Tmax and Tmin at HQ.
  Both use the same numeric, completeness-C HQ observations; report coverage
  and exclusions rather than imputing. No database writes.
- Primary: latest HKO bulletin/RSS before 20:00 HKT on D7 through D1; latest
  GFS initialization plus an **assumed** six-hour release lag before that same
  cutoff. Initialization/retrieval do not establish historical availability.
  Keep stale HKO issues and their actual ages visible. Select a run before
  checking its data, so incomplete newer runs cannot silently become older runs.
- GFS: existing nearest point, 22.25 N / 114.25 E, about 9.71 km from HQ.
  No bilinear or terrain correction is possible from this single-point extract.
  Use the January interval method, padding max(0.02 C, native packing step).
  Fully contained interval extrema constrain one endpoint; intersecting intervals
  covering 24 hours constrain the other. Midpoint is a disclosed plotting/scoring
  proxy, not an exact daily extremum. Also report AE bounds and sampled extrema.
- Accuracy: paired MAE, RMSE, signed bias, D1–D7, seasons and D1 months.
  Difference = GFS AE minus HKO AE, positive favors HKO. Primary and sensitivity
  inference uses calendar circular block bootstrap, 2,000 draws, seed 3522,
  7-day blocks and a 14-day primary sensitivity; all leads move with target date.
  Two main endpoints, Tmax and Tmin; subgroup intervals are exploratory,
  unadjusted and describe this year's weather-date variability.
- Timing sensitivities: 20 HKT with lag 4/8/12 h; 12/16 HKT with lag 6 h.
  Additional 02/08 HKT with lag 6 h support a shared six-hour inspection grid.
  Always compare common cases within a scenario; report changing coverage.
- Revision: match the **same target date and variable** at successive cutoffs.
  Primary cadence 24 h: D7→D6 through D2→D1 at 20 HKT. Secondary cadence 6 h:
  02/08/14/20 HKT from D7 02 through D1 20 (nominally 27 opportunities).
  Engineering qualification: D7 02 requires output through +196 h, exceeding
  the acquired +192 h horizon. Exclude that slot, leaving D7 08 through D1 20,
  26 common six-hour opportunities per target; retain its 730 exclusions.
  14 HKT is an additional lag-6 scenario. Require both products at both ends.
- Report native changed-value rate, >=1 C material-change rate, change magnitude,
  improved/worsened/tied share, and AE(old)-AE(new), positive = useful.
  Primary usefulness denominator is **all common opportunities**, including no
  change. Conditional usefulness among native/material changes has a different
  denominator and is descriptive. Native floating GFS and integer HKO frequency
  is not precision matched; include a nearest-integer half-up sensitivity.
- Compare benefit(GFS)-benefit(HKO) on paired opportunities and bootstrap target
  dates. Also calculate conservative benefit ranges from both GFS daily-extremum
  AE ranges. More recovery from a worse initial forecast does not imply better
  final accuracy; check D7/D1 errors and the telescoping identity. Bound pooled
  chain benefits using first/last errors after exact cancellation of intermediate
  errors; individual-step bounds are retained separately. Repeat daily revision
  comparisons under the main timing sensitivity scenarios.
- Revision gain is retrospective association with approaching the event, not
  a causal benefit from update frequency alone. No day-0 or realized weather
  enters the forecast selection rule. Do not rank whole agencies or other years.

Deliverable: a repository Markdown benchmark with reproducible CSV evidence,
scientific PNG figures, code and independent validation, then push to GitHub.
