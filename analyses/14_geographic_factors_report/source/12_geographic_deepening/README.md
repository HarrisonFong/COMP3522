# Geographic deepening — lowland, urban definitions and joint associations

User-requested extension, 2026-11-14. Read `PLAN.md` for the exploratory design. The delivered Chinese HTML is `COMP3522_Geographic_Factors/deepening/index.html`; the original report links to it from the factors section. This analysis does not replace the earlier results or create new official station forecasts.

## Conclusions

- Ground elevation above mean sea level is the HKO metadata field. The 300/700 m cutoffs are study rules, not official HKO climate categories. Only NGP/TC/TMS provide eligible mid/high elevation temperature data. The 29 lowland sites span 4–142 m, with just one site >=100 m.
- Within lowland, <20 /20–<50 /50–<300 m groups have 11/9/9 stations. Their raw D3 MAEs do not rise monotonically with elevation. All-site Pearson temperature-error correlations are strongly influenced by mountains. Spearman, partial correlation and region-adjusted models give a more qualified account.
- D3 paired inland-minus-near Tmax MAE is 1.779°C for 32 sites, 1.033°C after removing TC/TMS, and 0.715°C after also removing NGP. Corresponding Tmin gaps are 2.173/1.197/0.642°C. Removing TC/TMS alone is not a lowland restriction.
- Urban grouping is definition-sensitive. Broad land use includes recreation/open space and vacant/construction/other uses; after mountain exclusion its low group is only PEN/WGL. Footprint and height intensity measure different aspects. Do not declare a universal urbanization-accuracy relationship.
- Date fixed effects plus six continuous geographic predictors retain a positive coastal association. The lowland Tmax urban coefficient changes sign after four-region adjustment; coefficients are conditional, not causal. District grouping is not an urbanization measure.
- Six old 30-site D3 coastal means are reproduced to floating-point precision. Previous changed-revision-only U/C results, 9-site common-date results, multi-factor forecast-correction results and this geographic loss analysis use different estimands and must not be concatenated into a single ranking.

## Data and outcome definitions

Use the previous verified source snapshots and models from `../11_geographic_factors/`. No database connection or write. Temperature: all eligible 2022–2025 C daily observations paired with daily-latest public D3 forecasts; loss is absolute error, bias is forecast minus observation. Rain: 2025 D3 predictions from the previous temporal test; event loss is squared error of the fixed training-only PSR-category mean probability against local rainfall >=10 mm; amount loss is absolute error of the fixed PSR-category median against mm observed. These are research-derived baselines, not native official local probabilities or amounts. Rain cohort removal changes evaluation sites, not fitted baseline probabilities. The earlier lowland-refit table separately compares training with/without mountain sites on identical lowland cases.

Source station features: previous `results/station_factors.csv`. Coast/land-use/building definitions come from the archived `geography_specification.json` and `building_region_specification.json`. Land use is 2023; coastline/buildings are 2026 snapshots. DTM terrain follows the previous study's historical 5 m product and operational TPI/slope rules.

Urban numerator and denominator:

- Restricted developed codes: 1,2,3,11,21,22,23,31,41,42,44,51,52.
- Broad: additionally 32 (Open Space and Recreation), 53 (Vacant Land/Construction in Progress), 54 (Others).
- Effective-land denominator excludes unmapped/sea, codes 62,91,92 (fish ponds/reservoirs/streams), and airport code 43. Fractions are not whole-circle shares or measured imperviousness.
- Permanent building footprint: Tower/Podium union intersected with effective land; excludes temporary/open-sided structures. Low <=0.05747741628451219, middle <=0.13652222507667297, high above; these prior empirical tercile cuts stay fixed after station removal.
- Height intensity: maximum known TopHeight−BaseHeight on 2 m centre-sampled cells, area integral divided by effective land. Low <=0.651177085066699 m, middle <=2.570014664476614 m, high above. Not mean building height, population density, FAR or measured true volume. Regression uses log1p intensity, category rules use original units.

Four administrative regions: HKI/KL/NT/Islands, with administrative Islands District separate from NT. The prior coordinate-to-district assignment puts TC in Wong Tai Sin (KL); a district label does not guarantee lowland or urban built form. All 18 administrative districts have station representations, many with only one site.

## Statistical methods

Prescribed lowland bins (<20,20–<50,50–<300 m) are readable exploratory rules, not error-optimized or physical transition boundaries. Additional four-bin coverage and rank-tertile cuts 15.333333/38.666667 m are retained. Rain uses the same elevation definitions, not newly selected cuts.

Three cohorts: all32, old30 excluding TC/TMS, lowland29 excluding all >=300 m. Rain is 20/18/18. Group mean loss is equal-station weighting, available dates; matched contrasts instead use each cross-group station pair's common dates and equal pair weights. Pair support changes by cohort/definition and is reported. No outcome-driven site selection, imputation or zero-filling.

Site-level matrices use one site per row. Pearson and Spearman both supplied. Partial Spearman ranks all variables, residualizes the factor and mean loss on the other five factor columns and an intercept, then correlates residuals. Leave-one-site min/max is an influence diagnostic, not a confidence interval. VIF comes from regressing each standardized predictor on the other five; an inverse correlation-matrix independent check is included. Neither low VIF nor adjustment identifies causation.

Joint regression: `loss_station,date = date_intercept + standardized geographic predictors + residual`. Six predictors: elevation, log1p coastal km, one urban proxy, slope, TPI z, relief. Four urban proxies are substituted one at a time; four-region dummies are an additional sensitivity for restricted land use in all/lowland cohorts. Date-centering both response and X removes daily intercepts. Each date has equal total weight; stations with observations on that date have equal weight. No station effects because they absorb static geography. Standardization uses equal-site mean/population SD within each target/cohort; 1 SD differs across cohorts, so raw coefficient magnitudes cannot be directly compared without the exported scale.

2,000 circular 14-calendar-day bootstrap draws, same day all stations together, seed 3536 (=3522+14). Regression coefficients are refitted through sufficient statistics for every bootstrap sample. This describes temporal uncertainty conditional on this site network, labels and missingness, not a representative new-site population. No multiplicity correction. In-sample within-date R² is not out-of-sample forecast skill. No new ML selection on 2025 outcomes is undertaken in this extension.

## Reproduction

Original project root: `C:/Users/Sena/Documents/ChatGPT/Project FYP - demo`.
Numerical environment is the existing repo Python 3.14.6 with NumPy, pandas, scipy, matplotlib and threadpoolctl. See prior model metadata for installed versions. Scripts live at `geographical-research/analyses/12_geographic_deepening/`; parent layout is required. Large D3 audit cases go to `analysis/geographic-deepening-20261114/`, outside Git and the evidence package.

```powershell
$env:PYTHONIOENCODING = 'utf-8'
$modelPython = './geographical-research/.venv/Scripts/python.exe'
$analysisDir = './geographical-research/analyses/12_geographic_deepening'
& $modelPython "$analysisDir/run_deepening.py"
& $modelPython "$analysisDir/verify_deepening.py"
& $modelPython "$analysisDir/build_report.py"
```

`build_report.py` needs the preceding delivered HTML for its CSS and inserts one link into that report. It saves the original first as `index_before_deepening.html`. Update `MAIN` for another destination. `qa_report.cjs` uses the installed Playwright/Chrome paths and checks both document layouts and relative links. Rebuilding numerical results requires the previous case pickles/prediction CSVs; rebuilding only the report uses supplied aggregates.

## Evidence files

- `station_definitions.csv`, `definitions.json`: full station values, operational group rules and cohorts.
- `group_means.csv`: all factors, urban definitions, four regions and 18 districts; each row specifies outcome period and baseline.
- `matched_contrasts.csv`: prespecified same-day D3 contrasts, 14-day intervals, station and date support.
- `station_outcomes.csv`: one row per station/target for correlation, with missing-date coverage.
- `factor_correlations.csv`: Pearson/Spearman between factors; `outcome_correlations.csv`: simple/partial correlations and leave-one sensitivity; `vif.csv`: collinearity diagnostics.
- `date_adjusted_regressions.csv`: every coefficient, standardized scale, interval, cases/dates/sites, R² and condition number. All 44 models, not only favourable findings.
- `region_factor_cross_counts.csv`: site counts and names within region-by-factor cells.
- `mountain_influence.csv`: mean loss/bias removing one mountain at a time and cumulative exclusions. `sample_summary.csv`: cohort/sample support.
- `old_coast_reconciliation.csv`: exact six-point old/new coast mean reconciliation.
- `sources/github_*.md` and `github_manifest.json`: source snapshots, public paths and Git blob SHAs. GitHub documents have been read directly this turn; not a claim that every GitHub branch was exhaustively reviewed.
- `verification.json`: independent row-loss/group/date-pair checks, all 44 coefficient fits using row-weighted least squares, all 2000-draw intervals using independent raw-moment daily statistics, inverse-correlation partial correlations/VIF, and old result reconciliation.

## Related sources found, not included as calculated results

Global LCZ primary paper: https://essd.copernicus.org/articles/14/3835/2022/ and linked DOI https://doi.org/10.5281/zenodo.6364594 . Nominal 2018 ~100 m product can provide a different urban form/cover classification after Hong Kong coverage and confidence checks.

2021 census small-subunit statistics and geometry: https://data.gov.hk/en-data/dataset/hk-censtatd-census_geo-2021-population-census-by-ssg . Contains 2342 small-subunit groups. A 500 m population feature requires explicit boundary allocation; district averages are not station-buffer populations.

Vegetation fraction, sky-view factor and wind exposure remain uncalculated candidates. Existing land-use/DTM/buildings may support them with additional documented construction; availability is not evidence of an already established relationship.
