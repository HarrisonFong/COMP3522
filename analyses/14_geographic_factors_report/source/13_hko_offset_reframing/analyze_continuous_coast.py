"""Continuous coastal distance: descriptive site OLS and within-date models.

All fits are retrospective associations, with frozen HKO-reference offsets.
No 2025 model selection; distance in km is specified directly, not log distance.
"""
from pathlib import Path
import sys,os,json
os.environ.setdefault('OPENBLAS_NUM_THREADS','4')
import numpy as np
import pandas as pd
from scipy.stats import pearsonr,spearmanr
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];R=HERE/'results'
sys.path.insert(0,str(HERE.parent/'12_geographic_deepening'))
import run_deepening as g
g.S['coast_km']=g.S.coast_distance_m/1000
S=g.S;COHORTS={'all32':S.index.tolist(),'low29':S.index[S.elevation_m.lt(200)].tolist()}
def save(rows,name):pd.DataFrame(rows).to_csv(R/('continuous_coast_'+name+'.csv'),index=False,encoding='utf-8-sig')
def slope(x,y):return float(np.dot(x-x.mean(),y-y.mean())/np.sum((x-x.mean())**2))
def date_slope(q):
 x=q.coast_km-q.groupby('valid_date').coast_km.transform('mean');y=q.loss-q.groupby('valid_date').loss.transform('mean');w=1/q.groupby('valid_date').loss.transform('size')
 return float((w*x*y).sum()/(w*x*x).sum())
def main():
 cal=pd.date_range('2025-01-01','2025-12-31');w=g.block_weights(365,14,2000)
 summary=[];sites=[];regressions=[];influence=[];common=[];verification=[]
 for target in ['Tmax','Tmin']:
  raw=pd.read_csv(ROOT/f'analysis/hko-offset-20261114/{target}_2025_errors.csv.gz',parse_dates=['valid_date']);raw=raw[raw.lead.eq(3)].copy()
  for cohort,codes in COHORTS.items():
   a=raw[raw.station_code.isin(codes)].copy()
   for version in ['raw','offset']:
    a['loss']=a[version+'_error'].abs();q=a[['station_code','valid_date','loss']].merge(S[['coast_km']],left_on='station_code',right_index=True,validate='many_to_one')
    p=q.pivot(index='valid_date',columns='station_code',values='loss').reindex(cal).reindex(columns=sorted(codes));x=S.loc[p.columns,'coast_km'].to_numpy();y=p.mean().to_numpy()
    b=slope(x,y);intercept=float(y.mean()-b*x.mean());fit=intercept+b*x;ss=float(np.sum((y-fit)**2));r2=1-ss/np.sum((y-y.mean())**2)
    count=w@p.notna().to_numpy(float);means=(w@p.fillna(0).to_numpy())/count;beta=means@(x-x.mean())/np.sum((x-x.mean())**2);lo,hi=np.quantile(beta,[.025,.975])
    row=dict(target=target,cohort=cohort,version=version,n_stations=len(codes),n_dates=q.valid_date.nunique(),n_cases=len(q),intercept=intercept,slope_per_km=b,ci_low=lo,ci_high=hi,pearson=pearsonr(x,y).statistic,spearman=spearmanr(x,y).statistic,r_squared=r2,min_km=x.min(),max_km=x.max())
    yy=p.dropna();common.append(dict(target=target,cohort=cohort,version=version,n_common_dates=len(yy),months=';'.join(map(str,sorted(yy.index.month.unique()))),slope_per_km=slope(x,yy.mean().to_numpy())))
    for code,xx,yv,n in zip(p.columns,x,y,p.notna().sum()):sites.append(dict(target=target,cohort=cohort,version=version,station_code=code,coast_km=xx,mae=yv,n_dates=n,elevation_m=S.loc[code,'elevation_m']))
    loo=[];dl=[]
    for j,code in enumerate(p.columns):
     keep=np.arange(len(x))!=j;sb=slope(x[keep],y[keep]);db=date_slope(q[q.station_code.ne(code)]);loo.append(sb);dl.append(db)
     influence.append(dict(target=target,cohort=cohort,version=version,removed_station=code,site_slope_per_km=sb,date_slope_per_km=db))
    row.update(leave_one_site_slope_min=min(loo),leave_one_site_slope_max=max(loo),leave_one_date_slope_min=min(dl),leave_one_date_slope_max=max(dl));summary.append(row)
    for name,features,region in [('coast_only',['coast_km'],False),('six_factors',['elevation_m','coast_km','restricted_fraction_500m','slope_deg','tpi_z_500m','relief_500m'],False),('six_factors_region',['elevation_m','coast_km','restricted_fraction_500m','slope_deg','tpi_z_500m','relief_500m'],True)]:
     result=g.regression(q,features,cal,w,region)
     for r in result:
      r.update(target=target,cohort=cohort,version=version,model=name)
      if r['feature']=='coast_km':r.update(slope_per_km=r['coefficient']/r['scale_sd'],slope_ci_low=r['ci_low']/r['scale_sd'],slope_ci_high=r['ci_high']/r['scale_sd'])
      regressions.append(r)
     # Independent point check by explicit weighted date-demeaned least squares.
     st=S.loc[sorted(codes)];z=(st[features]-st[features].mean())/st[features].std(ddof=0)
     if region:z=pd.concat([z,pd.get_dummies(st.region4_group,dtype=float).drop(columns='HKI')],axis=1)
     names=z.columns.tolist();v=q[['station_code','valid_date','loss']].join(z,on='station_code');centered=v[names+['loss']]-v.groupby('valid_date')[names+['loss']].transform('mean');ww=1/np.sqrt(v.groupby('valid_date').loss.transform('size').to_numpy())
     direct=np.linalg.lstsq(centered[names].to_numpy()*ww[:,None],centered.loss.to_numpy()*ww,rcond=None)[0]
     assert np.allclose(direct,[r['coefficient'] for r in result],atol=1e-10)
     verification.append(dict(target=target,cohort=cohort,version=version,model=name,max_abs_difference=float(max(abs(direct-np.array([r['coefficient'] for r in result]))))))
    assert np.allclose(np.polyfit(x,y,1),[b,intercept],atol=1e-10)
    # Separate block-index construction verifies the site slope interval.
    rng=np.random.default_rng(3536);starts=rng.integers(365,size=(2000,27));draws=((starts[:,:,None]+np.arange(14))%365).reshape(2000,-1)[:,:365]
    wb=np.stack([np.bincount(d,minlength=365) for d in draws]);bs=((wb@p.fillna(0).to_numpy())/(wb@p.notna().to_numpy(float)))@(x-x.mean())/np.sum((x-x.mean())**2)
    assert np.allclose(np.quantile(bs,[.025,.975]),[lo,hi],atol=1e-10)
  print(target,'continuous coastline done',flush=True)
 for data,name in [(summary,'site_regressions'),(sites,'station_points'),(regressions,'date_regressions'),(influence,'leave_one_station_out'),(common,'strict_common_sensitivity'),(verification,'verification_models')]:save(data,name)
 (R/'continuous_coast_metadata.json').write_text(json.dumps(dict(passed=True,period='2025 D3',cohorts=COHORTS,primary_x='untransformed shortest coast distance in km',site_regression='OLS of equal-weight station MAE; each site own available dates, descriptive',date_regression='Within-date centering; equal date weight and equal available station weight within date; no station FE',bootstrap='2000 circular 14-day calendar blocks, seed 3536; fixed sites and frozen offset fits',limitations='Sparse inland sites; spatial station dependence and training-fit uncertainty not captured; exploratory, no causal interpretation or linear extrapolation',independently_verified_models=len(verification)),ensure_ascii=False,indent=2),encoding='utf-8')
 print(pd.DataFrame(summary)[['target','cohort','version','slope_per_km','ci_low','ci_high','pearson','spearman','r_squared']].to_string(index=False))
 print(pd.DataFrame(regressions).query("feature=='coast_km'")[['target','cohort','version','model','slope_per_km','slope_ci_low','slope_ci_high']].to_string(index=False))
if __name__=='__main__':
 with threadpool_limits(limits=4):main()
