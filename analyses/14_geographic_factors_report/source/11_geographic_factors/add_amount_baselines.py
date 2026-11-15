"""Add zero/median amount baselines without rerunning unchanged ML fits."""
import pandas as pd
from run_models import LOCAL,OUT,fit_predict,mean_score,save
t='rain_amount';q=pd.read_pickle(LOCAL/(t+'_cases.pkl'));fin=q[q.valid_date<'2025-01-01'];test=q[q.valid_date.ge('2025-01-01')&q.issue_date.ge('2025-01-01')]
sel=pd.read_csv(OUT/(t+'_selection.csv')).to_dict('records');scores=pd.read_csv(OUT/(t+'_primary_scores.csv')).to_dict('records')
new=['zero','category_median','station_median'];sel=[r for r in sel if r['method'] not in new];scores=[r for r in scores if r['method'] not in new]
for design in ['temporal','spatial']:
 p=pd.read_csv(LOCAL/(t+'_'+design+'_predictions.csv.gz'))
 assert list(p.case_id)==list(test.case_id)
 for method in new:
  p[method]=float('nan')
  for fold in ([-1] if design=='temporal' else sorted(test.spatial_fold.unique())):
   te=test if fold==-1 else test[test.spatial_fold.eq(fold)];train=fin if fold==-1 else fin[~fin.station_code.isin(te.station_code)]
   z=fit_predict(train,te,t,method)
   mapping=dict(zip(te.case_id,z));mask=p.case_id.isin(mapping);p.loc[mask,method]=p.loc[mask,'case_id'].map(mapping)
   sel.append(dict(target=t,design=design,fold=int(fold),method=method,param=None))
  scores.append(dict(target=t,design=design,method=method,primary_loss=mean_score(test,p[method],t),n_cases=len(test)))
 p.to_csv(LOCAL/(t+'_'+design+'_predictions.csv.gz'),index=False,compression='gzip')
save(sel,t+'_selection.csv');save(scores,t+'_primary_scores.csv');print(pd.DataFrame(scores).tail(6).to_string(index=False))
