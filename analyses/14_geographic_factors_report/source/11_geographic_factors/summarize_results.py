"""Common-case scores, paired time-block intervals, validation choice, and attribution."""
from pathlib import Path
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','4');os.environ.setdefault('OMP_NUM_THREADS','4')
import json
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from run_models import OUT,LOCAL,TARGETS,FACTORS,GROUPS,fit_predict,mean_score,save
from analyze_geography import block_weights

CAL=pd.date_range('2025-01-01','2025-12-31')
def cube(q,z):
 codes=sorted(q.station_code.unique());a=np.full((len(CAL),len(codes)*9),np.nan)
 di=CAL.get_indexer(q.valid_date);si=pd.Index(codes).get_indexer(q.station_code);li=q.lead.to_numpy()-1
 assert (di>=0).all() and (si>=0).all()
 a[di,si*9+li]=z;return a
def resampled(a,w):
 n=w@np.isfinite(a).astype(float);num=w@np.nan_to_num(a)
 v=np.divide(num,n,out=np.full_like(num,np.nan),where=n>0)
 return np.where(np.isfinite(v).all(axis=1),v.mean(axis=1),np.nan)
def metrics(q,z,target):
 e=z-q.y.to_numpy();a=cube(q,e)
 rec=dict(n_cases=len(q),n_dates=q.valid_date.nunique(),n_stations=q.station_code.nunique())
 if target=='rain_event':
  p=np.clip(z,1e-8,1-1e-8);y=q.y.to_numpy();ll=-(y*np.log(p)+(1-y)*np.log1p(-p))
  rec.update(brier=float(np.nanmean(a*a,axis=0).mean()),log_loss=float(np.nanmean(cube(q,ll),axis=0).mean()))
 else:rec.update(mae=float(np.nanmean(abs(a),axis=0).mean()),rmse=float(np.sqrt(np.nanmean(a*a,axis=0).mean())),bias=float(np.nanmean(a,axis=0).mean()))
 return rec

def main():
 ws={b:block_weights(len(CAL),b) for b in [7,14,28]}
 allmetrics=[];intervals=[];diffs=[];attribution=[];subgroups=[];thresholds=[];validation=[];choices=[];fallback=[]
 for target in TARGETS:
  cases=pd.read_pickle(LOCAL/(target+'_cases.pkl'));tr=cases[cases.valid_date<'2024-01-01'];va=cases[cases.valid_date.between('2024-01-01','2024-12-31')&cases.issue_date.ge('2024-01-01')]
  selections=pd.read_csv(OUT/(target+'_selection.csv'));grid=pd.read_csv(OUT/(target+'_validation_grid.csv'))
  methods=selections[selections.design.eq('temporal')].method.tolist()
  for m in methods:
   if m.startswith(('linear','hgb')):score=float(grid[(grid.design=='temporal')&(grid.method==m)].validation_loss.min())
   else:score=mean_score(va,fit_predict(tr,va,target,m),target)
   validation.append(dict(target=target,method=m,validation_loss=score,n_cases=len(va)))
  chosen=min([r for r in validation if r['target']==target],key=lambda r:r['validation_loss'])
  choices.append(dict(target=target,method=chosen['method'],basis='minimum 2024 validation loss; 2025 outcomes not used for choice',validation_loss=chosen['validation_loss']))
  for design in ['temporal','spatial']:
   q=pd.read_csv(LOCAL/(target+'_'+design+'_predictions.csv.gz'),parse_dates=['valid_date','issue_date'])
   assert q[methods].notna().all().all()
   draws={};point={}
   for m in methods+[x for x in q.columns if '_drop_' in x]:
    z=q[m].to_numpy();e=z-q.y.to_numpy();loss=e*e if target=='rain_event' else abs(e)
    a=cube(q,loss);point[m]=float(np.nanmean(a,axis=0).mean());draws[m]={b:resampled(a,w) for b,w in ws.items()}
    if '_drop_' not in m:
     allmetrics.append(dict(target=target,design=design,method=m,primary_loss=point[m],**metrics(q,z,target)))
     for b in ws:
      boot=draws[m][b];lo,hi=np.nanquantile(boot,[.025,.975]);intervals.append(dict(target=target,design=design,method=m,block_days=b,loss=point[m],ci_low=lo,ci_high=hi,n_finite=int(np.isfinite(boot).sum())))
     for f,col in GROUPS.items():
      for g,qq in q.groupby(col):
       vals=q.loc[qq.index,m].to_numpy();subgroups.append(dict(target=target,design=design,method=m,factor=f,group=g,**metrics(qq,vals,target)))
     if target=='rain_event':
      for t in [.2,.35,.5]:
       y=q.y.eq(1).to_numpy();alarm=z>=t;tp=int((alarm&y).sum());fp=int((alarm&~y).sum());fn=int((~alarm&y).sum());tn=int((~alarm&~y).sum())
       thresholds.append(dict(target=target,design=design,method=m,threshold=t,tp=tp,fp=fp,fn=fn,tn=tn,hit_rate=tp/(tp+fn) if tp+fn else np.nan,false_alarm_ratio=fp/(tp+fp) if tp+fp else np.nan,miss_rate=fn/(tp+fn) if tp+fn else np.nan,accuracy=(tp+tn)/len(q),denominator='pooled station/date/lead cases, dependent observations'))
   refs=['raw','station_mean','station_median'] if target in ['Tmax','Tmin'] else ['category_mean','station_mean','category_median'] if target=='rain_amount' else ['category_mean','station_mean']
   comparisons={(m,r) for m in methods for r in refs if m!=r}|{('linear_full','linear_base'),('hgb_full','hgb_base'),('hgb_full','linear_full')}
   for m,ref in sorted(comparisons):
    for b in ws:
     delta=draws[m][b]-draws[ref][b];lo,hi=np.nanquantile(delta,[.025,.975]);diffs.append(dict(target=target,design=design,method=m,reference=ref,block_days=b,loss_difference=point[m]-point[ref],ci_low=lo,ci_high=hi,n_finite=int(np.isfinite(delta).sum()),interpretation='negative favours method'))
   if design=='temporal':
    for m in ['linear_full','hgb_full']:
     for f in FACTORS:
      drop=m+'_drop_'+f
      for b in ws:
       delta=draws[drop][b]-draws[m][b];lo,hi=np.nanquantile(delta,[.025,.975]);attribution.append(dict(target=target,method=m,factor=f,block_days=b,loss_increase_without_factor=point[drop]-point[m],ci_low=lo,ci_high=hi,interpretation='positive is incremental predictive usefulness, not causal contribution'))
   for fold in ([-1] if design=='temporal' else sorted(q.spatial_fold.unique())):
    te=q if fold==-1 else q[q.spatial_fold.eq(fold)];held=set() if fold==-1 else set(te.station_code);train=cases[(cases.valid_date<'2025-01-01')&~cases.station_code.isin(held)]
    for m in methods:
     if m=='station_mean' or m=='station_median':keys=['station_code','lead'] if target in ['Tmax','Tmin'] else ['station_code','psr','lead']
     elif m.startswith('mean_'):keys=[GROUPS[m[5:]]]+(['lead'] if target in ['Tmax','Tmin'] else ['psr','lead'])
     else:continue
     known=set(train[keys].itertuples(index=False,name=None));n=sum(t not in known for t in te[keys].itertuples(index=False,name=None))
     fallback.append(dict(target=target,design=design,fold=int(fold),method=m,n_cases=len(te),n_fallback=n))
   print('summarized',target,design,flush=True)
  save(allmetrics,'method_metrics.csv');save(intervals,'method_intervals.csv');save(diffs,'paired_method_differences.csv');save(attribution,'factor_drop_comparisons.csv');save(subgroups,'method_by_geographic_group.csv');save(thresholds,'rain_event_threshold_metrics.csv');save(validation,'all_method_validation.csv');save(choices,'validation_recommendations.csv');save(fallback,'empirical_fallback_usage.csv')
 print('SUMMARY COMPLETE',flush=True)
if __name__=='__main__':
 with threadpool_limits(limits=4):main()
