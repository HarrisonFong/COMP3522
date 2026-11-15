# COMP3522: four geographic factors, Temperature and Rainfall

Completed exploratory retrospective analysis, 2026-11-14. The Chinese report is `index.html` in the delivered `COMP3522_Geographic_Factors` folder. Open it directly in a browser. Figures and interactive records are embedded; retain `results/` and `code/` for evidence links. The sibling ZIP contains the report, figures, all aggregate tables, provenance and scripts. It deliberately does not redistribute raw observations, case-level predictions or large GIS inputs.

## Main findings

The same public forecast is matched to different AWS observations: raw errors measure geographic representativeness, not the skill of independent native station forecasts. Elevation and coastal position have clearer temperature associations. Lowland-only matched D3 coastal differences remain negative, while urban and terrain rankings can change when mountain stations are excluded. Small geographic samples and correlated factors prevent causal claims.

Known-station mean/median temperature correction is already effective; the additional boosting advantage over station mean has time-block intervals including zero. Ridge has lower 2025 unseen-region point errors than boosting. Rain-event model gains over category means are small. Rain-amount MAE advantages over means do not establish ML superiority: category medians are competitive, and absolute-error boosting substantially underpredicts amount. Numerical rainfall is a research mapping from PSR, not an official native mm forecast.

## Source and paths

Original project root: `C:/Users/Sena/Documents/ChatGPT/Project FYP - demo`.
Scripts normally live at `geographical-research/analyses/11_geographic_factors/`, from which the project root is derived. The copies in the evidence ZIP are archival; place them in that relative layout to rerun, or update path constants deliberately.

Required existing snapshots, all read only:

- `analysis/initial-reliability/all-data/{forecasts,observations,series,stations}.csv`
- `analysis/geographic-representativeness/results/station_geography.csv` and `geography_specification.json` (earlier geographic enrichment, including complete candidate flags, coastline and 250/500/1000 m land use).
- `analysis/regional-altitude/sources/hk_sea.json` (marine mask).
- `analysis/geographic-factors-20261114/sources/Whole_HK_DTM_5m.asc`, extracted from the official named ZIP linked in `results/terrain_provenance.json`. Do not substitute an unknown later DTM without recording provenance and rerunning everything.

The earlier enrichment scripts and their underlying GIS sources remain in the original project. This package contains the derived station features and specifications but is not a standalone raw-source distribution. The sources' hashes are in `model_metadata.json`, `terrain_provenance.json`, and `geography_specification.json`. Local Git HEAD is `042ce8931f7eda185e034c730521b834bf90e600`; inspected upstream main was `435396e6cd870f70ea5e73026f2acf7c023f13d7`. New analysis has not been pushed.

## Environments and reproduction

Numerical environment: repository `.venv`, Python 3.14.6, NumPy 2.5.4, pandas 3.1.1, scikit-learn 1.9.1, Matplotlib 3.11.2; `threadpoolctl` also required. Version strings are the installed environment observed in this session, not a promise of availability on every package index.

GIS environment: bundled Python 3.12.14 at `C:/Users/Sena/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`; `build_terrain.py` and its verifier prepend `analysis/geographic-representativeness/.deps` containing rasterio 1.5.2, pyproj and shapely. The report uses Windows Microsoft JhengHei if available. Separate environments avoid the GIS wheel limitation in the numerical Python version.

Run from the project root using PowerShell. Each command is separate. Intermediate large cases and predictions are written to `analysis/geographic-factors-20261114/`; aggregates to the scripts' `results/` directory. No database is opened.

```powershell
$geoPython = 'C:/Users/Sena/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$modelPython = './geographical-research/.venv/Scripts/python.exe'
$analysisDir = './geographical-research/analyses/11_geographic_factors'
$env:PYTHONIOENCODING = 'utf-8'
& $geoPython "$analysisDir/build_terrain.py"
& $geoPython "$analysisDir/verify_terrain.py"
& $modelPython "$analysisDir/run_models.py"
& $modelPython "$analysisDir/analyze_geography.py"
& $modelPython "$analysisDir/summarize_results.py"
& $modelPython "$analysisDir/run_sensitivity.py"
& $modelPython "$analysisDir/lowland_contrasts.py"
& $modelPython "$analysisDir/verify_analysis.py"
& $modelPython "$analysisDir/verify_summaries.py"
& $modelPython "$analysisDir/verify_lowland.py"
& $modelPython "$analysisDir/build_report.py"
```

`build_report.py` currently publishes to `Z:/study/yr4/sem1/comp3522/5_Part1_Finalisation/COMP3522_Geographic_Factors`; change `DEST` for another machine. No model fitting is needed just to rebuild the report from supplied aggregates. `add_amount_baselines.py` is retained as development provenance; the current full `run_models.py` already includes those baselines, so do not rerun that legacy supplement in the standard sequence.

## Design and metrics

- 32 temperature AWS and 20 rainfall AWS; all eligible candidates, including TC/TMS. 2022–2025 C observations, daily latest archived forecast per issue/target date, HKT D1–D9, no imputation. Geographic data are static proxies; see PLAN.md.
- Temperature: predict observation minus public forecast; add correction back to public forecast. Event: local daily rainfall >=10 mm. Amount: local numeric rainfall, not PSR expressed in native mm. C Trace is below the event threshold; omitted from amount, never assigned zero. These selected AWS contain no resulting event/amount sample count difference.
- 2022–2023 train, 2024 tune; 2022–2024 final fit, both issue/valid dates in 2025 for test. No final training target overlaps a validation/test issue date.
- Unseen-region: deterministic five coordinate KMeans groups, longitude scaled by cosine 22.3°, seed 3522, n_init 20. Exclude held group from training and tuning. Geography has no coordinate predictors. Unknown station mean/median corrections use explicit training-network/category fallback.
- Primary means use equal station × lead weights. Numerical targets: MAE, RMSE, Bias. Binary event: Brier, log loss; pooled threshold confusion tables are explicitly different weighting. Category/station empirical probabilities have fallback for absent groups, not smoothing.
- Temperature/numeric Ridge alpha 1/100/10000; event Logistic C .1/1/10. HGB 7/15 leaves, learning rate .07, min leaf 150, L2 1, no early stopping, seed 3522. Primary HGB 80 rounds; numerical primary uses absolute error. Rainfall diagnostic extras: 500-round absolute error, 80-round squared error, zero/category median/station median. These are declared post-diagnostic additions, still tuned on 2024.
- Geography: elevation; log(1+coastal distance km); developed effective-land ratio; slope/TPI z/relief. Mean-group models use prescribed bins. Terrain derives from DTM with sea masked, not invented field classifications. Continuous and categorical proxies are both supplied.
- D3 geographic comparisons match dates within each cross-group station pair, then give pairs equal weight; different pairs need not share all dates. Strict network-common dates and available-case descriptive means are separate tables.
- 2,000 circular calendar-block bootstrap samples, primary 14 days, 7/28 sensitivity, models held fixed. Intervals apply to these stations and fitted models, not a new-station population. No multiplicity adjustment. Existing 2025 outcomes had already been inspected; do not label this prospective confirmation.

## Evidence index

- `station_factors.csv`, `station_design.csv`, `group_station_counts.csv`: labels, continuous measurements, support, candidates and spatial folds.
- `geographic_means.csv`: D1–D9 original temperature error or observed rainfall distribution summaries. Rain frequency/amount is not forecast skill.
- `geographic_matched_contrasts_D3.csv`, `geographic_pair_support_D3.csv`: date-matched contrasts and every pair's support.
- `lowland_matched_contrasts_D3.csv`: same method restricted to 29 stations below 300 m; contrast text specifies difference orientation.
- `geographic_strict_common_D3.csv`: common-date sensitivity (only 24 days for full temperature network).
- `geographic_label_sensitivity_D3.csv`: terrain radius/cut and urban radius/broad-code regrouping; `geographic_model_sensitivity.csv`: refitted radius and lowland models on identical eligible cases.
- `method_metrics.csv`, `method_intervals.csv`, `paired_method_differences.csv`: all primary methods and paired uncertainty. Negative paired loss difference favours the named method.
- `factor_drop_comparisons.csv`: separately refit models dropping one factor, full-model hyperparameters fixed. Positive means incremental predictive information conditional on other factors, never causal or additive percentage.
- `method_by_geographic_group.csv`: interactive table source. `rain_event_threshold_metrics.csv`: pooled event confusion counts at .2/.35/.5.
- `*_validation_grid.csv`, `*_selection.csv`, `all_method_validation.csv`, `validation_recommendations.csv`, `empirical_fallback_usage.csv`: tuning, method choice, fallback auditing.
- `coverage.csv`, `coast_leave_one_station_out.csv`, `factor_spearman.csv`: missing-date coverage, influential-site checks, site-level factor correlations.
- `independent_verification.json`: raw-source joins and 140 independent model refits; `terrain_verification.json`: original ASC/derived TIFF checks and analytical planes; `summary_verification.json`: independent aggregations; `lowland_verification.json`: additional restricted contrasts.

Verification establishes that the implementation matches the documented calculation. It does not validate scientific assumptions or transform the 32/20 stations into a representative random sample of all Hong Kong locations.
