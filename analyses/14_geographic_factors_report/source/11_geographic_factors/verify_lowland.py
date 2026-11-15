"""Independently join each lowland station pair and check signed D3 contrasts."""
import json,itertools
import numpy as np
import pandas as pd
from run_models import LOCAL,OUT
rows=pd.read_csv(OUT/'lowland_matched_contrasts_D3.csv');checked=0
for target in ['Tmax','Tmin']:
 q=pd.read_pickle(LOCAL/(target+'_cases.pkl'));q=q[q.elevation_m.lt(300)&q.lead.eq(3)].copy();q['loss']=(q.forecast-q.y).abs()
 assert q.station_code.nunique()==29
 for r in rows[rows.target.eq(target)].itertuples():
  b,a=r.contrast.split(' minus ');col=r.factor+'_group';left=q[q[col].eq(a)];right=q[q[col].eq(b)]
  z=left[['station_code','valid_date','loss']].merge(right[['station_code','valid_date','loss']],on='valid_date',suffixes=('_a','_b'))
  z['diff']=z.loss_b-z.loss_a;by=z.groupby(['station_code_a','station_code_b']).agg(mean=('diff','mean'),n=('diff','size'))
  assert np.isclose(by['mean'].mean(),r.difference,atol=1e-12)
  assert by.n.min()==r.min_common_dates and by.n.max()==r.max_common_dates
  assert left.station_code.nunique()==r.n_stations_a and right.station_code.nunique()==r.n_stations_b
  assert r.n_valid_bootstrap==2000 and r.ci_low<=r.difference<=r.ci_high
  checked+=1
result={'passed':True,'independent_lowland_contrasts':checked,'scope':'Independent explicit date joins, pair mean then equal-pair mean, sign, station counts and support. Bootstrap algorithm covered separately by primary verifier.'}
(OUT/'lowland_verification.json').write_text(json.dumps(result,indent=2));print(result)
