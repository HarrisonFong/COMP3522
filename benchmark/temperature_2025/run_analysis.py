"""Read-only annual benchmark; writes only local derived evidence and cache."""
from __future__ import annotations
import argparse
from bisect import bisect_right
from collections import Counter,defaultdict
import csv,gzip,hashlib,json,math,sys,traceback
from datetime import date,datetime,time,timedelta
from functools import lru_cache
from pathlib import Path
import numpy as np
from annual_methods import START,END,UTC,HKT,BASE,SCENARIOS,reconstruct,error_bounds,ci,revision

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'data_management/model_forecasts'))
from manage_gfs import connect
CACHE=HERE/'cache/snapshot.json.gz'
QUERIES={
'station':"SELECT station_code,station_name,latitude,longitude,elevation_m FROM project.hko_station WHERE station_code='HKO'",
'catalog':"""SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns
 WHERE table_schema='project' AND table_name IN ('external_model_source','external_model_temperature',
 'hko_forecast_daily','hko_forecast_issue','hko_daily_observation') ORDER BY 1,ordinal_position""",
'gfs':"""SELECT s.source_id,s.run_time_utc,s.forecast_hour,t.message_number,t.short_name,t.step_type,
 t.interval_start_utc,t.valid_time_utc,t.temperature_c,t.grid_latitude,t.grid_longitude,t.grid_distance_km,
 (s.manifest->'grib_message_metadata'->(t.message_number-1)->>'quantization_step_k')::float8 AS packing_step_c,
 s.manifest->>'availability_time_utc' AS historical_availability
 FROM project.external_model_source s JOIN project.external_model_temperature t USING(source_id)
 WHERE s.model='GFS' AND s.product='pgrb2.0p25' AND t.station_code='HKO'
 AND s.run_time_utc >= %(run_start)s AND s.run_time_utc < %(run_end)s
 ORDER BY s.run_time_utc,s.forecast_hour,t.message_number""",
'forecasts':"""SELECT f.forecast_issue_id,i.source_file_id,i.bulletin_time_hkt,i.published_time_utc,
 f.valid_date,f.lead_days,f.forecast_tmax_c,f.forecast_tmin_c
 FROM project.hko_forecast_daily f JOIN project.hko_forecast_issue i USING(forecast_issue_id)
 WHERE f.valid_date >= %(start)s AND f.valid_date < %(end)s AND f.lead_days BETWEEN 1 AND 9
 ORDER BY f.valid_date,i.bulletin_time_hkt,f.forecast_issue_id""",
'observations':"""SELECT s.series_code,o.observation_date,o.observation_series_id,
 o.value_numeric,o.value_text,o.data_completeness FROM project.hko_daily_observation o
 JOIN project.hko_observation_series s USING(observation_series_id)
 WHERE s.series_code IN ('obs_hko_daily_tmax','obs_hko_daily_tmin')
 AND o.observation_date >= %(start)s AND o.observation_date < %(end)s ORDER BY 1,2""",
}


def encode(value):
    if isinstance(value,datetime):return {'__datetime__':value.isoformat()}
    if isinstance(value,date):return {'__date__':value.isoformat()}
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,Path):return str(value)
    try:return float(value)
    except (TypeError,ValueError):return str(value)


def hook(value):
    if set(value)=={'__datetime__'}:return datetime.fromisoformat(value['__datetime__'])
    if set(value)=={'__date__'}:return date.fromisoformat(value['__date__'])
    return value


def save_json(name,value):
    (HERE/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,default=encode)+'\n',encoding='utf-8',newline='\n')


def write_csv(name,rows):
    with (HERE/name).open('w',newline='',encoding='utf-8') as f:
        if not rows:f.write('scenario,variable,valid_date,lead_days,reason\n');return
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def load(offline):
    if offline:
        with gzip.open(CACHE,'rt',encoding='utf-8') as f:return json.load(f,object_hook=hook)
    from psycopg.rows import dict_row
    params=dict(start=START,end=END,run_start=datetime(2024,12,24,tzinfo=UTC),run_end=datetime(2026,1,1,tzinfo=UTC))
    snap={}
    with connect() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        assert conn.execute('SHOW transaction_read_only').fetchone()[0]=='on'
        with conn.cursor(row_factory=dict_row) as c:
            for name,sql in QUERIES.items():c.execute(sql,params);snap[name]=c.fetchall()
        snap.update(snapshot_at_utc=datetime.now(UTC).isoformat(),database_read_only=True,database_writes=False)
    CACHE.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(CACHE,'wt',encoding='utf-8') as f:json.dump(snap,f,default=encode)
    return snap


def cases(snap):
    by_run=defaultdict(list);by_target=defaultdict(list);obs={};observation_audit=Counter()
    for r in snap['gfs']:
        r['temperature_c']=float(r['temperature_c'])
        if r['packing_step_c'] is None or not math.isfinite(r['packing_step_c']):raise ValueError('Unknown packing step')
        by_run[r['run_time_utc']].append(r)
    for r in snap['forecasts']:by_target[r['valid_date']].append(r)
    for r in snap['observations']:
        variable=r['series_code'].removeprefix('obs_hko_daily_');key=(variable,r['observation_date'])
        observation_audit[variable+'_rows']+=1
        if r['data_completeness']=='C' and r['value_numeric'] is not None:
            if key in obs:raise ValueError('Duplicate truth')
            obs[key]=float(r['value_numeric']);observation_audit[variable+'_valid']+=1
    # Expected runs are generated from the calendar, not only runs that happen
    # to be present. A missing latest run is excluded rather than silently aged.
    runs=[datetime(2024,12,24,tzinfo=UTC)+timedelta(hours=6*i) for i in range(1492)]
    completeness={run:len(rows)==193 and len({r['forecast_hour'] for r in rows})==65 for run,rows in by_run.items()}
    @lru_cache(maxsize=None)
    def endpoint(run,target,var):return reconstruct(by_run[run],target,var) if completeness.get(run) else None
    records=[];excluded=[];coverage=[]
    for scenario,(hour,lag) in SCENARIOS.items():
        counts=Counter()
        for day in range(365):
            target=START+timedelta(days=day)
            for lead in range(1,8):
                decision=target-timedelta(days=lead)
                cutoff=datetime.combine(decision,time(hour),HKT).astimezone(UTC)
                i=bisect_right(runs,cutoff-timedelta(hours=lag))-1
                run=runs[i] if i>=0 else None
                eligible=[r for r in by_target[target] if r['bulletin_time_hkt'].replace(tzinfo=HKT)<=cutoff
                          and r['published_time_utc'] is not None and r['published_time_utc']<=cutoff]
                hko=max(eligible,key=lambda r:(r['bulletin_time_hkt'],r['forecast_issue_id'])) if eligible else None
                for var in ('tmax','tmin'):
                    truth=obs.get((var,target));gfs=endpoint(run,target,var) if run else None
                    has_hko=hko is not None and hko['forecast_'+var+'_c'] is not None
                    counts[var+'_expected']+=1;counts[var+'_hko_present']+=has_hko
                    counts[var+'_gfs_reconstructed']+=gfs is not None;counts[var+'_truth']+=truth is not None
                    reason=('missing_truth' if truth is None else 'missing_hko_vintage_or_value' if not has_hko
                            else 'missing_gfs_run_or_daily_coverage' if gfs is None else None)
                    if reason:
                        excluded.append(dict(scenario=scenario,variable=var,valid_date=target,lead_days=lead,reason=reason));continue
                    counts[var+'_paired']+=1
                    row=dict(scenario=scenario,variable=var,valid_date=target,lead_days=lead,
                        cutoff_utc=cutoff,decision_date=decision,hko_issue_id=hko['forecast_issue_id'],
                        hko_source_file_id=hko['source_file_id'],hko_bulletin_hkt=hko['bulletin_time_hkt'],
                        hko_published_utc=hko['published_time_utc'],hko_age_hours=(cutoff-hko['bulletin_time_hkt'].replace(tzinfo=HKT)).total_seconds()/3600,
                        hko_stale=hko['bulletin_time_hkt'].date()<decision,gfs_run_utc=run,gfs_age_hours=(cutoff-run).total_seconds()/3600,
                        assumed_lag_hours=lag,hko=float(hko['forecast_'+var+'_c']),observed=truth,**gfs)
                    row['gfs_error_lower'],row['gfs_error_upper']=error_bounds(row['gfs_lower'],row['gfs_upper'],truth)
                    row['paired_delta_ae']=abs(row['gfs']-truth)-abs(row['hko']-truth)
                    records.append(row)
        coverage.append(dict(scenario=scenario,**counts))
    audit=dict(observations=dict(observation_audit),gfs_rows=len(snap['gfs']),gfs_runs=len(by_run),
               complete_gfs_runs=sum(completeness.values()),expected_gfs_runs=1492,
               missing_gfs_runs=[r.isoformat() for r in runs if not completeness.get(r)],
               actual_grid_points=sorted({(r['grid_latitude'],r['grid_longitude'],r['grid_distance_km']) for r in snap['gfs']}),
               historical_gfs_availability_populated=sum(r['historical_availability'] is not None for r in snap['gfs']),
               primary_stale_hko_cases=sum(r['hko_stale'] for r in records if r['scenario']==BASE))
    return records,excluded,coverage,audit


def score_group(rows,group):
    result=group|dict(n=len(rows),n_dates=len({r['valid_date'] for r in rows}))
    truth=np.array([r['observed'] for r in rows])
    for product in ('hko','gfs','gfs_sampled'):
        e=np.array([r[product] for r in rows])-truth
        result.update({product+'_mae':float(abs(e).mean()),product+'_rmse':float(np.sqrt((e*e).mean())),product+'_bias':float(e.mean())})
    delta=[r['paired_delta_ae'] for r in rows];dates=[r['valid_date'] for r in rows]
    result['delta_mae']=float(np.mean(delta));result['ci7_low'],result['ci7_high']=ci(delta,dates)
    result['ci14_low'],result['ci14_high']=ci(delta,dates,14)
    result['gfs_mae_lower']=float(np.mean([r['gfs_error_lower'] for r in rows]))
    result['gfs_mae_upper']=float(np.mean([r['gfs_error_upper'] for r in rows]))
    result['mean_envelope_width']=float(np.mean([r['envelope_width'] for r in rows]))
    return result


def scores(records):
    result=[]
    for scenario in SCENARIOS:
        for var in ('tmax','tmin'):
            rows=[r for r in records if r['scenario']==scenario and r['variable']==var]
            for lead in range(8):
                members=[r for r in rows if lead==0 or r['lead_days']==lead]
                if members:result.append(score_group(members,dict(scenario=scenario,variable=var,group='lead',value=str(lead))))
            if scenario!=BASE:continue
            for season,months in dict(DJF=(12,1,2),MAM=(3,4,5),JJA=(6,7,8),SON=(9,10,11)).items():
                members=[r for r in rows if r['valid_date'].month in months]
                if members:result.append(score_group(members,dict(scenario=scenario,variable=var,group='season',value=season)))
            for month in range(1,13):
                members=[r for r in rows if r['valid_date'].month==month and r['lead_days']==1]
                if members:result.append(score_group(members,dict(scenario=scenario,variable=var,group='month_D1',value=str(month))))
    return result


def revisions(records,base=BASE,include_intraday=True):
    trajectories=defaultdict(list)
    for r in records:
        if r['scenario']==base or (include_intraday and r['scenario'] in ('02HKT_lag6','08HKT_lag6','14HKT_lag6')):
            trajectories[(r['variable'],r['valid_date'])].append(r)
    pairs=[]
    for (variable,target),trajectory in sorted(trajectories.items()):
        for cadence in ((24,6) if include_intraday else (24,)):
            selected=sorted((r for r in trajectory if cadence==6 or r['scenario']==base),key=lambda r:r['cutoff_utc'])
            for old,new in zip(selected,selected[1:]):
                if (new['cutoff_utc']-old['cutoff_utc']).total_seconds()!=cadence*3600:continue
                pairs.append(dict(scenario=base,cadence_hours=cadence,variable=variable,valid_date=target,
                    old_cutoff_utc=old['cutoff_utc'],new_cutoff_utc=new['cutoff_utc'],
                    old_lead=old['lead_days'],new_lead=new['lead_days'],
                    old_hko_issue_id=old['hko_issue_id'],new_hko_issue_id=new['hko_issue_id'],
                    old_gfs_run_utc=old['gfs_run_utc'],new_gfs_run_utc=new['gfs_run_utc'],
                    observed=new['observed'],old_hko=old['hko'],new_hko=new['hko'],old_gfs=old['gfs'],new_gfs=new['gfs'],
                    **revision(old,new)))
    summaries=[];contrasts=[]
    for cadence in ((24,6) if include_intraday else (24,)):
        for variable in ('tmax','tmin'):
            allrows=[r for r in pairs if r['cadence_hours']==cadence and r['variable']==variable]
            for lead in ([0,*range(1,7)] if cadence==24 else [0]):
                rows=[r for r in allrows if lead==0 or r['new_lead']==lead]
                if not rows:continue
                group=dict(scenario=base,cadence_hours=cadence,variable=variable,new_lead=lead,n_pairs=len(rows),n_dates=len({r['valid_date'] for r in rows}))
                dates=[r['valid_date'] for r in rows]
                for product in ('hko','gfs'):
                    delta=np.array([r[product+'_delta'] for r in rows]);benefit=np.array([r[product+'_benefit'] for r in rows])
                    changed=abs(delta)>1e-10;material=abs(delta)>=1-1e-10
                    lo,hi=ci(benefit,dates)
                    summaries.append(group|dict(product=product,n_changed=int(changed.sum()),n_material=int(material.sum()),
                        vintage_refresh_rate_pct=100*float(np.mean([r['old_hko_issue_id']!=r['new_hko_issue_id'] if product=='hko'
                            else r['old_gfs_run_utc']!=r['new_gfs_run_utc'] for r in rows])),
                        revision_rate_pct=float(changed.mean()*100),material_revision_rate_pct=float(material.mean()*100),
                        rounded_revision_rate_pct=float(np.mean([r[product+'_rounded_changed'] for r in rows])*100),
                        mean_absolute_change=float(abs(delta).mean()),mean_error_reduction=float(benefit.mean()),benefit_ci7_low=lo,benefit_ci7_high=hi,
                        improved_all_pct=float((benefit>1e-10).mean()*100),worsened_all_pct=float((benefit< -1e-10).mean()*100),
                        tied_all_pct=float((abs(benefit)<=1e-10).mean()*100),
                        useful_changed_pct=float((benefit[changed]>1e-10).mean()*100) if changed.any() else None,
                        useful_material_pct=float((benefit[material]>1e-10).mean()*100) if material.any() else None,
                        mean_error_reduction_material=float(benefit[material].mean()) if material.any() else None))
                delta=[r['paired_benefit_delta'] for r in rows];lo,hi=ci(delta,dates);lo14,hi14=ci(delta,dates,14)
                # Shared intermediate forecasts cancel exactly along a chain.
                # Endpoint bounds are much tighter than independently bounding
                # every step and then averaging; retain both for inspection.
                chains=defaultdict(list)
                for r in rows:chains[r['valid_date']].append(r)
                bound_lo=bound_hi=0.
                for chain in chains.values():
                    chain.sort(key=lambda r:r['old_cutoff_utc'])
                    first=previous=chain[0]
                    for nxt in chain[1:]+[None]:
                        if nxt is None or nxt['old_cutoff_utc']!=previous['new_cutoff_utc']:
                            # Reconstruct bounds from the selected forecast cases,
                            # not from independently varied per-step benefits.
                            old=next(r for r in trajectories[(variable,first['valid_date'])] if r['cutoff_utc']==first['old_cutoff_utc'])
                            new=next(r for r in trajectories[(variable,previous['valid_date'])] if r['cutoff_utc']==previous['new_cutoff_utc'])
                            a,b=error_bounds(old['gfs_lower'],old['gfs_upper'],old['observed'])
                            c,d=error_bounds(new['gfs_lower'],new['gfs_upper'],new['observed'])
                            bound_lo+=a-d;bound_hi+=b-c
                            first=nxt
                        previous=nxt
                contrasts.append(group|dict(gfs_minus_hko_benefit=float(np.mean(delta)),ci7_low=lo,ci7_high=hi,ci14_low=lo14,ci14_high=hi14,
                    gfs_benefit_lower=float(np.mean([r['gfs_benefit_lower'] for r in rows])),
                    gfs_benefit_upper=float(np.mean([r['gfs_benefit_upper'] for r in rows])),
                    gfs_chain_benefit_lower=bound_lo/len(rows),gfs_chain_benefit_upper=bound_hi/len(rows),
                    paired_chain_benefit_lower=bound_lo/len(rows)-float(np.mean([r['hko_benefit'] for r in rows])),
                    paired_chain_benefit_upper=bound_hi/len(rows)-float(np.mean([r['hko_benefit'] for r in rows]))))
    return pairs,summaries,contrasts


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--offline',action='store_true');args=p.parse_args()
    snap=load(args.offline);records,excluded,coverage,audit=cases(snap)
    print('Cases built: '+str(len(records))+'; exclusions: '+str(len(excluded)),flush=True)
    accuracy=scores(records);pairs,updates,contrasts=revisions(records)
    for scenario in ('20HKT_lag4','20HKT_lag8','20HKT_lag12','12HKT_lag6','16HKT_lag6'):
        a,b,c=revisions(records,scenario,False);pairs+=a;updates+=b;contrasts+=c
    for name,rows in [('forecast_cases.csv',records),('excluded_cases.csv',excluded),('coverage.csv',coverage),
                      ('accuracy.csv',accuracy),('revision_pairs.csv',pairs),('revision_summary.csv',updates),('revision_contrasts.csv',contrasts)]:write_csv(name,rows)
    (HERE/'source_queries.sql').write_text('\n\n'.join('-- '+k+'\n'+v+';' for k,v in QUERIES.items()),encoding='utf-8',newline='\n')
    metadata=dict(snapshot_at_utc=snap['snapshot_at_utc'],database_read_only=snap['database_read_only'],database_writes=False,
        target_start=str(START),target_end_exclusive=str(END),primary_scenario=BASE,scenarios=SCENARIOS,
        primary_cases=sum(r['scenario']==BASE for r in records),expected_primary_cases=5110,
        exclusions_by_scenario=dict(Counter(r['scenario'] for r in excluded)),station=snap['station'][0],audit=audit,
        conditional_temporal_envelopes=True,exact_daily_extrema=False,verified_historical_gfs_availability=False,
        bootstrap=dict(replicates=2000,seed=3522,block_days=7,sensitivity_block_days=14,unit='target date, keeping leads and products paired',multiplicity_adjusted=False),
        code_sha256=hashlib.sha256((HERE/'run_analysis.py').read_bytes()+(HERE/'annual_methods.py').read_bytes()).hexdigest(),
        input_cache_sha256=hashlib.sha256(CACHE.read_bytes()).hexdigest(),
        query_sha256=hashlib.sha256((HERE/'source_queries.sql').read_bytes()).hexdigest(),
        evidence_hashes={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in
            ('forecast_cases.csv','excluded_cases.csv','coverage.csv','accuracy.csv','revision_pairs.csv','revision_summary.csv','revision_contrasts.csv')})
    save_json('run_metadata.json',metadata)
    print(json.dumps(dict(primary_cases=metadata['primary_cases'],audit=audit,
        accuracy=[r for r in accuracy if r['scenario']==BASE and r['group']=='lead' and r['value']=='0'],
        updates=[r for r in updates if r['new_lead']==0],update_contrasts=[r for r in contrasts if r['new_lead']==0]),default=encode,indent=2))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(json.dumps(dict(error_type=type(exc).__name__,locations=[(Path(f.filename).name,f.lineno) for f in traceback.extract_tb(exc.__traceback__)])),file=sys.stderr)
        sys.exit(1)
