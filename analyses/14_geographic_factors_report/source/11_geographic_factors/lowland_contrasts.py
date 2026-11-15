import itertools
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from run_models import LOCAL,OUT,save
from analyze_geography import paired_group,block_weights
rows=[];cal=pd.date_range('2022-01-01','2025-12-31');w=block_weights(len(cal),14)
with threadpool_limits(limits=4):
 for target in ['Tmax','Tmin']:
  q=pd.read_pickle(LOCAL/(target+'_cases.pkl'));q=q[q.elevation_m.lt(300)&q.lead.eq(3)].copy();q['ae']=abs(q.forecast-q.y)
  a=q.pivot(index='valid_date',columns='station_code',values='ae').reindex(cal)
  for factor in ['coast','urban','terrain']:
   groups={g:list(d.station_code.unique()) for g,d in q.groupby(factor+'_group')}
   for ga,gb in itertools.combinations(groups,2):
    point,lo,hi,support,n=paired_group(a,groups[ga],groups[gb],w)
    rows.append(dict(target=target,factor=factor,contrast=gb+' minus '+ga,difference=point,ci_low=lo,ci_high=hi,n_stations_a=len(groups[ga]),n_stations_b=len(groups[gb]),min_common_dates=min(x[2] for x in support),max_common_dates=max(x[2] for x in support),n_valid_bootstrap=n,scope='all 29 AWS below 300m, D3, pair-specific common dates'))
save(rows,'lowland_matched_contrasts_D3.csv');print(pd.DataFrame(rows).query("factor=='coast'").to_string(index=False))
