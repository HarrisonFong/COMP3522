"""Recompute published aggregates from saved cases/predictions, separately from fitting."""
from pathlib import Path
import json,itertools
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;OUT=HERE/'results';ROOT=HERE.parents[2];LOCAL=ROOT/'analysis/geographic-factors-20261114'
counts={'method_cells':0,'subgroup_cells':0,'geographic_contrasts':0,'sensitivity_rows':0,'threshold_rows':0}
metrics=pd.read_csv(OUT/'method_metrics.csv');sub=pd.read_csv(OUT/'method_by_geographic_group.csv');contr=pd.read_csv(OUT/'geographic_matched_contrasts_D3.csv');sens=pd.read_csv(OUT/'geographic_model_sensitivity.csv');threshold=pd.read_csv(OUT/'rain_event_threshold_metrics.csv')
def calc(q,p):
 z=q[['station_code','lead','y']].copy();z['error']=p-z.y;z['abs']=abs(z.error);z['sq']=z.error**2
 g=z.groupby(['station_code','lead']);return g['abs'].mean().mean(),np.sqrt(g.sq.mean().mean()),g.error.mean().mean(),g.sq.mean().mean()
for target in ['Tmax','Tmin','rain_event','rain_amount']:
 cases=pd.read_pickle(LOCAL/(target+'_cases.pkl'));event=target=='rain_event'
 for design in ['temporal','spatial']:
  p=pd.read_csv(LOCAL/(target+'_'+design+'_predictions.csv.gz'))
  for r in metrics[(metrics.target==target)&(metrics.design==design)].itertuples():
   mae,rmse,bias,bs=calc(p,p[r.method]);expected=[bs] if event else [mae,rmse,bias];saved=[r.brier] if event else [r.mae,r.rmse,r.bias]
   assert np.allclose(expected,saved,rtol=1e-10,atol=1e-10);counts['method_cells']+=len(expected)
  for r in sub[(sub.target==target)&(sub.design==design)].itertuples():
   q=p[p[r.factor+'_group']==r.group];mae,rmse,bias,bs=calc(q,q[r.method]);expected=bs if event else mae
   assert abs(expected-(r.brier if event else r.mae))<1e-10;counts['subgroup_cells']+=1
  if event:
   for r in threshold[threshold.design==design].itertuples():
    y=p.y.eq(1);a=p[r.method]>=r.threshold;counts4=[int((a&y).sum()),int((a&~y).sum()),int((~a&y).sum()),int((~a&~y).sum())]
    assert counts4==[r.tp,r.fp,r.fn,r.tn];counts['threshold_rows']+=1
 for r in contr[contr.target==target].itertuples():
  gb,ga=r.contrast.split(' minus ');q=cases[cases.lead.eq(3)].copy();q['value']=abs(q.forecast-q.y) if target in ['Tmax','Tmin'] else q.y
  sitesa=q.loc[q[r.factor+'_group']==ga,'station_code'].unique();sitesb=q.loc[q[r.factor+'_group']==gb,'station_code'].unique();a=q.pivot(index='valid_date',columns='station_code',values='value');diff=[];ns=[]
  for sa,sb in itertools.product(sitesa,sitesb):
   pair=a[[sa,sb]].dropna();diff.append(float((pair[sb]-pair[sa]).mean()));ns.append(len(pair))
  assert abs(np.mean(diff)-r.difference)<1e-10 and len(diff)==r.n_station_pairs and min(ns)==r.min_common_dates and max(ns)==r.max_common_dates;counts['geographic_contrasts']+=1
 for variant,rows in sens[sens.target==target].groupby('variant'):
  p=pd.read_csv(LOCAL/(target+'_sensitivity_'+variant+'.csv.gz'));primary=pd.read_csv(LOCAL/(target+'_temporal_predictions.csv.gz')).set_index('case_id').loc[p.case_id].reset_index()
  assert np.allclose(primary.y,p.y)
  for r in rows.itertuples():
   c=calc(p,p[r.method]);b=calc(primary,primary[r.method]);value=c[3] if event else c[0];base=b[3] if event else b[0]
   assert abs(value-r.loss)<1e-10 and abs(base-r.primary_on_same_cases)<1e-10;counts['sensitivity_rows']+=1
 print('aggregate verified',target,flush=True)
assert (pd.read_csv(OUT/'method_intervals.csv').n_finite==2000).all()
assert (pd.read_csv(OUT/'geographic_matched_contrasts_D3.csv').n_valid_bootstrap==2000).all()
out={'passed':True,**counts,'scope':'Independent groupby metrics, subgroup losses, threshold confusion counts, all matched D3 geographic contrast point estimates and supports, and sensitivity prediction scores. Existing interval algorithms separately checked in primary verifier; not a new inferential model.'}
(OUT/'summary_verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(out)
