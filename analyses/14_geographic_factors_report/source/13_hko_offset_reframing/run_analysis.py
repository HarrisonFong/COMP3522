"""Frozen observed HKO-reference offsets; retrospective 2025 evaluation.

Reuse the pre-existing 30-station validation decision, independently reproduce
its scores from raw observations, and extend to the 32/29-station cohorts.
"""
from pathlib import Path
import os,sys,json,re,hashlib
os.environ.setdefault('OPENBLAS_NUM_THREADS','4')
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]
OUT=HERE/'results';OUT.mkdir(exist_ok=True)
DATA=ROOT/'analysis/initial-reliability/all-data'
AUDIT=ROOT/'analysis/hko-offset-20261114';AUDIT.mkdir(exist_ok=True)
OLD=ROOT/'tmp/COMP3522-review/analyses/09_geographic_temperature_v2/results'
sys.path.insert(0,str(HERE.parent/'12_geographic_deepening'))
import run_deepening as geo
S=geo.S.copy();S['elevation_band']=pd.cut(S.elevation_m,[-np.inf,200,700,np.inf],right=False,labels=['lt200','200to700','ge700'])
COHORTS={'all32':S.index.tolist(),'old30':S.index[~S.index.isin(['TC','TMS'])].tolist(),'low29':S.index[S.elevation_m.lt(200)].tolist()}
METHODS=['raw','annual_mean','monthly_mean','monthly_median']
CHOICE={'Tmax':'monthly_mean','Tmin':'monthly_median'}
def save(rows,name):pd.DataFrame(rows).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
def metrics(q,err):
 z=q[['station_code','lead']].copy();z['error']=err;z['ae']=abs(err);z['se']=err**2
 g=z.groupby(['station_code','lead'])[['error','ae','se']].mean()
 return dict(mae=g.ae.mean(),rmse=np.sqrt(g.se.mean()),bias=g.error.mean(),n_cases=len(q),n_stations=q.station_code.nunique(),n_dates=q.valid_date.nunique())
def main():
 stations=pd.read_csv(DATA/'stations.csv');norm=lambda x:re.sub('[^a-z0-9]','',str(x).lower())
 mapping={norm(r.station_name):r.station_code for r in stations.itertuples()}
 series=pd.read_csv(DATA/'series.csv');series=series[series.metric_name.str.contains('Maximum Temperature|Minimum Temperature')].copy()
 series['station_code']=series.station_name.map(lambda x:mapping[norm(x)])
 series['target']=np.where(series.metric_name.str.contains('Maximum'),'Tmax','Tmin')
 obs=pd.read_csv(DATA/'observations.csv',parse_dates=['observation_date']).merge(series[['observation_series_id','station_code','target']],on='observation_series_id',validate='many_to_one')
 obs['accepted']=obs.value_numeric.where(obs.data_completeness.eq('C'))
 val=[];offsets=[];scores=[];benefits=[];coasts=[];reg=[];sites=[];reference=[];repro=[];groups=[]
 cal=pd.date_range('2025-01-01','2025-12-31');w=geo.block_weights(365,14,2000)
 for target in CHOICE:
  truth=obs[obs.target.eq(target)].pivot(index='observation_date',columns='station_code',values='accepted')
  d=pd.read_pickle(ROOT/f'analysis/geographic-factors-20261114/{target}_cases.pkl')[['station_code','valid_date','issue_date','lead','y','forecast']].copy()
  assert not d.duplicated(['station_code','valid_date','lead']).any()
  for year in [2023,2024,2025]:
   t=truth.loc[(truth.index.year>=2022)&(truth.index.year<year)]
   gap=t[S.index].subtract(t.HKO,axis=0);annual=gap.mean();fits={}
   for month in range(1,13):
    g=gap[gap.index.month==month];n=g.count()
    fits[month]={'raw':annual*0,'annual_mean':annual,'monthly_mean':g.mean().where(n>=20,annual),'monthly_median':g.median().where(n>=20,annual)}
    for code in S.index:
     offsets.append(dict(target=target,train_end_year=year-1,station_code=code,month=month,n_month=int(n[code]),fallback=bool(n[code]<20),**{m:fits[month][m][code] for m in METHODS}))
   q=d[d.valid_date.dt.year.eq(year)&d.issue_date.dt.year.eq(year)].copy();q['month']=q.valid_date.dt.month;q['raw_error']=q.forecast-q.y
   for m in METHODS:
    delta=pd.Series({(mo,c):fits[mo][m][c] for mo in range(1,13) for c in S.index})
    q[m]=q.raw_error.to_numpy()+delta.reindex(pd.MultiIndex.from_arrays([q.month,q.station_code])).to_numpy()
   assert q[METHODS].notna().all().all()
   for cohort,codes in COHORTS.items():
    a=q[q.station_code.isin(codes)]
    for m in METHODS:
     result=dict(target=target,year=year,cohort=cohort,method=m,**metrics(a,a[m]))
     (val if year<2025 else scores).append(result)
   if year<2025:continue
   q['offset_error']=q[CHOICE[target]];q.to_csv(AUDIT/(target+'_2025_errors.csv.gz'),index=False)
   # Same-case, equal station x lead estimand, calendar-block intervals.
   for cohort,codes in COHORTS.items():
    a=q[q.station_code.isin(codes)]
    for lead in [0,3]:
     b=a if lead==0 else a[a.lead.eq(lead)]
     b=b.assign(improvement=b.raw_error.abs()-b.offset_error.abs())
     z=b.pivot(index='valid_date',columns=['station_code','lead'],values='improvement').reindex(cal)
     count=w@z.notna().to_numpy(float);tot=w@z.fillna(0).to_numpy();boot=(tot/count).mean(axis=1)
     lo,hi=np.quantile(boot,[.025,.975]);raw=metrics(b,b.raw_error);adj=metrics(b,b.offset_error)
     by=b.groupby('station_code').improvement.mean()
     benefits.append(dict(target=target,cohort=cohort,lead='D1-D9' if lead==0 else 'D3',method=CHOICE[target],raw_mae=raw['mae'],offset_mae=adj['mae'],improvement=z.mean().mean(),ci_low=lo,ci_high=hi,percent=100*(raw['mae']-adj['mae'])/raw['mae'],improved_stations=int((by>0).sum()),worsened_stations=int((by<0).sum()),n_cases=len(b),n_dates=b.valid_date.nunique()))
    for lead in range(1,10):
     b=a[a.lead.eq(lead)]
     for version,field in [('raw','raw_error'),('offset','offset_error')]:
      loss=b.assign(loss=b[field].abs());z=loss.pivot(index='valid_date',columns='station_code',values='loss').reindex(cal)
      st=S.loc[codes];near=st.index[st.coast_group.eq('near')];inland=st.index[st.coast_group.eq('inland')]
      diff,lo,hi,support,nboot=geo.paired_group(z,near,inland,w)
      coasts.append(dict(target=target,cohort=cohort,lead=lead,version=version,difference=diff,ci_low=lo,ci_high=hi,n_pairs=len(support),min_common_dates=min(x[2] for x in support),max_common_dates=max(x[2] for x in support),n_boot=nboot))
      if lead==3:
       for code,ss in loss.groupby('station_code'):
        sites.append(dict(target=target,cohort=cohort,version=version,station_code=code,mae=ss.loss.mean(),bias=ss[field].mean(),n_dates=len(ss)))
       if cohort in ['all32','low29']:
        for region in [False,True]:
         for row in geo.regression(loss,geo.BASE,cal,w,region):reg.append(dict(target=target,cohort=cohort,version=version,**row))
       for band,cs in st.groupby('elevation_band',observed=True):
        ss=loss[loss.station_code.isin(cs.index)]
        groups.append(dict(target=target,cohort=cohort,version=version,band=band,**metrics(ss,ss[field])))
   # HKO is a separate reference series, not one of the 32 AWS outcomes.
   b=q[q.lead.eq(3)].copy();b['hko_y']=truth.HKO.reindex(b.valid_date).to_numpy();b['hko_error']=b.forecast-b.hko_y
   for code,ss in b.dropna(subset=['hko_y']).groupby('station_code'):
    reference.append(dict(target=target,station_code=code,n_dates=len(ss),station_raw_mae=ss.raw_error.abs().mean(),hko_mae_same_dates=ss.hko_error.abs().mean(),station_offset_mae=ss.offset_error.abs().mean(),raw_gap=ss.raw_error.abs().mean()-ss.hko_error.abs().mean(),offset_gap=ss.offset_error.abs().mean()-ss.hko_error.abs().mean()))
   print(target,'done',flush=True)
 # Old experiment reproduction, independent implementation and observation joins.
 v=pd.DataFrame(val);sc=pd.DataFrame(scores);off=pd.DataFrame(offsets)
 oldval=pd.read_csv(OLD/'method_selection.csv');oldscore=pd.read_csv(OLD/'overview_2025.csv');oldoff=pd.read_csv(OLD/'training_offsets.csv')
 for target in CHOICE:
  for method in METHODS:
   actual=v[v.target.eq(target)&v.cohort.eq('old30')&v.method.eq(method)].mae.mean();expected=oldval[oldval.variable.eq(target)&oldval.method.eq(method)].validation_mae.iloc[0]
   repro.append(dict(check='validation',target=target,method=method,absolute_difference=abs(actual-expected)));assert abs(actual-expected)<1e-10
   actual=sc[sc.target.eq(target)&sc.cohort.eq('old30')&sc.method.eq(method)].mae.iloc[0];expected=oldscore[oldscore.variable.eq(target)&oldscore.stage.eq('forecast')&oldscore.method.eq(method)].mae.iloc[0]
   repro.append(dict(check='2025_mae',target=target,method=method,absolute_difference=abs(actual-expected)));assert abs(actual-expected)<1e-10
 of=off.rename(columns={'target':'variable'}).merge(oldoff,on=['variable','train_end_year','station_code','month'],suffixes=('_new','_old'),validate='one_to_one')
 for m in METHODS:assert (of[m+'_new']-of[m+'_old']).abs().max()<1e-10
 decisions=v.groupby(['target','cohort','method']).mae.mean().reset_index(name='validation_mae');decisions['chosen_in_cohort']=decisions.validation_mae.eq(decisions.groupby(['target','cohort']).validation_mae.transform('min'))
 decisions['used_frozen_method']=decisions.apply(lambda r:r.method==CHOICE[r.target],axis=1)
 for rows,name in [(val,'validation_by_year'),(decisions,'validation_selection'),(offsets,'training_offsets'),(scores,'test_scores'),(benefits,'benefits'),(coasts,'coast_contrasts'),(reg,'adjusted_geo_regressions'),(sites,'station_outcomes'),(reference,'hko_same_date_reference'),(groups,'elevation_groups_2025'),(repro,'reproduction')]:save(rows,name)
 S.to_csv(OUT/'station_definitions.csv',encoding='utf-8-sig')
 meta=dict(reference='HKO / Tsim Sha Tsui headquarters',methods=METHODS,choice=CHOICE,choice_origin='Existing old30 2023/2024 validation; frozen before 2025; cohort-specific alternatives reported, not used to optimize 2025',train_years=[2022,2023,2024],test_year=2025,retrospective=True,cohorts=COHORTS,bootstrap=dict(reps=2000,block_days=14,seed=3536,fixed_fits=True,station_resampling=False,multiplicity_adjusted=False),offset_formula='F_station=F_public + monthly statistic of (O_station - O_HKO) from training only',same_year_issue_and_valid=True,old30_reproduction_max_abs_difference=max(x['absolute_difference'] for x in repro),old_offset_rows_verified=len(of),source_sha256={str(DATA/(x+'.csv')):hashlib.sha256((DATA/(x+'.csv')).read_bytes()).hexdigest() for x in ['observations','series','stations']})
 (OUT/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
 print(pd.DataFrame(benefits).to_string(index=False),flush=True)
if __name__=='__main__':
 with threadpool_limits(limits=4):main()
