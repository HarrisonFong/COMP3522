"""Fixed-parameter sensitivity to geographic scale and mountain-site inclusion."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','4');os.environ.setdefault('OMP_NUM_THREADS','4')
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from run_models import LOCAL,OUT,TARGETS,fit_predict,mean_score,save
from summarize_results import cube,resampled,CAL
from analyze_geography import block_weights,paired_group

def main():
 rows=[];w=block_weights(len(CAL),14);geography=pd.read_csv(OUT/'station_factors.csv').set_index('station_code')
 for target in TARGETS:
  original=pd.read_pickle(LOCAL/(target+'_cases.pkl'));selection=pd.read_csv(OUT/(target+'_selection.csv'))
  primary=pd.read_csv(LOCAL/(target+'_temporal_predictions.csv.gz')).set_index('case_id')
  for variant in ['terrain250','terrain1000','urban250','urban1000','lowland']:
   q=original.copy()
   if variant.startswith('terrain'):
    radius=variant[7:]
    q['tpi_z_500m']=q['tpi_z_'+radius+'m'];q['relief_500m']=q['relief_'+radius+'m'];q['terrain_group']=q['terrain_group_'+radius+'m']
   elif variant.startswith('urban'):
    radius=variant[5:];q['restricted_fraction_500m']=q['restricted_fraction_'+radius+'m']
    q['urban_group']=np.where(q.restricted_fraction_500m>=.5,'high',np.where(q.restricted_fraction_500m>=.2,'mixed','low'))
   else:q=q[q.elevation_m<300]
   tr=q[q.valid_date<'2025-01-01'];te=q[q.valid_date.ge('2025-01-01')&q.issue_date.ge('2025-01-01')]
   out=te[['case_id','station_code','valid_date','lead','y']].copy()
   methods=['linear_full','hgb_full']
   if variant.startswith('terrain'):methods+=['mean_terrain']
   elif variant.startswith('urban'):methods+=['mean_urban']
   else:methods+=['station_mean']+(['station_median'] if target in ['Tmax','Tmin'] else ['category_mean','category_median'] if target=='rain_amount' else ['category_mean'])
   for method in methods:
    param=selection[(selection.design=='temporal')&(selection.method==method)].iloc[0].param
    pred=fit_predict(tr,te,target,method,None if pd.isna(param) else param)
    out[method]=pred
    base=primary.loc[te.case_id,method].to_numpy()
    fn=lambda p:(p-te.y.to_numpy())**2 if target=='rain_event' else abs(p-te.y.to_numpy())
    delta=resampled(cube(te,fn(pred)),w)-resampled(cube(te,fn(base)),w)
    lo,hi=np.nanquantile(delta,[.025,.975])
    rows.append(dict(target=target,variant=variant,method=method,n_stations=te.station_code.nunique(),n_cases=len(te),loss=mean_score(te,pred,target),primary_on_same_cases=mean_score(te,base,target),difference=mean_score(te,pred,target)-mean_score(te,base,target),ci_low=lo,ci_high=hi,interpretation='variant refit minus original fit on identical eligible test cases; fixed original hyperparameters'))
   out.to_csv(LOCAL/(target+'_sensitivity_'+variant+'.csv.gz'),index=False,compression='gzip')
   save(rows,'geographic_model_sensitivity.csv');print('sensitivity',target,variant,'done',flush=True)
 # Leave-one-site-out influence on raw geographic D3 inland-minus-near contrast.
 loo=[]
 for target in ['Tmax','Tmin']:
  q=pd.read_pickle(LOCAL/(target+'_cases.pkl'));q=q[q.lead.eq(3)].copy();q['ae']=abs(q.forecast-q.y)
  a=q.pivot(index='valid_date',columns='station_code',values='ae')
  near=geography.index[geography.coast_group.eq('near')].tolist();inland=geography.index[geography.coast_group.eq('inland')].tolist()
  for omitted in ['none']+near+inland:
   aa=[s for s in near if s!=omitted];bb=[s for s in inland if s!=omitted]
   dif=[];ns=[]
   for sa in aa:
    for sb in bb:
     z=a[[sa,sb]].dropna();dif.append(float((z[sb]-z[sa]).mean()));ns.append(len(z))
   loo.append(dict(target=target,omitted_station=omitted,matched_mae_difference=float(np.mean(dif)),n_station_pairs=len(dif),min_common_dates=min(ns),max_common_dates=max(ns)))
 save(loo,'coast_leave_one_station_out.csv')
 print('SENSITIVITY COMPLETE',flush=True)
if __name__=='__main__':
 with threadpool_limits(limits=4):main()
