from pathlib import Path
import os,sys,json,itertools,hashlib
os.environ.setdefault('OMP_NUM_THREADS','4');os.environ.setdefault('OPENBLAS_NUM_THREADS','4')
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];PREV=HERE.parent/'11_geographic_factors';OUT=HERE/'results';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(PREV))
from analyze_geography import block_weights,paired_group
LOCAL=ROOT/'analysis/geographic-factors-20261114'
AUDIT=ROOT/'analysis/geographic-deepening-20261114';AUDIT.mkdir(exist_ok=True)
S=pd.read_csv(PREV/'results/station_factors.csv').set_index('station_code')
S['log_height_intensity']=np.log1p(S.height_intensity_500m)
S['elev_detail']=pd.cut(S.elevation_m,[-np.inf,20,50,300,700,np.inf],right=False,labels=['lt20','20to50','50to300','300to700','ge700']).astype(str)
S['elev_fine']=pd.cut(S.elevation_m,[-np.inf,20,50,100,300,700,np.inf],right=False,labels=['lt20','20to50','50to100','100to300','300to700','ge700']).astype(str)
cuts=S.loc[S.elevation_m.lt(300),'elevation_m'].quantile([1/3,2/3]).tolist()
S['elev_tertiles']=np.select([S.elevation_m.le(cuts[0]),S.elevation_m.le(cuts[1]),S.elevation_m.lt(300)],['lower','middle','upper'],default='mountain')
for typ,col in [('urban_restricted','restricted_fraction_500m'),('urban_broad','developed_fraction_500m')]:S[typ]=np.where(S[col]<.2,'low',np.where(S[col]<.5,'mixed','high'))
S['urban_footprint']=S.building_group.str.replace('building_','').replace({'mid':'mixed'})
S['urban_height']=S.intensity_group.str.replace('intensity_','').replace({'mid':'mixed'})
COHORTS={'all':S.index.tolist(),'old30':S.index[~S.index.isin(['TC','TMS'])].tolist(),'lowland':S.index[S.elevation_m.lt(300)].tolist()}
URBAN={'restricted':'restricted_fraction_500m','broad':'developed_fraction_500m','footprint':'building_cover_500m','height':'log_height_intensity'}
BASE=['elevation_m','log_coast_km','restricted_fraction_500m','slope_deg','tpi_z_500m','relief_500m']
ALLFEATURES=BASE+['developed_fraction_500m','building_cover_500m','log_height_intensity']
SCHEMES=['elev_detail','elev_fine','elev_tertiles','coast_group','urban_restricted','urban_broad','urban_footprint','urban_height','region4_group','district_zh']
def save(rows,name):pd.DataFrame(rows).to_csv(OUT/(name+'.csv'),index=False,encoding='utf-8-sig')
def subset(q,cohort):return q[q.station_code.isin(COHORTS[cohort])]
def pearson(a,b):return float(np.corrcoef(a,b)[0,1])
def residual(a,x):return a-x@np.linalg.lstsq(x,a,rcond=None)[0]
def partial(q,x,y,controls):
 ranks=q[[x,y]+controls].rank().to_numpy();z=np.column_stack([np.ones(len(q)),ranks[:,2:]])
 return pearson(residual(ranks[:,0],z),residual(ranks[:,1],z))

def regression(q,features,cal,w,region=False):
 # Equal-date, equal observed station within date, no station FE.
 sites=S.loc[sorted(q.station_code.unique())];mu=sites[features].mean();sd=sites[features].std(ddof=0)
 x=(sites[features]-mu)/sd;names=features.copy()
 if region:
  dum=pd.get_dummies(sites.region4_group,dtype=float).drop(columns='HKI');x=pd.concat([x,dum],axis=1);names+=list(dum.columns)
 a=q[['station_code','valid_date','loss']].merge(x,left_on='station_code',right_index=True,validate='many_to_one')
 vals=a[names+['loss']].to_numpy();ix=cal.get_indexer(a.valid_date);k=len(names);n=np.bincount(ix,minlength=len(cal)).astype(float)
 sums=np.zeros((len(cal),k+1));np.add.at(sums,ix,vals);means=np.divide(sums,n[:,None],out=np.zeros_like(sums),where=n[:,None]>0)
 centered=vals-means[ix];xx=centered[:,:k];yy=centered[:,-1];weights=1/n[ix]
 A=np.zeros((len(cal),k,k));b=np.zeros((len(cal),k));Y=np.zeros(len(cal))
 np.add.at(A,ix,np.einsum('ni,nj,n->nij',xx,xx,weights));np.add.at(b,ix,xx*(yy*weights)[:,None]);np.add.at(Y,ix,yy**2*weights)
 normal=A.sum(axis=0);rhs=b.sum(axis=0);beta=np.linalg.solve(normal,rhs)
 aa=(w@A.reshape(len(cal),-1)).reshape(len(w),k,k);bb=w@b;boot=np.linalg.solve(aa,bb[...,None])[...,0]
 lo,hi=np.quantile(boot,[.025,.975],axis=0);r2=1-(Y.sum()-2*beta@rhs+beta@normal@beta)/Y.sum()
 return [dict(feature=f,coefficient=beta[j],ci_low=lo[j],ci_high=hi[j],scale_sd=sd[f] if f in features else 1.,n_stations=len(sites),n_dates=int((n>1).sum()),n_cases=len(q),within_date_r2=r2,condition_number=np.linalg.cond(normal),region_adjustment=region) for j,f in enumerate(names)]

def main():
 save(S.reset_index(),'station_definitions');defs={'lowland_fixed_edges_m':[20,50,300],'lowland_tertile_cuts_m':cuts,'cohorts':COHORTS,'urban_columns':URBAN,'note':'Exploratory operational cutoffs, not official HKO climate classes. Existing building empirical tertile thresholds are kept fixed, not recomputed after removing mountains.'}
 (OUT/'definitions.json').write_text(json.dumps(defs,ensure_ascii=False,indent=2),encoding='utf-8')
 matrices=[];vifs=[];cross=[]
 for cohort,codes in COHORTS.items():
  st=S.loc[codes]
  for method in ['pearson','spearman']:
   mat=st[ALLFEATURES].corr(method=method)
   for a in ALLFEATURES:
    for b in ALLFEATURES:matrices.append(dict(cohort=cohort,method=method,feature_a=a,feature_b=b,correlation=mat.loc[a,b],n_stations=len(st)))
  for urban,col in URBAN.items():
   cols=[col if x=='restricted_fraction_500m' else x for x in BASE];z=(st[cols]-st[cols].mean())/st[cols].std(ddof=0)
   for f in cols:
    y=z[f].to_numpy();x=np.column_stack([np.ones(len(z)),z.drop(columns=f)]);r2=1-np.sum(residual(y,x)**2)/np.sum(y*y)
    vifs.append(dict(cohort=cohort,urban_definition=urban,feature=f,vif=1/(1-r2)))
  for sc in SCHEMES:
   for (reg,g),a in st.groupby(['region4_group',sc]) if sc!='region4_group' else []:
    cross.append(dict(cohort=cohort,region=reg,scheme=sc,group=g,n_stations=len(a),stations=';'.join(a.index)))
 save(matrices,'factor_correlations');save(vifs,'vif');save(cross,'region_factor_cross_counts')
 groupmeans=[];matched=[];stationrows=[];correlations=[];regs=[];influence=[];reconcile=[];sample=[]
 for target in ['Tmax','Tmin','rain_event','rain_amount']:
  temp=target in ['Tmax','Tmin']
  if temp:
   raw=pd.read_pickle(LOCAL/(target+'_cases.pkl'));q=raw[raw.lead.eq(3)][['station_code','valid_date','y','forecast']].copy();del raw
   q['loss']=(q.forecast-q.y).abs();q['error']=q.forecast-q.y;cal=pd.date_range('2022-01-01','2025-12-31');period='2022-2025 D3';baseline='raw public forecast'
  else:
   base='category_mean' if target=='rain_event' else 'category_median'
   raw=pd.read_csv(LOCAL/(target+'_temporal_predictions.csv.gz'),parse_dates=['valid_date']);q=raw[raw.lead.eq(3)][['station_code','valid_date','y',base]].rename(columns={base:'forecast'}).copy();del raw
   q['error']=q.forecast-q.y;q['loss']=q.error**2 if target=='rain_event' else q.error.abs();cal=pd.date_range('2025-01-01','2025-12-31');period='2025 D3';baseline=base
  w=block_weights(len(cal),14,2000)
  q=q.merge(S[SCHEMES],left_on='station_code',right_index=True,validate='many_to_one')
  q[['station_code','valid_date','y','forecast','loss','error']].to_csv(AUDIT/(target+'_D3_audit.csv.gz'),index=False,compression='gzip')
  site=q.groupby('station_code').agg(loss=('loss','mean'),bias=('error','mean'),n_dates=('valid_date','nunique'),observed_mean=('y','mean')).join(S)
  for code,r in site.iterrows():stationrows.append(dict(target=target,station_code=code,loss=r.loss,bias=r.bias,n_dates=r.n_dates,observed_mean=r.observed_mean,period=period,baseline=baseline))
  for cohort in COHORTS:
   d=subset(q,cohort);st=site.loc[sorted(d.station_code.unique())]
   sample.append(dict(target=target,cohort=cohort,n_stations=len(st),n_cases=len(d),n_dates=d.valid_date.nunique(),station_equal_loss=st.loss.mean(),station_equal_bias=st.bias.mean(),stations=';'.join(st.index),period=period))
   for scheme in SCHEMES:
    for group,dd in d.groupby(scheme):
     z=dd.groupby('station_code').agg(loss=('loss','mean'),bias=('error','mean'),n=('loss','size'))
     groupmeans.append(dict(target=target,cohort=cohort,scheme=scheme,group=group,loss=z.loss.mean(),bias=z.bias.mean(),n_stations=len(z),n_cases=len(dd),min_days=z.n.min(),max_days=z.n.max(),stations=';'.join(z.index),period=period,baseline=baseline))
   # Correlations have one independent geographic unit per station, not repeated dates.
   for urban,col in URBAN.items():
    cols=[col if x=='restricted_fraction_500m' else x for x in BASE]
    for f in cols:
     controls=[x for x in cols if x!=f];val=partial(st,f,'loss',controls)
     loo=[partial(st.drop(index=code),f,'loss',controls) for code in st.index]
     correlations.append(dict(target=target,cohort=cohort,urban_definition=urban,feature=f,n_stations=len(st),pearson=pearson(st[f],st.loss),spearman=pearson(st[f].rank(),st.loss.rank()),partial_spearman=val,leave_one_min=min(loo),leave_one_max=max(loo),period=period))
   variants=list(URBAN.items()) if cohort!='old30' else [('restricted',URBAN['restricted'])]
   for urban,col in variants:
    features=[col if x=='restricted_fraction_500m' else x for x in BASE]
    for region in ([False,True] if urban=='restricted' and cohort!='old30' else [False]):
     rows=regression(d,features,cal,w,region)
     regs.extend(dict(target=target,cohort=cohort,urban_definition=urban,period=period,baseline=baseline,**r) for r in rows)
   # Only prespecified contrasts, never choose groups after viewing losses.
   contrast_specs=[('coast_group','near','inland')]
   if cohort in ['all','lowland']:
    contrast_specs += [(sc,'high','low') for sc in ['urban_restricted','urban_broad','urban_footprint','urban_height']]
    contrast_specs += [('region4_group',a,b) for a,b in itertools.combinations(sorted(st.region4_group.unique()),2)]
   if cohort=='lowland':
    contrast_specs += [('elev_detail',a,b) for a,b in itertools.combinations(['lt20','20to50','50to300'],2)]
    contrast_specs += [('elev_tertiles',a,b) for a,b in itertools.combinations(['lower','middle','upper'],2)]
   a=d.pivot(index='valid_date',columns='station_code',values='loss').reindex(cal)
   for scheme,ga,gb in contrast_specs:
    ca=list(st.index[st[scheme].eq(ga)]);cb=list(st.index[st[scheme].eq(gb)])
    if not ca or not cb:continue
    result=paired_group(a,ca,cb,w)
    if result:
     point,lo,hi,support,n=result
     matched.append(dict(target=target,cohort=cohort,scheme=scheme,contrast=gb+' minus '+ga,difference=point,ci_low=lo,ci_high=hi,n_a=len(ca),n_b=len(cb),n_pairs=len(support),min_common_dates=min(r[2] for r in support),max_common_dates=max(r[2] for r in support),n_boot=n,period=period))
   print(target,cohort,'complete',flush=True)
  if temp:
   for omit in ['none','NGP','TC','TMS','TC;TMS','NGP;TC;TMS']:
    codes=[c for c in S.index if c not in omit.split(';')];dd=q[q.station_code.isin(codes)];st=site.loc[codes]
    for measure in ['loss','bias']:
     influence.append(dict(target=target,omitted=omit,measure=measure,value=st[measure].mean(),n_stations=len(codes)))
   old=pd.read_csv(HERE.parent/'09_geographic_temperature/results/group_metrics.csv')
   old=old[old.design.eq('all_available')&old.factor.eq('coast')&old.variable.eq(target)&old.lead.eq(3)]
   for r in old.itertuples():
    new=next(g for g in groupmeans if g['target']==target and g['cohort']=='old30' and g['scheme']=='coast_group' and g['group']==r.group)
    reconcile.append(dict(target=target,group=r.group,old_mae=r.mae,recomputed_mae=new['loss'],difference=new['loss']-r.mae))
  for name,rows in [('group_means',groupmeans),('matched_contrasts',matched),('station_outcomes',stationrows),('outcome_correlations',correlations),('date_adjusted_regressions',regs),('mountain_influence',influence),('old_coast_reconciliation',reconcile),('sample_summary',sample)]:save(rows,name)
 metadata={'date':'2026-11-14','seed':3522,'bootstrap':{'reps':2000,'calendar_block_days':14,'scope':'fixed stations; date resampling, no station-population or geographic-source uncertainty'},'station_source_sha256':hashlib.sha256((PREV/'results/station_factors.csv').read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'temperature_period':'2022-2025 D3 raw public forecast','rain_period':'2025 D3 research PSR-category baseline','regression':'OLS loss ~ date fixed effects + six standardized static geographical features; equal date weight, equal observed-station weight within date; all / old30 / lowland; alternate urban proxies one at a time, region-dummy sensitivity','correlation':'station-level available-date mean losses; Pearson, Spearman and partial Spearman controlling other five; leave-one-station range is sensitivity, not CI'}
 (OUT/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8');print('DONE',flush=True)
if __name__=='__main__':
 with threadpool_limits(limits=4):main()
