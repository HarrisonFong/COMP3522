"""Independent 2025 case reconstruction and same-day coast contrast check."""
from pathlib import Path
import json,re
import pandas as pd
import numpy as np
P=Path(__file__).resolve().parent;R=P/'results';ROOT=P.parents[2]
D=ROOT/'analysis/initial-reliability/all-data';A=ROOT/'analysis/hko-offset-20261114'
meta=json.loads((R/'metadata.json').read_text(encoding='utf-8'))
f=pd.read_csv(D/'forecasts.csv',parse_dates=['valid_date','bulletin_time_hkt']);f['issue_date']=f.bulletin_time_hkt.dt.normalize()
f=f.sort_values(['bulletin_time_hkt','forecast_issue_id']).drop_duplicates(['issue_date','valid_date'],keep='last')
f=f[f.issue_date.dt.year.eq(2025)&f.valid_date.dt.year.eq(2025)&f.lead_days.between(1,9)]
st=pd.read_csv(D/'stations.csv');se=pd.read_csv(D/'series.csv');o=pd.read_csv(D/'observations.csv',parse_dates=['observation_date'])
norm=lambda s:re.sub('[^a-z0-9]','',str(s).lower());mapping={norm(r.station_name):r.station_code for r in st.itertuples()}
se['station_code']=se.station_name.map(lambda s:mapping.get(norm(s)))
o=o.merge(se[['observation_series_id','station_code','metric_name']],on='observation_series_id');o=o[o.data_completeness.eq('C')]
geo=pd.read_csv(R/'station_definitions.csv').set_index('station_code');offset=pd.read_csv(R/'training_offsets.csv');scores=pd.read_csv(R/'test_scores.csv');coast=pd.read_csv(R/'coast_contrasts.csv')
checks=[]
for target,word,forecast in [('Tmax','Maximum','forecast_tmax_c'),('Tmin','Minimum','forecast_tmin_c')]:
 obs=o[o.metric_name.str.contains(word+' Temperature')];test=obs[obs.observation_date.dt.year.eq(2025)&obs.station_code.isin(geo.index)]
 independent=f[['valid_date','lead_days',forecast]].merge(test[['observation_date','station_code','value_numeric']],left_on='valid_date',right_on='observation_date').rename(columns={'lead_days':'lead'}).dropna(subset=[forecast,'value_numeric'])
 audit=pd.read_csv(A/(target+'_2025_errors.csv.gz'),parse_dates=['valid_date'])
 keys=['station_code','valid_date','lead'];m=independent.merge(audit,on=keys,validate='one_to_one',indicator=True)
 assert len(m)==len(independent)==len(audit) and (m[forecast]-m.value_numeric-m.raw_error).abs().max()<1e-12
 # Independently reconstruct all selected frozen offsets from source observations.
 train=obs[obs.observation_date.dt.year.between(2022,2024)].pivot(index='observation_date',columns='station_code',values='value_numeric')
 delta=train[geo.index].sub(train.HKO,axis=0);method=meta['choice'][target]
 for month in range(1,13):
  q=delta[delta.index.month==month];expected=q.mean() if method=='monthly_mean' else q.median();expected=expected.where(q.count()>=20,delta.mean())
  actual=offset[offset.target.eq(target)&offset.train_end_year.eq(2024)&offset.month.eq(month)].set_index('station_code')[method]
  assert np.allclose(actual.reindex(geo.index),expected,atol=1e-12)
 for cohort,codes in meta['cohorts'].items():
  q=audit[audit.station_code.isin(codes)]
  for method in meta['methods']:
   expected=q.groupby(keys[::2])[method].apply(lambda x:abs(x).mean()).mean()
   actual=scores[scores.target.eq(target)&scores.cohort.eq(cohort)&scores.method.eq(method)].mae.item();assert abs(expected-actual)<1e-12
 # Independently materialize the 40 lowland pairs; resample date blocks.
 rng=np.random.default_rng(3536);starts=rng.integers(365,size=(2000,27));draws=((starts[:,:,None]+np.arange(14))%365).reshape(2000,-1)[:,:365]
 weights=np.stack([np.bincount(ix,minlength=365) for ix in draws]);calendar=pd.date_range('2025-01-01','2025-12-31')
 low=geo.loc[meta['cohorts']['low29']];near=low.index[low.coast_group.eq('near')];inland=low.index[low.coast_group.eq('inland')]
 for version,col in [('raw','raw_error'),('offset','offset_error')]:
  q=audit[audit.lead.eq(3)];z=q.pivot(index='valid_date',columns='station_code',values=col).abs().reindex(calendar)
  pairs=np.column_stack([(z[b]-z[a]).to_numpy() for a in near for b in inland]);point=np.nanmean(pairs,axis=0).mean();boot=((weights@np.nan_to_num(pairs))/(weights@np.isfinite(pairs))).mean(axis=1)
  expected=[point,*np.quantile(boot,[.025,.975])];actual=coast[coast.target.eq(target)&coast.cohort.eq('low29')&coast.lead.eq(3)&coast.version.eq(version)][['difference','ci_low','ci_high']].iloc[0]
  assert np.allclose(expected,actual,atol=1e-12)
 checks.append(dict(target=target,raw_cases=len(independent),raw_forecast_join='passed',frozen_offsets='passed',all_method_cohort_maes='passed',lowland_D3_paired_coast_and_2000_bootstrap='passed'))
reg=pd.read_csv(R/'adjusted_geo_regressions.csv');n_models=0
for (target,cohort,version,region),rows in reg.groupby(['target','cohort','version','region_adjustment']):
 sites=geo.loc[sorted(meta['cohorts'][cohort])];features=['elevation_m','log_coast_km','restricted_fraction_500m','slope_deg','tpi_z_500m','relief_500m']
 x=(sites[features]-sites[features].mean())/sites[features].std(ddof=0)
 if region:x=pd.concat([x,pd.get_dummies(sites.region4_group,dtype=float).drop(columns='HKI')],axis=1)
 audit=pd.read_csv(A/(target+'_2025_errors.csv.gz'),parse_dates=['valid_date']);q=audit[audit.lead.eq(3)&audit.station_code.isin(sites.index)].copy()
 q=q[['station_code','valid_date',version+'_error']].rename(columns={version+'_error':'response'});q.response=q.response.abs();q=q.join(x,on='station_code')
 names=x.columns.tolist();centered=q[names+['response']]-q.groupby('valid_date')[names+['response']].transform('mean');weight=1/np.sqrt(q.groupby('valid_date').response.transform('size').to_numpy())
 beta=np.linalg.lstsq(centered[names].to_numpy()*weight[:,None],centered.response.to_numpy()*weight,rcond=None)[0]
 assert np.allclose(beta,rows.set_index('feature').loc[names].coefficient.to_numpy(),atol=1e-10);n_models+=1
out=dict(passed=True,checks=checks,independent_weighted_date_demeaned_regression_models=n_models,old30_reproduction_max_difference=meta['old30_reproduction_max_abs_difference'],old_offset_rows_verified=meta['old_offset_rows_verified'])
(R/'verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
