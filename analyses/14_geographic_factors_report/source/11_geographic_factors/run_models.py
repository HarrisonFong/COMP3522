"""Four-factor temporal/spatial model comparison. Raw data are read only."""
from pathlib import Path
import os
os.environ.setdefault('OMP_NUM_THREADS','4');os.environ.setdefault('OPENBLAS_NUM_THREADS','4')
import argparse,json,time,hashlib,platform
import numpy as np
import pandas as pd
import sklearn
from sklearn.cluster import KMeans
from sklearn.linear_model import Ridge,LogisticRegression
from sklearn.ensemble import HistGradientBoostingRegressor,HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
OUT=HERE/'results';LOCAL=ROOT/'analysis/geographic-factors-20261114';DATA=ROOT/'analysis/initial-reliability/all-data'
FACTORS={'elevation':['elevation_m'],'coast':['log_coast_km'],'urban':['restricted_fraction_500m'],'terrain':['slope_deg','tpi_z_500m','relief_500m']}
GROUPS={f:f+'_group' for f in FACTORS}
PSR=['Low','Medium Low','Medium','Medium High','High']
PSRCOLS=['psr_'+str(i) for i in range(5)]
TARGETS=['Tmax','Tmin','rain_event','rain_amount']

def save(df,name):pd.DataFrame(df).to_csv(OUT/name,index=False,encoding='utf-8-sig')
def sample_weight(d):
 w=1/d.groupby(['station_code','lead']).station_code.transform('size').to_numpy();return w*len(w)/w.sum()
def mean_score(q,p,target):
 err=np.asarray(p)-q.y.to_numpy();loss=err**2 if target=='rain_event' else abs(err)
 return float(pd.DataFrame({'s':q.station_code,'l':q.lead,'z':loss}).groupby(['s','l']).z.mean().mean())
def features(target,geo):return (['forecast','lead'] if target in ['Tmax','Tmin'] else PSRCOLS+['lead'])+geo
def training_target(q,target):return q.y.to_numpy()-q.forecast.to_numpy() if target in ['Tmax','Tmin'] else q.y.to_numpy()
def empirical(train,test,target,method):
 temp=target in ['Tmax','Tmin'];value=training_target(train,target)
 z=train.copy();z['value']=value;z['w']=sample_weight(train);z['wx']=z.value*z.w
 def means(keys):
  g=z.groupby(keys);return g.wx.sum()/g.w.sum()
 globalmean=float(np.average(value,weights=z.w))
 basekeys=['lead'] if temp else ['psr','lead']
 base=means(basekeys)
 def values(tab,keys,fallback):
  return np.array([tab.get(tuple(row) if len(keys)>1 else row[0],fallback[i]) for i,row in enumerate(test[keys].itertuples(index=False,name=None))],float)
 default=np.full(len(test),globalmean);fallback=values(base,basekeys,default)
 if method=='raw':return test.forecast.to_numpy()
 if method=='zero':return np.zeros(len(test))
 if method=='global_mean':out=default
 elif method=='category_mean':out=fallback
 elif method=='station_mean':
  keys=['station_code','lead'] if temp else ['station_code','psr','lead'];out=values(means(keys),keys,fallback)
 elif method in ['station_median','category_median']:
  keys=basekeys if method=='category_median' else ['station_code']+basekeys
  medianbase=z.groupby(basekeys).value.median()
  medianfallback=fallback if temp else values(medianbase,basekeys,np.full(len(test),float(z.value.median())))
  out=values(z.groupby(keys).value.median(),keys,medianfallback)
 elif method.startswith('mean_'):
  factor=method[5:];keys=[GROUPS[factor]]+basekeys;out=values(means(keys),keys,fallback)
 else:raise ValueError(method)
 return out+test.forecast.to_numpy() if temp else out

def fit_predict(train,test,target,method,param=None,drop=None):
 if not method.startswith(('linear','hgb')):return empirical(train,test,target,method)
 full=method.endswith('_full');geo=sum([v for k,v in FACTORS.items() if k!=drop],[]) if full else []
 cols=features(target,geo);w=sample_weight(train);y=training_target(train,target)
 if method.startswith('linear'):
  if target=='rain_event':
   model=make_pipeline(StandardScaler(),LogisticRegression(C=float(param),max_iter=500,solver='lbfgs',random_state=3522))
   model.fit(train[cols],y,logisticregression__sample_weight=w)
   out=model.predict_proba(test[cols])[:,1]
  else:
   model=make_pipeline(StandardScaler(),Ridge(alpha=float(param)))
   model.fit(train[cols],y,ridge__sample_weight=w);out=model.predict(test[cols])
 else:
  kw=dict(max_iter=500 if method.startswith('hgb_long') else 80,learning_rate=.07,max_leaf_nodes=int(param),min_samples_leaf=150,l2_regularization=1.,early_stopping=False,random_state=3522)
  model=HistGradientBoostingClassifier(**kw) if target=='rain_event' else HistGradientBoostingRegressor(loss='squared_error' if method.startswith('hgb_squared') else 'absolute_error',**kw)
  model.fit(train[cols],y,sample_weight=w)
  out=model.predict_proba(test[cols])[:,1] if target=='rain_event' else model.predict(test[cols])
 if target in ['Tmax','Tmin']:out=out+test.forecast.to_numpy()
 if target=='rain_amount':out=np.maximum(out,0)
 assert np.isfinite(out).all()
 if target=='rain_event':assert ((out>=0)&(out<=1)).all()
 return out

def reconstruct():
 geo=pd.read_csv(OUT/'station_factors.csv')
 xy=np.column_stack([geo.longitude*np.cos(np.radians(22.3)),geo.latitude]);geo['spatial_fold']=KMeans(n_clusters=5,random_state=3522,n_init=20).fit_predict(xy)
 save(geo,'station_design.csv')
 stations=pd.read_csv(DATA/'stations.csv');series=pd.read_csv(DATA/'series.csv')
 norm=lambda s:''.join(c for c in str(s).lower() if c.isalnum())
 codes={norm(r.station_name):r.station_code for r in stations.itertuples()}
 s=series[series.metric_name.str.contains('Maximum Temperature|Minimum Temperature|Total Rainfall')].copy()
 s['station_code']=s.station_name.map(lambda s:codes[norm(s)]);s['target']=np.select([s.metric_name.str.contains('Maximum Temperature'),s.metric_name.str.contains('Minimum Temperature')],['Tmax','Tmin'],default='rain')
 assert not s.duplicated(['station_code','target']).any()
 obs=pd.read_csv(DATA/'observations.csv',parse_dates=['observation_date']).merge(s[['observation_series_id','station_code','target']],on='observation_series_id',validate='many_to_one')
 obs=obs[obs.data_completeness.eq('C')&obs.observation_date.between('2022-01-01','2025-12-31')]
 assert not obs.duplicated(['station_code','target','observation_date']).any()
 f=pd.read_csv(DATA/'forecasts.csv',parse_dates=['bulletin_time_hkt','valid_date'])
 f['issue_date']=f.bulletin_time_hkt.dt.normalize()
 assert f.lead_days.eq((f.valid_date-f.issue_date).dt.days).all()
 assert not f.groupby(['valid_date','bulletin_time_hkt'])[['forecast_tmax_c','forecast_tmin_c','psr']].nunique(dropna=False).gt(1).any().any()
 f=f.sort_values(['bulletin_time_hkt','forecast_issue_id']).drop_duplicates(['valid_date','issue_date'],keep='last')
 f=f[f.lead_days.between(1,9)&f.valid_date.between('2022-01-01','2025-12-31')].rename(columns={'lead_days':'lead'})
 assert not f.duplicated(['valid_date','lead']).any()
 all_data={};coverage=[]
 for target in TARGETS:
  temp=target in ['Tmax','Tmin'];gg=geo[geo.temperature_candidate if temp else geo.rain_candidate]
  truth=obs[(obs.target==(target if temp else 'rain'))&obs.station_code.isin(gg.station_code)].copy()
  if target=='rain_event':
   truth=truth[truth.value_numeric.notna()|truth.value_text.eq('Trace')];truth['y']=truth.value_numeric.ge(10).astype(float)
  else:truth=truth[truth.value_numeric.notna()].copy();truth['y']=truth.value_numeric
  q=f.merge(truth[['station_code','observation_date','observation_series_id','y']],left_on='valid_date',right_on='observation_date')
  if temp:q['forecast']=q['forecast_tmax_c' if target=='Tmax' else 'forecast_tmin_c'];q=q[q.forecast.notna()]
  else:q=q[q.psr.isin(PSR)].copy();q['forecast']=np.nan
  for i,c in enumerate(PSR):q[PSRCOLS[i]]=q.psr.eq(c).astype(float)
  q=q.merge(gg,on='station_code',validate='many_to_one').sort_values(['valid_date','station_code','lead']).reset_index(drop=True)
  assert not q.duplicated(['valid_date','station_code','lead']).any()
  assert np.isfinite(q[features(target,sum(FACTORS.values(),[]))+['y']]).all().all()
  q['case_id']=np.arange(len(q))
  all_data[target]=q
  for (st,yr,month),r in q.groupby(['station_code',q.valid_date.dt.year,q.valid_date.dt.month]):coverage.append(dict(target=target,station_code=st,year=yr,month=month,n_cases=len(r),n_dates=r.valid_date.nunique()))
  q.to_pickle(LOCAL/(target+'_cases.pkl'))
  print('DATA',target,len(gg),len(q),flush=True)
 save(coverage,'coverage.csv');return all_data

def evaluate(target,q):
 start=time.time();temp=target in ['Tmax','Tmin']
 methods=(['raw','global_mean','station_mean','station_median'] if temp else ['zero','global_mean','category_mean','category_median','station_mean','station_median'] if target=='rain_amount' else ['global_mean','category_mean','station_mean'])+['mean_'+f for f in FACTORS]+['linear_base','linear_full','hgb_base','hgb_full']
 if target=='rain_amount':methods+=['hgb_long_full','hgb_squared_full']
 train=q[q.valid_date<'2024-01-01'];valid=q[q.valid_date.between('2024-01-01','2024-12-31')&q.issue_date.ge('2024-01-01')]
 final=q[q.valid_date<'2025-01-01'];test=q[q.valid_date.ge('2025-01-01')&q.issue_date.ge('2025-01-01')]
 assert train.valid_date.max()<valid.issue_date.min() and final.valid_date.max()<test.issue_date.min()
 columns=['case_id','station_code','valid_date','issue_date','bulletin_time_hkt','forecast_issue_id','observation_series_id','lead','y','forecast','psr','spatial_fold']+list(GROUPS.values())
 pred=test[columns].copy();grid=[];selected=[];scores=[]
 def tune(tr,va,method,design,fold):
  params=([.1,1.,10.] if target=='rain_event' else [1.,100.,10000.]) if method.startswith('linear') else [7,15]
  vals=[]
  for p in params:
   z=fit_predict(tr,va,target,method,p);score=mean_score(va,z,target)
   row=dict(target=target,design=design,fold=fold,method=method,param=p,validation_loss=score,n_train=len(tr),n_validation=len(va),train_max_date=str(tr.valid_date.max().date()),validation_min_issue=str(va.issue_date.min().date()),excluded_stations=';'.join(sorted(set(test.station_code)-set(tr.station_code))))
   grid.append(row);vals.append((score,p));save(grid,target+'_validation_grid.csv')
  return min(vals)[1]
 for method in methods:
  p=tune(train,valid,method,'temporal',-1) if method.startswith(('linear','hgb')) else None
  selected.append(dict(target=target,design='temporal',fold=-1,method=method,param=p))
  pred[method]=fit_predict(final,test,target,method,p)
  scores.append(dict(target=target,design='temporal',method=method,primary_loss=mean_score(test,pred[method],target),n_cases=len(test)))
  print(target,'temporal',method,scores[-1]['primary_loss'],flush=True)
  pred.to_pickle(LOCAL/(target+'_temporal_partial.pkl'))
 # Drop-one-factor retraining with chosen full-model parameters fixed.
 for method in ['linear_full','hgb_full']:
  p=next(r['param'] for r in selected if r['method']==method)
  for factor in FACTORS:
   pred[method+'_drop_'+factor]=fit_predict(final,test,target,method,p,drop=factor)
   print(target,'drop',method,factor,flush=True)
 pred.to_csv(LOCAL/(target+'_temporal_predictions.csv.gz'),index=False,compression='gzip')
 spatial=test[columns].copy()
 for method in methods:spatial[method]=np.nan
 for fold in sorted(test.spatial_fold.unique()):
  held=set(test.loc[test.spatial_fold.eq(fold),'station_code']);tr=train[~train.station_code.isin(held)];va=valid[~valid.station_code.isin(held)];fin=final[~final.station_code.isin(held)];te=test[test.station_code.isin(held)]
  assert not held.intersection(tr.station_code) and not held.intersection(va.station_code) and not held.intersection(fin.station_code)
  for method in methods:
   p=tune(tr,va,method,'spatial',int(fold)) if method.startswith(('linear','hgb')) else None
   selected.append(dict(target=target,design='spatial',fold=int(fold),method=method,param=p))
   spatial.loc[te.index,method]=fit_predict(fin,te,target,method,p)
  print(target,'spatial fold',fold,'sites',sorted(held),'done',flush=True)
  spatial.to_pickle(LOCAL/(target+'_spatial_partial.pkl'))
 assert spatial[methods].notna().all().all()
 for m in methods:scores.append(dict(target=target,design='spatial',method=m,primary_loss=mean_score(test,spatial[m],target),n_cases=len(test)))
 spatial.to_csv(LOCAL/(target+'_spatial_predictions.csv.gz'),index=False,compression='gzip')
 save(scores,target+'_primary_scores.csv');save(selected,target+'_selection.csv')
 print('COMPLETE',target,round(time.time()-start,1),'seconds',flush=True)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--targets',nargs='+',default=TARGETS);parser.add_argument('--reuse-cases',action='store_true');args=parser.parse_args()
 OUT.mkdir(exist_ok=True);LOCAL.mkdir(exist_ok=True)
 with threadpool_limits(limits=4):
  data={t:pd.read_pickle(LOCAL/(t+'_cases.pkl')) for t in args.targets} if args.reuse_cases else reconstruct()
  for t in args.targets:evaluate(t,data[t])
 metadata={'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,'sklearn':sklearn.__version__,'targets':[t for t in TARGETS if (LOCAL/(t+'_spatial_predictions.csv.gz')).exists()],'last_run_targets':args.targets,'created':pd.Timestamp.now().isoformat(),'primary_context':'forecast level/category and lead only, no season or issue-time observed future weather','geographic_groups':FACTORS,'source_sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [DATA/'forecasts.csv',DATA/'observations.csv',DATA/'series.csv',OUT/'station_factors.csv']}}
 (OUT/'model_metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
if __name__=='__main__':main()
