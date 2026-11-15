"""Independent raw-row joins, metric regrouping and model refits; no training-function reuse."""
from pathlib import Path
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','4');os.environ.setdefault('OMP_NUM_THREADS','4')
import hashlib,json,itertools
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier,HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];OUT=HERE/'results';LOCAL=ROOT/'analysis/geographic-factors-20261114';DATA=ROOT/'analysis/initial-reliability/all-data'
checks=[]
def check(label,condition,detail=''):
 if not condition:raise AssertionError(label+': '+str(detail))
 checks.append({'check':label,'detail':detail})
def score(q,p,event):
 loss=(p-q.y.to_numpy())**2 if event else abs(p-q.y.to_numpy())
 return pd.DataFrame({'station':q.station_code.to_numpy(),'lead':q.lead.to_numpy(),'loss':loss}).groupby(['station','lead']).loss.mean().mean()
def simple_prediction(train,test,target,method):
 temp=target in ['Tmax','Tmin']
 if method=='raw':return test.forecast.to_numpy()
 if method=='zero':return np.zeros(len(test))
 z=train[['station_code','lead','psr','elevation_group','coast_group','urban_group','terrain_group']].copy()
 z['v']=train.y.to_numpy()-(train.forecast.to_numpy() if temp else 0)
 z['w']=1/z.groupby(['station_code','lead']).station_code.transform('size');z['wv']=z.v*z.w
 base=['lead'] if temp else ['psr','lead']
 def lookup(keys,median=False):
  grouped=z.groupby(keys)
  vals=grouped.v.median() if median else grouped.wv.sum()/grouped.w.sum()
  index=pd.MultiIndex.from_frame(test[keys]) if len(keys)>1 else pd.Index(test[keys[0]])
  return vals.reindex(index).to_numpy()
 baseline=lookup(base);baseline=np.where(np.isfinite(baseline),baseline,z.wv.sum()/z.w.sum())
 if method=='global_mean':out=np.full(len(test),z.wv.sum()/z.w.sum())
 elif method=='category_mean':out=baseline
 elif method=='station_mean':out=lookup(['station_code']+base);out=np.where(np.isfinite(out),out,baseline)
 elif method.startswith('mean_'):out=lookup([method[5:]+'_group']+base);out=np.where(np.isfinite(out),out,baseline)
 elif method in ['station_median','category_median']:
  out=lookup((['station_code'] if method=='station_median' else [])+base,True)
  fallback=baseline if temp else lookup(base,True)
  fallback=np.where(np.isfinite(fallback),fallback,z.v.median())
  out=np.where(np.isfinite(out),out,fallback)
 else:raise ValueError(method)
 return out+test.forecast.to_numpy() if temp else out
def model_prediction(tr,te,target,method,param,drop=None):
 geo={'elevation':['elevation_m'],'coast':['log_coast_km'],'urban':['restricted_fraction_500m'],'terrain':['slope_deg','tpi_z_500m','relief_500m']}
 temp=target in ['Tmax','Tmin'];event=target=='rain_event'
 columns=['forecast','lead'] if temp else ['psr_'+str(i) for i in range(5)]+['lead']
 if method.endswith('_full'):columns+=list(itertools.chain.from_iterable(v for k,v in geo.items() if k!=drop))
 counts=tr.groupby(['station_code','lead']).size().to_dict()
 weights=np.array([1/counts[(s,l)] for s,l in zip(tr.station_code,tr.lead)]);weights/=weights.mean()
 y=tr.y.to_numpy()-(tr.forecast.to_numpy() if temp else 0)
 if method.startswith('linear'):
  scale=StandardScaler().fit(tr[columns]);x=scale.transform(tr[columns]);z=scale.transform(te[columns])
  fit=LogisticRegression(C=float(param),max_iter=500,solver='lbfgs',random_state=3522) if event else Ridge(alpha=float(param))
  fit.fit(x,y,sample_weight=weights);pred=fit.predict_proba(z)[:,1] if event else fit.predict(z)
 else:
  kw=dict(max_iter=500 if method.startswith('hgb_long') else 80,learning_rate=.07,max_leaf_nodes=int(param),min_samples_leaf=150,l2_regularization=1.,early_stopping=False,random_state=3522)
  fit=HistGradientBoostingClassifier(**kw) if event else HistGradientBoostingRegressor(loss='squared_error' if method.startswith('hgb_squared') else 'absolute_error',**kw)
  fit.fit(tr[columns],y,sample_weight=weights);pred=fit.predict_proba(te[columns])[:,1] if event else fit.predict(te[columns])
 if temp:pred+=te.forecast.to_numpy()
 if target=='rain_amount':pred=np.maximum(pred,0)
 return pred

def main():
 obs=pd.read_csv(DATA/'observations.csv');obs=obs.set_index(['observation_series_id','observation_date'])
 f=pd.read_csv(DATA/'forecasts.csv');f['issue_date']=f.bulletin_time_hkt.str[:10]
 latest=f.groupby(['valid_date','issue_date']).bulletin_time_hkt.max()
 ff=f.set_index(['forecast_issue_id','valid_date'])
 check('forecast keys unique',ff.index.is_unique)
 metrics=pd.read_csv(OUT/'method_metrics.csv')
 totalrows=0;refits=0;method_checks=0
 for target in ['Tmax','Tmin','rain_event','rain_amount']:
  q=pd.read_pickle(LOCAL/(target+'_cases.pkl'));temp=target in ['Tmax','Tmin'];event=target=='rain_event';totalrows+=len(q)
  date=q.valid_date.dt.strftime('%Y-%m-%d');ix=pd.MultiIndex.from_arrays([q.observation_series_id,date]);truth=obs.loc[ix].reset_index(drop=True)
  check(target+' C observation rows',truth.data_completeness.eq('C').all())
  expected=truth.value_numeric.ge(10).to_numpy(dtype=float) if event else truth.value_numeric.to_numpy()
  check(target+' truth values match raw export',np.allclose(expected,q.y))
  if not event:check(target+' numeric observations exclude Trace',truth.value_text.ne('Trace').all())
  fix=pd.MultiIndex.from_arrays([q.forecast_issue_id,date]);forecast=ff.loc[fix].reset_index(drop=True)
  check(target+' bulletin timestamp preserved',(pd.to_datetime(forecast.bulletin_time_hkt).to_numpy()==q.bulletin_time_hkt.to_numpy()).all())
  bix=pd.MultiIndex.from_arrays([date,q.issue_date.dt.strftime('%Y-%m-%d')]);check(target+' daily latest',np.array_equal(latest.loc[bix].to_numpy(),q.bulletin_time_hkt.dt.strftime('%Y-%m-%d %H:%M:%S').to_numpy()))
  if temp:check(target+' public forecast values',np.allclose(forecast['forecast_tmax_c' if target=='Tmax' else 'forecast_tmin_c'],q.forecast))
  else:check(target+' PSR preserved',np.array_equal(forecast.psr.to_numpy(),q.psr.to_numpy()))
  check(target+' lead date arithmetic',((q.valid_date-q.issue_date).dt.days==q.lead).all() and q.lead.between(1,9).all())
  check(target+' no duplicate case keys',not q.duplicated(['station_code','valid_date','lead']).any())
  expected_sites=32 if temp else 20;check(target+' cohort count',q.station_code.nunique()==expected_sites)
  tr=q[q.valid_date<'2024-01-01'];va=q[q.valid_date.between('2024-01-01','2024-12-31')&q.issue_date.ge('2024-01-01')];fin=q[q.valid_date<'2025-01-01'];te=q[q.valid_date.ge('2025-01-01')&q.issue_date.ge('2025-01-01')]
  check(target+' temporal boundary embargo',tr.valid_date.max()<va.issue_date.min() and fin.valid_date.max()<te.issue_date.min())
  selection=pd.read_csv(OUT/(target+'_selection.csv'));grid=pd.read_csv(OUT/(target+'_validation_grid.csv'))
  methods=selection[selection.design.eq('temporal')].method.tolist()
  for design in ['temporal','spatial']:
   p=pd.read_csv(LOCAL/(target+'_'+design+'_predictions.csv.gz'))
   check(target+' '+design+' exact same cases',np.array_equal(p.case_id,te.case_id) and np.allclose(p.y,te.y))
   check(target+' '+design+' finite predictions',np.isfinite(p[methods]).all().all())
   if event:check(target+' '+design+' probability bounds',p[methods].ge(0).all().all() and p[methods].le(1).all().all())
   for m in methods:
    expected_score=score(te,p[m].to_numpy(),event);record=metrics[(metrics.target==target)&(metrics.design==design)&(metrics.method==m)].iloc[0]
    check(target+' '+design+' '+m+' metric',abs(expected_score-record.primary_loss)<1e-10);method_checks+=1
   for fold in ([-1] if design=='temporal' else sorted(te.spatial_fold.unique())):
    test=te if fold==-1 else te[te.spatial_fold.eq(fold)];held=set() if fold==-1 else set(test.station_code)
    train=fin[~fin.station_code.isin(held)];val=va[~va.station_code.isin(held)];tune_train=tr[~tr.station_code.isin(held)]
    check(target+' '+design+' '+str(fold)+' split exclusion',not held.intersection(train.station_code) and not held.intersection(val.station_code))
    for m in [m for m in methods if not m.startswith(('linear','hgb'))]:
     expected_simple=simple_prediction(train,test,target,m)
     saved_simple=p.set_index('case_id').loc[test.case_id,m].to_numpy()
     check(target+' '+design+' '+str(fold)+' '+m+' training-only baseline',np.allclose(expected_simple,saved_simple,rtol=1e-8,atol=1e-8))
    for m in [m for m in methods if m.startswith(('linear','hgb'))]:
     par=selection[(selection.design==design)&(selection.fold==fold)&(selection.method==m)].iloc[0].param
     gg=grid[(grid.design==design)&(grid.fold==fold)&(grid.method==m)]
     best=gg.sort_values(['validation_loss','param']).iloc[0]
     check(target+' '+design+' '+str(fold)+' '+m+' validation choice',par==best.param)
     if fold!=-1:check(target+' '+str(fold)+' excluded-site audit',all(set(str(s).split(';'))==held for s in gg.excluded_stations))
     check(target+' validation sample counts',gg.n_train.eq(len(tune_train)).all() and gg.n_validation.eq(len(val)).all())
     pred=model_prediction(train,test,target,m,par)
     saved=p.set_index('case_id').loc[test.case_id,m].to_numpy()
     check(target+' '+design+' '+str(fold)+' '+m+' independent refit',np.allclose(pred,saved,rtol=1e-8,atol=1e-8),float(np.max(abs(pred-saved))))
     refits+=1
    print('verified fits',target,design,fold,flush=True)
   if design=='temporal':
    for m in ['linear_full','hgb_full']:
     par=selection[(selection.design==design)&(selection.method==m)].iloc[0].param
     for drop in ['elevation','coast','urban','terrain']:
      pred=model_prediction(fin,te,target,m,par,drop)
      check(target+' '+m+' drop '+drop+' refit',np.allclose(pred,p[m+'_drop_'+drop],rtol=1e-8,atol=1e-8));refits+=1
  print('RAW+MODELS VERIFIED',target,flush=True)
 # A direct bootstrap arithmetic check against explicit sampled calendar rows.
 from analyze_geography import block_weights
 from summarize_results import cube,resampled,CAL
 p=pd.read_csv(LOCAL/'Tmax_temporal_predictions.csv.gz',parse_dates=['valid_date']);err=abs(p.hgb_full-p.y)-abs(p.station_mean-p.y)
 a=cube(p,err);w=block_weights(len(CAL),14);estimate=resampled(a,w)
 for i in [0,37,1999]:
  sampled=np.repeat(np.arange(len(CAL)),w[i].astype(int));direct=np.nanmean(a[sampled],axis=0).mean()
  check('calendar block direct replicate '+str(i),abs(direct-estimate[i])<1e-12)
 result={'passed':True,'source_case_rows_checked':totalrows,'independent_model_refits':refits,'metric_summaries_checked':method_checks,'checks':checks,'scope':'Independent raw export joins, metric groupby calculations, all selected temporal/spatial ML refits, core factor-drop refits and three block arithmetic checks. Does not certify raw archive completeness, operational availability, true terrain classes or new-station population uncertainty.'}
 (OUT/'independent_verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print({k:v for k,v in result.items() if k!='checks'},flush=True)
if __name__=='__main__':
 with threadpool_limits(limits=4):main()
