"""Execute the January comparison using a read-only DB snapshot and local outputs."""
from __future__ import annotations
import argparse
from collections import defaultdict,Counter
import csv
from datetime import date,datetime,time,timedelta,timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import traceback
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'data_management/model_forecasts'))
sys.path.insert(0,str(ROOT/'analyses'))
from manage_gfs import connect
from common.rh_observations import validate_reports
from methods import (START,END,UTC,HKT,COLS,BASE,SCENARIOS,select_hko,select_run,
                     reconstruct,error_bounds,metrics,block_ci,revision_summary)

RESULTS=HERE/'results'
CACHE=HERE/'cache'/'snapshot.json.gz'
QUERY_START=datetime(2024,12,24,tzinfo=UTC)
QUERY_END=datetime(2025,1,31,tzinfo=UTC)
QUERIES={
'station': "SELECT station_code,station_name,latitude,longitude,elevation_m FROM project.hko_station WHERE station_code='HKO'",
'catalog': "SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='project' AND table_name IN ('external_model_source','external_model_temperature','hko_forecast_daily','hko_forecast_issue') ORDER BY table_name,ordinal_position",
'gfs': """SELECT s.source_id,s.run_time_utc,s.forecast_hour,s.subset_sha256,
 s.manifest->'grib_message_metadata' AS grib_metadata,
 s.manifest->>'availability_time_utc' AS availability_time_utc,
 t.message_number,t.short_name,t.step_type,t.interval_start_utc,t.valid_time_utc,t.temperature_c,
 t.grid_latitude,t.grid_longitude,t.grid_distance_km,t.target_latitude,t.target_longitude
 FROM project.external_model_source s JOIN project.external_model_temperature t USING(source_id)
 WHERE s.model='GFS' AND s.product='pgrb2.0p25' AND t.station_code='HKO'
 AND s.run_time_utc >= %(run_start)s AND s.run_time_utc < %(run_end)s
 ORDER BY s.run_time_utc,s.forecast_hour,t.message_number""",
'forecasts': """SELECT f.forecast_issue_id,i.source_file_id,i.bulletin_time_hkt,i.published_time_utc,
 f.valid_date,f.lead_days,f.forecast_tmin_c,f.forecast_tmax_c,f.forecast_rh_min_pct,
 f.forecast_rh_max_pct,f.psr,f.weather,i.general_situation
 FROM project.hko_forecast_daily f JOIN project.hko_forecast_issue i USING(forecast_issue_id)
 WHERE f.valid_date >= %(start)s AND f.valid_date < %(end)s
 AND f.lead_days BETWEEN 1 AND 9
 ORDER BY f.valid_date,i.bulletin_time_hkt,f.forecast_issue_id""",
'observations': """SELECT o.observation_series_id,s.series_code,o.observation_date,
 o.value_numeric,o.value_text,o.data_completeness FROM project.hko_daily_observation o
 JOIN project.hko_observation_series s USING(observation_series_id)
 WHERE o.observation_date >= DATE '2024-12-23' AND o.observation_date < %(end)s
 AND (s.series_code IN ('obs_hko_daily_tmax','obs_hko_daily_tmin','obs_hko_daily_rainfall')
      OR o.observation_series_id=ANY(%(rain_ids)s))
 ORDER BY o.observation_series_id,o.observation_date""",
'rh_reports': """SELECT report_id,report_date,bulletin_date,bulletin_time,
 report_json->>'ReportTimeInfoDate' AS source_observation_date,
 report_json->>'HKOReadingsMinRH' AS observed_rh_min_text,
 report_json->>'HKOReadingsMaxRH' AS observed_rh_max_text,
 report_json->>'NoteDesc3' AS source_quality_note
 FROM project.hko_multistation_report WHERE report_date >= %(start)s AND report_date < %(end)s
 ORDER BY report_date""",
'climate': """WITH h AS (
 SELECT s.series_code,o.value_numeric,
 make_date(2000,EXTRACT(MONTH FROM o.observation_date)::int,EXTRACT(DAY FROM o.observation_date)::int)-DATE '2000-01-01' AS ref
 FROM project.hko_daily_observation o JOIN project.hko_observation_series s USING(observation_series_id)
 WHERE s.series_code IN ('obs_hko_daily_tmax','obs_hko_daily_tmin')
 AND o.observation_date >= DATE '1991-01-01' AND o.observation_date < DATE '2021-01-01'
 AND o.value_numeric IS NOT NULL AND o.data_completeness='C'), d AS (
 SELECT target::date AS valid_date,make_date(2000,1,EXTRACT(DAY FROM target)::int)-DATE '2000-01-01' AS ref
 FROM generate_series(%(start)s::timestamp,%(end)s::timestamp-INTERVAL '1 day',INTERVAL '1 day') target)
 SELECT d.valid_date,h.series_code,avg(h.value_numeric) AS climatology_mean,count(*) AS history_n
 FROM d JOIN h ON LEAST(abs(d.ref-h.ref),366-abs(d.ref-h.ref))<=2
 GROUP BY d.valid_date,h.series_code ORDER BY 1,2""",
}


def encode(value):
    if isinstance(value,datetime):return {'__datetime__':value.isoformat()}
    if isinstance(value,date):return {'__date__':value.isoformat()}
    if isinstance(value,np.generic):return value.item()
    try:return float(value)
    except (TypeError,ValueError):return str(value)


def decode(value):
    if set(value)=={'__datetime__'}:return datetime.fromisoformat(value['__datetime__'])
    if set(value)=={'__date__'}:return date.fromisoformat(value['__date__'])
    return value


def save_json(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,default=encode)+'\n',encoding='utf-8')


def write_csv(name,rows):
    if not rows:return
    with (RESULTS/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})


def load(offline):
    weights=list(csv.DictReader((ROOT/'analyses/01_rainfall/results/psr_area_weights.csv').open(encoding='utf-8')))
    params=dict(start=START,end=END,run_start=QUERY_START,run_end=QUERY_END,
                rain_ids=[int(r['observation_series_id']) for r in weights])
    if offline:
        with gzip.open(CACHE,'rt',encoding='utf-8') as f:snapshot=json.load(f,object_hook=decode)
    else:
        from psycopg.rows import dict_row
        snapshot={}
        with connect() as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            assert conn.execute('SHOW transaction_read_only').fetchone()[0]=='on'
            with conn.cursor(row_factory=dict_row) as cursor:
                for name,sql in QUERIES.items():
                    cursor.execute(sql,params);snapshot[name]=cursor.fetchall()
            snapshot['snapshot_at_utc']=datetime.now(UTC).isoformat()
            snapshot['read_only']=True
        CACHE.parent.mkdir(parents=True,exist_ok=True)
        with gzip.open(CACHE,'wt',encoding='utf-8') as f:json.dump(snapshot,f,default=encode)
    snapshot['weights']=weights
    return snapshot


def prepare(snapshot):
    by_run=defaultdict(list);by_target=defaultdict(list)
    for row in snapshot['gfs']:
        meta=row['grib_metadata'][row['message_number']-1]
        row['packing_step_c']=float(meta['quantization_step_k'])
        by_run[row['run_time_utc']].append(row)
    for row in snapshot['forecasts']:by_target[row['valid_date']].append(row)
    obs={v:{} for v in ('tmax','tmin')}
    for row in snapshot['observations']:
        for v in obs:
            if row['series_code']=='obs_hko_daily_'+v and row['data_completeness']=='C' and row['value_numeric'] is not None:
                if row['observation_date'] in obs[v]:raise ValueError('Duplicate observation date')
                obs[v][row['observation_date']]=float(row['value_numeric'])
    rh,audit=validate_reports(snapshot['rh_reports'],START,END)
    obs.update(rh)
    climate={(r['valid_date'],r['series_code'].removeprefix('obs_hko_daily_')):float(r['climatology_mean'])
             for r in snapshot['climate']}
    # A complete run is required before it can enter latest-available selection.
    for run,rows in by_run.items():
        if len({r['forecast_hour'] for r in rows})!=65 or len(rows)!=193:
            raise ValueError('Incomplete GFS run in analysis window')
    return by_run,by_target,obs,climate,audit


def cases(snapshot):
    by_run,by_target,obs,climate,rh_audit=prepare(snapshot)
    records=[];hko_records=[];exclusions=[];selected=[]
    for scenario,(hour,lag) in SCENARIOS.items():
        for offset in range(31):
            target=START+timedelta(days=offset)
            for lead in range(1,8):
                decision=target-timedelta(days=lead)
                cutoff=datetime.combine(decision,time(hour),HKT).astimezone(UTC)
                hko=select_hko(by_target[target],cutoff)
                run=select_run(by_run,cutoff,lag)
                if hko is None or run is None:
                    exclusions.append(dict(scenario=scenario,valid_date=target,lead_days=lead,reason='no_eligible_vintage'))
                    continue
                common=dict(scenario=scenario,valid_date=target,lead_days=lead,decision_date=decision,
                    cutoff_utc=cutoff,hko_issue_id=hko['forecast_issue_id'],
                    hko_bulletin_hkt=hko['bulletin_time_hkt'],hko_rss_utc=hko['published_time_utc'],
                    hko_age_hours=(cutoff-hko['bulletin_time_hkt'].replace(tzinfo=HKT)).total_seconds()/3600,
                    hko_stale_issue=hko['bulletin_time_hkt'].date()<decision,
                    hko_product_lead=hko['lead_days'],gfs_run_utc=run,gfs_assumed_lag_hours=lag,
                    gfs_age_hours=(cutoff-run).total_seconds()/3600,gfs_availability_verified=False)
                selected.append(common|dict(psr=hko['psr']))
                for variable,column in COLS.items():
                    if hko[column] is None or target not in obs[variable]:
                        exclusions.append(dict(scenario=scenario,valid_date=target,lead_days=lead,reason='missing_'+variable))
                        continue
                    row=common|dict(variable=variable,hko=float(hko[column]),observed=obs[variable][target])
                    if scenario==BASE:hko_records.append(row)
                    if variable.startswith('rh'):continue
                    reconstruction=reconstruct(by_run[run],target,variable)
                    if reconstruction is None:
                        exclusions.append(dict(scenario=scenario,valid_date=target,lead_days=lead,reason='daily_reconstruction_'+variable))
                        continue
                    row.update(reconstruction)
                    row['gfs_error_min'],row['gfs_error_max']=error_bounds(row['gfs_lower'],row['gfs_upper'],row['observed'])
                    row['hko_ae']=abs(row['hko']-row['observed']);row['gfs_ae']=abs(row['gfs']-row['observed'])
                    row['paired_delta_ae']=row['gfs_ae']-row['hko_ae']
                    row['climate']=climate[(target,variable)]
                    row['persistence']=obs[variable].get(decision-timedelta(days=2))
                    records.append(row)
    return records,hko_records,selected,exclusions,rh_audit


def summaries(records):
    scores=[];contrasts=[];baseline=[]
    for scenario in SCENARIOS:
        for variable in ('tmax','tmin'):
            for lead in range(8):
                members=[r for r in records if r['scenario']==scenario and r['variable']==variable
                         and (lead==0 or r['lead_days']==lead)]
                if not members:continue
                group=dict(scenario=scenario,variable=variable,lead_days=lead,n_dates=len({r['valid_date'] for r in members}))
                for product in ('hko','gfs','gfs_sampled'):
                    scores.append(group|dict(product=product)|metrics([r[product] for r in members],[r['observed'] for r in members]))
                low,high=block_ci([r['paired_delta_ae'] for r in members],[r['valid_date'] for r in members])
                low3,high3=block_ci([r['paired_delta_ae'] for r in members],[r['valid_date'] for r in members],block=3)
                contrasts.append(group|dict(n=len(members),delta_mae=float(np.mean([r['paired_delta_ae'] for r in members])),
                    ci7_low=low,ci7_high=high,ci3_low=low3,ci3_high=high3,
                    temporal_delta_lower=float(np.mean([r['gfs_error_min']-r['hko_ae'] for r in members])),
                    temporal_delta_upper=float(np.mean([r['gfs_error_max']-r['hko_ae'] for r in members])),
                    mean_envelope_width=float(np.mean([r['envelope_width'] for r in members]))))
                if scenario==BASE:
                    for reference in ('climate','persistence'):
                        matched=[r for r in members if r[reference] is not None]
                        reference_mae=np.mean([abs(r[reference]-r['observed']) for r in matched])
                        for product in ('hko','gfs'):
                            forecast_mae=np.mean([abs(r[product]-r['observed']) for r in matched])
                            baseline.append(group|dict(product=product,reference=reference,n=len(matched),
                                reference_mae=float(reference_mae),forecast_mae=float(forecast_mae),
                                mae_skill=float(1-forecast_mae/reference_mae) if reference_mae else None))
    return scores,contrasts,baseline


def hko_only(snapshot,rows,selected):
    scores=[]
    for variable in ('rh_min','rh_max'):
        for lead in range(8):
            members=[r for r in rows if r['variable']==variable and (lead==0 or r['lead_days']==lead)]
            scores.append(dict(variable=variable,lead_days=lead,product='hko_only',
                               **metrics([r['hko'] for r in members],[r['observed'] for r in members])))
    weights={int(r['observation_series_id']):float(r['weight']) for r in snapshot['weights']}
    weight_sum=sum(weights.values());weights={k:v/weight_sum for k,v in weights.items()}
    daily=defaultdict(dict);hq={}
    for row in snapshot['observations']:
        if not START<=row['observation_date']<END:continue
        value=None
        if row['data_completeness']=='C':
            if row['value_numeric'] is not None:value=(float(row['value_numeric']),)*2
            elif row['value_text']=='Trace':value=(0.,.05)
        if row['observation_series_id'] in weights:daily[row['observation_date']][row['observation_series_id']]=value
        if row['series_code']=='obs_hko_daily_rainfall':hq[row['observation_date']]=value
    events={};ambiguous=0
    for target,values in daily.items():
        if set(values)!=set(weights) or any(v is None for v in values.values()):continue
        lo=sum(weights[k]*v[0] for k,v in values.items());hi=sum(weights[k]*v[1] for k,v in values.items())
        if lo<10<=hi:ambiguous+=1;continue
        events[target]=int(lo>=10)
    bands={'Low':(0,.30),'Medium Low':(.30,.45),'Medium':(.45,.55),'Medium High':(.55,.70),'High':(.70,1)}
    psr=[]
    for r in selected:
        if r['scenario']!=BASE or r['psr'] not in bands or r['valid_date'] not in events:continue
        lo,hi=bands[r['psr']];event=events[r['valid_date']]
        psr.append(dict(valid_date=r['valid_date'],lead_days=r['lead_days'],category=r['psr'],event=event,
                        midpoint_bs=((lo+hi)/2-event)**2,bs_lower=min((lo-event)**2,(hi-event)**2),
                        bs_upper=max((lo-event)**2,(hi-event)**2)))
    revisions=[]
    trajectories=defaultdict(dict)
    for r in selected:
        if r['scenario']==BASE:trajectories[r['valid_date']][r['lead_days']]=r['psr']
    for target,path in trajectories.items():
        for lead in range(1,7):
            if lead in path and lead+1 in path and path[lead] in bands and path[lead+1] in bands:
                revisions.append(path[lead]!=path[lead+1])
    rain=dict(reference='Task 1 agreed area_weighted_22 >=10mm proxy; not official territorial labels',
              panel_dates=len(events),panel_event_dates=sum(events.values()),trace_ambiguous_dates=ambiguous,
              hq_complete_dates=sum(v is not None for v in hq.values()),
              hq_trace_dates=sum(v is not None and v[0]!=v[1] for v in hq.values()),
              hq_rainfall_lower_mm=sum(v[0] for v in hq.values() if v),
              hq_rainfall_upper_mm=sum(v[1] for v in hq.values() if v),
              hq_point_10mm_event_dates=sum(v[0]>=10 for v in hq.values() if v),
              n_forecasts=len(psr),categories=dict(Counter(r['category'] for r in psr)),
              midpoint_brier=float(np.mean([r['midpoint_bs'] for r in psr])) if psr else None,
              brier_lower=float(np.mean([r['bs_lower'] for r in psr])) if psr else None,
              brier_upper=float(np.mean([r['bs_upper'] for r in psr])) if psr else None,
              revision_pairs=len(revisions),revision_rate_pct=100*np.mean(revisions) if revisions else None)
    return scores,psr,rain


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--offline',action='store_true');args=parser.parse_args()
    RESULTS.mkdir(exist_ok=True)
    snapshot=load(args.offline)
    records,hko_rows,selected,excluded,rh_audit=cases(snapshot)
    scores,contrasts,baselines=summaries(records)
    base=[r for r in records if r['scenario']==BASE]
    revisions=[];pairs=[];ffis=[]
    for product in ('hko','gfs'):
        a,b,c=revision_summary(base,product);revisions+=a;pairs+=b;ffis+=c
    for row in revisions:
        members=[r for r in pairs if r['product']==row['product'] and r['variable']==row['variable']
                 and (row['later_lead']==0 or r['later_lead']==row['later_lead'])]
        row['mean_error_reduction_all_ci7_low'],row['mean_error_reduction_all_ci7_high']=block_ci(
            [r['benefit'] for r in members],[r['valid_date'] for r in members])
    hko_rh=[r for r in hko_rows if r['variable'].startswith('rh')]
    a,b,c=revision_summary(hko_rh,'hko');rh_revisions=a
    rh_scores,psr,rain=hko_only(snapshot,hko_rows,selected)
    for name,data in [('paired_cases.csv',records),('temperature_scores.csv',scores),('paired_contrasts.csv',contrasts),
                      ('baseline_skill.csv',baselines),('revision_summary.csv',revisions),('revision_pairs.csv',pairs),
                      ('flip_flop_by_date.csv',ffis),('hko_rh_scores.csv',rh_scores),('hko_rh_revisions.csv',rh_revisions),
                      ('hko_psr_proxy_cases.csv',psr),('vintage_selection.csv',selected),('excluded_cases.csv',excluded)]:write_csv(name,data)
    metadata=dict(snapshot_at_utc=snapshot['snapshot_at_utc'],database_read_only=snapshot['read_only'],database_writes=False,
        target_dates=[str(START),str(END)],primary_scenario=BASE,scenarios=SCENARIOS,station=snapshot['station'][0],
        gfs_rows_fetched=len(snapshot['gfs']),gfs_runs_fetched=len({r['run_time_utc'] for r in snapshot['gfs']}),
        gfs_available_variables=sorted({r['short_name'] for r in snapshot['gfs']}),
        primary_cases=len(base),expected_primary_cases=31*7*2,exclusions=excluded,
        primary_stale_hko_cases=sum(r['hko_stale_issue'] for r in base),
        inner_coverage_hours=dict(Counter(r['inner_hours'] for r in base)),
        temporal_exact_daily_reconstruction=False,historical_gfs_availability_verified=False,
        grid_positions=list({(r['grid_latitude'],r['grid_longitude'],r['grid_distance_km']) for r in snapshot['gfs']}),
        rh_audit=rh_audit,rainfall=rain,
        input_cache_sha256=hashlib.sha256(CACHE.read_bytes()).hexdigest(),
        rain_weights_sha256=hashlib.sha256((ROOT/'analyses/01_rainfall/results/psr_area_weights.csv').read_bytes()).hexdigest(),
        queries_sha256=hashlib.sha256(json.dumps(QUERIES,sort_keys=True).encode()).hexdigest(),
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()+(HERE/'methods.py').read_bytes()).hexdigest(),
        bootstrap=dict(replicates=2000,seed=3522,primary_calendar_block_days=7,sensitivity_block_days=3,
                       resampling_unit='target date, all leads/products together',multiple_comparison_adjustment=False),
        external_context=dict(monthly_weather='https://www.hko.gov.hk/en/wxinfo/pastwx/mws2025/mws202501.htm',
                              regridding='https://earthsystemmodeling.org/regrid/'))
    save_json(RESULTS/'run_metadata.json',metadata)
    (HERE/'source_queries.sql').write_text('\n\n'.join('-- '+k+'\n'+v+';' for k,v in QUERIES.items()),encoding='utf-8')
    print(json.dumps(dict(primary_cases=len(base),excluded=len(excluded),
                         pooled_contrasts=[r for r in contrasts if r['scenario']==BASE and r['lead_days']==0],
                         revisions=[r for r in revisions if r['later_lead']==0],rainfall=rain),indent=2,default=encode))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('January analysis failed ('+type(exc).__name__+'). Database access was read-only.',file=sys.stderr)
        print(json.dumps([dict(file=Path(f.filename).name,function=f.name,line=f.lineno)
                          for f in traceback.extract_tb(exc.__traceback__)][-5:]),file=sys.stderr)
        raise SystemExit(1)
