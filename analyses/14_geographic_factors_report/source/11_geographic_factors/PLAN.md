# Four geographic factors and method comparison

User goal, 2026-11-14: complete elevation, coastal position, urban land use and terrain for Temperature and Rainfall; compare simple means, statistical models and ML and derive evidence-based conclusions. Existing 2025 results are known, so this is exploratory retrospective evaluation, not a pristine prospective test. Do not tune using 2025 scores.

## Source and cohort

Use existing read-only 2022–2025 forecast/observation CSV snapshots. All 32 full-period AWS temperature candidates and all 20 rainfall candidates from the audited inventory, including TC/TMS. No selection by errors, top-N coverage selection, imputation, or database writes. HKO/HKA are reference sites, not AWS groups. Forecast selection: daily latest per issue/target date, HKT calendar leads D1–D9. C numerical observations only; C Trace is below the 10 mm event threshold. For experimental numerical rainfall, exclude Trace and report that difference rather than assign zero.

Factors: elevation <300 / 300–<700 / >=700 m; coastline <=500 / >500–2000 / >2000 m; developed effective-land ratio within 500 m <.2 / .2–<.5 / >=.5. Reuse the documented restricted developed codes, excluding water/airport. No season predictor or seasonal clustering in the primary experiment, as requested; month/year coverage is still audited. Land-use buffers 250/1000 m and broader developed codes are sensitivities.

Acquire official Lands Department 5 m DTM. Record its provenance and limitations (including above-ground/vegetation contamination). Derive slope, relief, standardized relative elevation and a four-class terrain proxy from fixed rules before fitting forecast models. Primary radius 500 m, sensitivity 250/1000 m. Thresholds: standardized relative elevation <=-1 valley/depression, >1 ridge/top, intermediate with local plane slope <5 degrees flat/gentle terrain, otherwise slope. This operational four-class proxy adapts TPI+slope classification, not validated field geology, hydrological valley mapping or an exact SAGA implementation. Continuous variables retain information lost by categories. Use marine masking and expose small-island/edge support. Do not change thresholds to obtain desired errors or class counts.

## Two distinct questions

1. Geographic representativeness: same unmodified public forecast, observed at different stations. Means/MAE/RMSE/Bias by each factor and matched station-pair contrasts at the same date and lead. Pair-specific common dates need not be a network-wide common set. Also show strict all-site common-date and lowland/high-site sensitivities; don't make causal factor claims.
2. Experimental local prediction: fit statistical corrections / local event or amount models from public forecast and static geography. Predictions must be out-of-time and compared on identical cases for each target. These are research-derived forecasts, not native station forecasts or official PSR calibration.

## Models and evaluation

Temporal: 2022–2023 train, 2024 validation; refit 2022–2024 and evaluate issue and valid dates both in 2025. Ensure training valid dates precede validation issue dates (boundary embargo). For tuning compare a small fixed grid; early stopping disabled to avoid shuffled validation. Per station/lead equal weighting for fitting and primary scoring. Every method sees the same held-out cases for a given target.

Temperature targets Tmax/Tmin: raw public forecast, training global-mean residual correction, station-mean correction, station-median correction, separate factor-group mean corrections, Ridge and histogram boosting with/without four geographic groups. Mean/median corrections use training data only.

Rain event target local daily rainfall >=10 mm: PSR-category empirical event mean (local calibration baseline), station/category empirical event mean with a category fallback for absent combinations (no smoothing), single-factor/category means, logistic regression and histogram boosting with/without geography. Brier score is primary; log loss and threshold-specific hit/FAR/miss/accuracy and base rate supplementary. Public PSR Medium High+ is only a shared decision-rule reference, not a local probability forecast. Do not use midpoint coding as ground-truth probabilities.

Rain amount target: explicitly experimental mapping from PSR/lead/geography to local millimetres; global and station means, factor-group means, Ridge and boosting. MAE primary, RMSE/Bias supplementary. Numeric-only observations; no native PSR mm error claimed.

After the first numeric-rainfall fits, add a zero-amount diagnostic and PSR-category / station-category medians. These extra baselines are documented post-result additions: boosting uses absolute-error training, so a comparison only against means could mistake a loss-function benefit for an ML or geographic benefit. No existing ML hyperparameters are changed. Temperature unseen-site mean/median corrections both use the training-network lead-mean fallback; rainfall median methods use a training category-median fallback.

The first 80-round amount booster has a large dry bias. To check that the method comparison is not an artefact of its training budget/loss, additionally evaluate a 500-round absolute-error booster and an 80-round squared-error booster. Both use the same 7/15 leaf validation grid and spatial exclusion rules, without 2025-based parameter choice. These are explicitly post-diagnostic additions. Primary four-factor drop experiments retain the original 80-round family; supplementary families are labelled separately.

Spatial: five deterministic coordinate clusters, refit and tune excluding each held-out cluster from both training and validation; evaluate its 2025 cases. Unseen-site station corrections use an explicit training-network fallback, not held-out observations. Contrast known-site and unseen-site conclusions.

Attribution: retrain full Ridge/logistic and boosting after dropping each of the four factor groups. A positive loss increase means incremental predictive information conditional on remaining features; not causal importance and contributions do not sum to 100%. Report signed differences and paired time-block intervals. Fixed fitted models during resampling, 7/14/28-day sensitivity; fixed-station uncertainty only.

## Required completion evidence

All four factor definitions, values, coverage and classification sensitivity; all target/model/temporal and spatial evaluations; same-case predictions and split/tuning audit; group means and matched geographic contrasts with uncertainty; drop-factor comparisons; meaningful independent numerical/source checks; Chinese HTML conclusions, data/methods/logic/assumptions, figures and captions, downloadable evidence tables and reproducible scripts. No final completion claim while any requirement lacks evidence.
