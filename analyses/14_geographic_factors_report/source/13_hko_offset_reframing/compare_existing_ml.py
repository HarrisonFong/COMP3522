"""Compare already-fitted ML predictions against frozen observed HKO offsets."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];R=HERE/'results'
sys.path.insert(0,str(HERE.parent/'11_geographic_factors'))
from analyze_geography import block_weights
def main():
 rows=[];checks=[];cal=pd.date_range('2025-01-01','2025-12-31');w=block_weights(365,14,2000)
 for t in ['Tmax','Tmin']:
  ref=pd.read_csv(ROOT/f'analysis/hko-offset-20261114/{t}_2025_errors.csv.gz',parse_dates=['valid_date'])
  for cohort,suffix in [('all32','temporal_predictions'),('low29','sensitivity_lowland')]:
   m=pd.read_csv(ROOT/f'analysis/geographic-factors-20261114/{t}_{suffix}.csv.gz',parse_dates=['valid_date'])
   q=m.merge(ref[['station_code','valid_date','lead','y','offset_error']],on=['station_code','valid_date','lead'],validate='one_to_one',suffixes=('','_ref'))
   assert len(q)==len(m) and np.allclose(q.y,q.y_ref)
   for method in ['station_mean','station_median','linear_full','hgb_full']:
    z=q[['station_code','valid_date','lead']].copy();z['delta']=abs(q[method]-q.y)-abs(q.offset_error)
    p=z.pivot(index='valid_date',columns=['station_code','lead'],values='delta').reindex(cal)
    point=p.mean().mean();boot=((w@p.fillna(0).to_numpy())/(w@p.notna().to_numpy(float))).mean(axis=1);lo,hi=np.quantile(boot,[.025,.975])
    independent=z.groupby(['station_code','lead']).delta.mean().mean();assert abs(independent-point)<1e-12
    rows.append(dict(target=t,cohort=cohort,method=method,reference='hko_observed_offset',mae_difference=point,ci_low=lo,ci_high=hi,n_cases=len(q),n_stations=q.station_code.nunique(),meaning='negative favours ML/residual correction over HKO observed offset'))
   checks.append(dict(target=t,cohort=cohort,n_cases=len(q),identical_observations=True))
 pd.DataFrame(rows).to_csv(R/'restored_ml_vs_hko.csv',index=False,encoding='utf-8-sig')
 (R/'restored_ml_verification.json').write_text(json.dumps(dict(passed=True,matched_cases=checks,fits='existing fits reused; no 2025 selection or new fitting',bootstrap='2000 circular 14-day calendar blocks seed 3536; fixed sites and fits'),indent=2),encoding='utf-8')
 print(pd.DataFrame(rows).query("method=='hgb_full'").to_string(index=False))
if __name__=='__main__':
 with threadpool_limits(limits=4):main()
