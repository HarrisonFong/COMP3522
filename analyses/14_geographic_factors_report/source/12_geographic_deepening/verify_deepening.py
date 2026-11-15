"""Independent aggregation, rank-matrix algebra and row-wise least-squares checks."""
from pathlib import Path
import json,itertools
import numpy as np
import pandas as pd
from scipy.stats import spearmanr,pearsonr
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;R=HERE/'results';ROOT=HERE.parents[2];AUDIT=ROOT/'analysis/geographic-deepening-20261114'
S=pd.read_csv(R/'station_definitions.csv').set_index('station_code');defs=json.loads((R/'definitions.json').read_text());cohorts=defs['cohorts'];counts={}
reg=pd.read_csv(R/'date_adjusted_regressions.csv');corr=pd.read_csv(R/'outcome_correlations.csv');groups=pd.read_csv(R/'group_means.csv');matched=pd.read_csv(R/'matched_contrasts.csv')
def check(v):assert v
def close(a,b):np.testing.assert_allclose(a,b,atol=2e-10,rtol=2e-9)
with threadpool_limits(limits=4):
 for target in ['Tmax','Tmin','rain_event','rain_amount']:
  q=pd.read_csv(AUDIT/(target+'_D3_audit.csv.gz'),parse_dates=['valid_date']);q=q.join(S,on='station_code');q['squared_error']=(q.forecast-q.y)**2
  close(q.loss,q.squared_error if target=='rain_event' else abs(q.forecast-q.y));check(not q.duplicated(['station_code','valid_date']).any())
  for r in groups[groups.target.eq(target)].itertuples():
   d=q[q.station_code.isin(cohorts[r.cohort])&q[r.scheme].eq(r.group)];by=d.groupby('station_code').loss.mean()
   close(by.mean(),r.loss);check(len(by)==r.n_stations and len(d)==r.n_cases)
  for r in matched[matched.target.eq(target)].itertuples():
   gb,ga=r.contrast.split(' minus ');d=q[q.station_code.isin(cohorts[r.cohort])];a=d[d[r.scheme].eq(ga)];b=d[d[r.scheme].eq(gb)]
   z=a[['station_code','valid_date','loss']].merge(b[['station_code','valid_date','loss']],on='valid_date',suffixes=('_a','_b'));z['delta']=z.loss_b-z.loss_a
   by=z.groupby(['station_code_a','station_code_b']).delta.agg(['mean','size']);close(by['mean'].mean(),r.difference);check(by['size'].min()==r.min_common_dates and by['size'].max()==r.max_common_dates)
  for (cohort,urban,region),rows in reg[reg.target.eq(target)].groupby(['cohort','urban_definition','region_adjustment']):
   d=q[q.station_code.isin(cohorts[cohort])].copy();sites=S.loc[sorted(d.station_code.unique())];features=[f for f in rows.feature if f in S.columns]
   vals=(sites[features]-sites[features].mean())/sites[features].std(ddof=0)
   if region:vals=pd.concat([vals,pd.get_dummies(sites.region4_group,dtype=float).drop(columns='HKI')],axis=1)
   names=rows.feature.tolist();vals=vals[names];x=vals.loc[d.station_code].reset_index(drop=True);y=d.loss.reset_index(drop=True);dates=d.valid_date.reset_index(drop=True);x=x-x.groupby(dates).transform('mean');y=y-y.groupby(dates).transform('mean');n=dates.map(dates.value_counts()).to_numpy();weight=1/n
   beta=np.linalg.lstsq(x.to_numpy()*np.sqrt(weight)[:,None],y.to_numpy()*np.sqrt(weight),rcond=None)[0];close(beta,rows.coefficient)
   close(1-np.sum(weight*(y-x@beta)**2)/np.sum(weight*y*y),rows.within_date_r2.iloc[0])
   # Independent raw-moment formula for within-day normal equations, then whole interval.
   cal=pd.date_range('2022-01-01' if target in ['Tmax','Tmin'] else '2025-01-01','2025-12-31');nd=len(cal);k=len(names);AA=np.zeros((nd,k,k));BB=np.zeros((nd,k))
   raw=vals.loc[d.station_code].to_numpy();yy=d.loss.to_numpy();inds=pd.Series(np.arange(len(d)),index=d.valid_date)
   for dt,ix in inds.groupby(level=0):
    idx=ix.to_numpy();xx=raw[idx];zz=yy[idx];j=cal.get_loc(dt);AA[j]=xx.T@xx/len(idx)-np.outer(xx.mean(axis=0),xx.mean(axis=0));BB[j]=xx.T@zz/len(idx)-xx.mean(axis=0)*zz.mean()
   rng=np.random.default_rng(3536);starts=rng.integers(nd,size=(2000,int(np.ceil(nd/14))));idx=((starts[:,:,None]+np.arange(14))%nd).reshape(2000,-1)[:,:nd];W=np.zeros((2000,nd))
   for j,rr in enumerate(idx):W[j]=np.bincount(rr,minlength=nd)
   boot=np.linalg.solve((W@AA.reshape(nd,-1)).reshape(2000,k,k),(W@BB)[...,None])[...,0];lo,hi=np.quantile(boot,[.025,.975],axis=0);close(lo,rows.ci_low);close(hi,rows.ci_high)
   counts['regression_models']=counts.get('regression_models',0)+1
  for (cohort,urban),rs in corr[corr.target.eq(target)].groupby(['cohort','urban_definition']):
   st=q[q.station_code.isin(cohorts[cohort])].groupby('station_code').loss.mean().to_frame().join(S);features=rs.feature.tolist();matrix=st[features+['loss']].rank().corr().to_numpy();precision=np.linalg.inv(matrix)
   for j,f in enumerate(features):
    row=rs[rs.feature.eq(f)].iloc[0];close(spearmanr(st[f],st.loss).statistic,row.spearman);close(pearsonr(st[f],st.loss).statistic,row.pearson);close(-precision[j,-1]/np.sqrt(precision[j,j]*precision[-1,-1]),row.partial_spearman)
  print('verified',target,flush=True)
 for (cohort,urban),q in pd.read_csv(R/'vif.csv').groupby(['cohort','urban_definition']):
  st=S.loc[cohorts[cohort],q.feature];diagonal=np.diag(np.linalg.inv(st.corr().to_numpy()));close(diagonal,q.vif)
 old=pd.read_csv(R/'old_coast_reconciliation.csv');close(old.old_mae,old.recomputed_mae)
 check(S.loc[cohorts['lowland']].elev_detail.value_counts().to_dict()=={'lt20':11,'20to50':9,'50to300':9})
 counts.update(passed=True,group_summaries=len(groups),matched_contrasts=len(matched),correlations=len(corr),old_coast_means=len(old),bootstrap_draws_per_regression=2000,scope='Independent date-join contrasts; row-weighted least squares; raw-moment block bootstrap intervals; precision-matrix partial Spearman and VIF; group means and source-loss arithmetic. No scientific causality validation.')
 (R/'verification.json').write_text(json.dumps(counts,indent=2),encoding='utf-8');print(counts)
