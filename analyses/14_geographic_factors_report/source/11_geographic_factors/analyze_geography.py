"""Mean summaries and same-date/lead spatial contrasts; no fitted prediction model."""
from pathlib import Path
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','4');os.environ.setdefault('OMP_NUM_THREADS','4')
import itertools,json
import pandas as pd
import numpy as np
from threadpoolctl import threadpool_limits
from run_models import LOCAL,OUT,FACTORS,GROUPS,save

def block_weights(n,block=14,reps=2000):
 rng=np.random.default_rng(3522+block);starts=rng.integers(n,size=(reps,int(np.ceil(n/block))))
 ix=((starts[:,:,None]+np.arange(block))%n).reshape(reps,-1)[:,:n]
 w=np.zeros((reps,n))
 for i,row in enumerate(ix):w[i]=np.bincount(row,minlength=n)
 return w
def paired_group(a,groupa,groupb,w):
 # Each cross-group station pair uses its own intersection; pairs equal-weighted.
 diffs=[];supports=[]
 for sa,sb in itertools.product(groupa,groupb):
  va=a[sa].to_numpy();vb=a[sb].to_numpy();ok=np.isfinite(va)&np.isfinite(vb)
  if not ok.any():continue
  diffs.append(np.where(ok,vb-va,np.nan));supports.append((sa,sb,int(ok.sum())))
 if not diffs:return None
 z=np.stack(diffs,axis=1);n=np.isfinite(z).sum(axis=0)
 point=float(np.mean(np.nansum(z,axis=0)/n))
 den=w@np.isfinite(z).astype(float);num=w@np.nan_to_num(z)
 vals=np.divide(num,den,out=np.full_like(num,np.nan),where=den>0)
 valid=np.isfinite(vals).all(axis=1);boot=vals[valid].mean(axis=1)
 return point,*np.quantile(boot,[.025,.975]),supports,int(valid.sum())

def main():
 geo=pd.read_csv(OUT/'station_factors.csv').set_index('station_code');cal=pd.date_range('2022-01-01','2025-12-31');w=block_weights(len(cal))
 scores=[];paired=[];support=[];strict=[];sensitivity=[];groupcounts=[]
 for target in ['Tmax','Tmin','rain_event','rain_amount']:
  d=pd.read_pickle(LOCAL/(target+'_cases.pkl'));codes=sorted(d.station_code.unique())
  d['ae']=abs(d.forecast-d.y) if target in ['Tmax','Tmin'] else np.nan
  d['error']=d.forecast-d.y
  d['alarm']=d.psr.isin(['Medium High','High'])
  for f,col in GROUPS.items():
   groups={g:sorted(q.station_code.unique()) for g,q in d.groupby(col)}
   for g,cs in groups.items():groupcounts.append(dict(target=target,factor=f,group=g,n_stations=len(cs),stations=';'.join(cs)))
   for (lead,g),q in d.groupby(['lead',col]):
    row=dict(target=target,factor=f,group=g,lead=int(lead),n_stations=q.station_code.nunique(),n_cases=len(q),n_dates_union=q.valid_date.nunique())
    if target in ['Tmax','Tmin']:
     by=q.groupby('station_code');row.update(mae=float(by.ae.mean().mean()),rmse=float(np.sqrt(q.assign(se=q.error**2).groupby('station_code').se.mean().mean())),bias=float(by.error.mean().mean()))
    elif target=='rain_event':
     ev=q.y.eq(1);al=q.alarm;tp=int((al&ev).sum());fp=int((al&~ev).sum());fn=int((~al&ev).sum());tn=int((~al&~ev).sum())
     row.update(tp=tp,fp=fp,fn=fn,tn=tn,hit_rate=tp/(tp+fn) if tp+fn else np.nan,false_alarm_ratio=fp/(tp+fp) if tp+fp else np.nan,event_rate=float(q.groupby('station_code').y.mean().mean()))
    else:row.update(mean_rain_mm=float(q.groupby('station_code').y.mean().mean()))
    scores.append(row)
   # Primary D3 factor contrasts. Temperature uses raw absolute error;
   # rain event uses event indicator (frequency difference, NOT prediction skill).
   lead=3;dd=d[d.lead.eq(lead)];field='ae' if target in ['Tmax','Tmin'] else 'y'
   a=dd.pivot(index='valid_date',columns='station_code',values=field).reindex(cal)
   allcommon=a.dropna()
   for g,cs in groups.items():
    strict.append(dict(target=target,factor=f,group=g,lead=3,n_dates=len(allcommon),mean_value=float(allcommon[cs].to_numpy().mean()),quantity='MAE_C' if target in ['Tmax','Tmin'] else 'event_frequency' if target=='rain_event' else 'rain_mm'))
   for ga,gb in itertools.combinations(groups,2):
    res=paired_group(a,groups[ga],groups[gb],w)
    if res is None:continue
    point,lo,hi,sp,nboot=res
    paired.append(dict(target=target,factor=f,contrast=gb+' minus '+ga,lead=3,quantity='MAE_C' if target in ['Tmax','Tmin'] else 'event_frequency' if target=='rain_event' else 'rain_mm',difference=point,ci_low=lo,ci_high=hi,n_station_pairs=len(sp),min_common_dates=min(x[2] for x in sp),max_common_dates=max(x[2] for x in sp),n_valid_bootstrap=nboot,block_days=14))
    support.extend(dict(target=target,factor=f,group_a=ga,group_b=gb,station_a=sa,station_b=sb,n_common_dates=n) for sa,sb,n in sp)
   # Same observed rows, alternative labels; summary does not pretend identical groups.
   variants={'primary':col}
   if f=='terrain':variants.update({'radius250':'terrain_group_250m','radius1000':'terrain_group_1000m','cut075':'terrain_group_cut075','cut125':'terrain_group_cut125'})
   if f=='urban':
    for radius in [250,1000]:
     key='urban_'+str(radius);geo[key]=np.where(geo[f'restricted_fraction_{radius}m']>=.5,'high',np.where(geo[f'restricted_fraction_{radius}m']>=.2,'mixed','low'));variants['radius'+str(radius)]=key
    geo['urban_broad']=np.where(geo.developed_fraction_500m>=.5,'high',np.where(geo.developed_fraction_500m>=.2,'mixed','low'));variants['broad']= 'urban_broad'
   for variant,label in variants.items():
    lab=geo.loc[codes,label]
    for g,cs in lab.groupby(lab).groups.items():
     vals=dd[dd.station_code.isin(cs)]
     sensitivity.append(dict(target=target,factor=f,variant=variant,group=g,n_stations=len(cs),n_cases=len(vals),mean_value=float(vals.groupby('station_code')[field].mean().mean()),stations=';'.join(cs)))
   print('geographic',target,f,'done',flush=True)
  save(scores,'geographic_means.csv');save(paired,'geographic_matched_contrasts_D3.csv');save(support,'geographic_pair_support_D3.csv');save(strict,'geographic_strict_common_D3.csv');save(sensitivity,'geographic_label_sensitivity_D3.csv');save(groupcounts,'group_station_counts.csv')
 # Numeric factor correlation is descriptive at site level, not repeated forecast rows.
 cols=sum(FACTORS.values(),[]);geo[cols].corr(method='spearman').to_csv(OUT/'factor_spearman.csv')
 print('GEOGRAPHY COMPLETE',flush=True)
if __name__=='__main__':
 with threadpool_limits(limits=4):main()
