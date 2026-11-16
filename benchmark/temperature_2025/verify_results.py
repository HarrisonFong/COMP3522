"""Independent arithmetic, bootstrap and optional live-source verification.

--offline needs only committed CSV/JSON files. Live mode also checks all HKO/GFS
vintage selections and the local read-only source snapshot's reconstructions.
"""
from collections import defaultdict,Counter
import argparse,csv,gzip,hashlib,json,math,sys,traceback
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
BASE='20HKT_lag6';UTC=timezone.utc;HKT=timezone(timedelta(hours=8))


def read(name):
    with (HERE/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def close(a,b):return abs(float(a)-float(b))<1e-10


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--offline',action='store_true');args=p.parse_args()
    checks=[]
    def check(name,ok):checks.append(dict(check=name,passed=bool(ok)))
    meta=json.loads((HERE/'run_metadata.json').read_text(encoding='utf-8'))
    check('read_only_contract',meta['database_read_only'] and not meta['database_writes'])
    for name,digest in meta['evidence_hashes'].items():check('hash:'+name,hashlib.sha256((HERE/name).read_bytes()).hexdigest()==digest)
    check('code_hash',hashlib.sha256((HERE/'run_analysis.py').read_bytes()+(HERE/'annual_methods.py').read_bytes()).hexdigest()==meta['code_sha256'])
    check('query_hash',hashlib.sha256((HERE/'source_queries.sql').read_bytes()).hexdigest()==meta['query_sha256'])
    cases=read('forecast_cases.csv');scores=read('accuracy.csv');pairs=read('revision_pairs.csv')
    summaries=read('revision_summary.csv');contrasts=read('revision_contrasts.csv');excluded=read('excluded_cases.csv')
    check('unique_cases',len({(r['scenario'],r['variable'],r['valid_date'],r['lead_days']) for r in cases})==len(cases))
    check('primary_complete',sum(r['scenario']==BASE for r in cases)==5110)
    check('horizon_exclusions',len(excluded)==730 and all(r['scenario']=='02HKT_lag6' and r['lead_days']=='7' for r in excluded))
    check('full_observations_and_runs',meta['audit']['gfs_rows']==287956 and meta['audit']['complete_gfs_runs']==1492
          and all(meta['audit']['observations'][v+'_valid']==365 for v in ('tmax','tmin')))
    lookup={};groups=defaultdict(list)
    for r in cases:
        for k in ('hko','gfs','gfs_lower','gfs_upper','gfs_sampled','observed','paired_delta_ae','gfs_error_lower','gfs_error_upper'):r[k]=float(r[k])
        lookup[(r['variable'],r['valid_date'],r['cutoff_utc'],r['assumed_lag_hours'])]=r
        groups[(r['scenario'],r['variable'],'lead','0')].append(r)
        groups[(r['scenario'],r['variable'],'lead',r['lead_days'])].append(r)
        target=date.fromisoformat(r['valid_date'])
        if r['scenario']==BASE:
            season=('DJF','MAM','JJA','SON')[(target.month%12)//3]
            groups[(BASE,r['variable'],'season',season)].append(r)
            if r['lead_days']=='1':groups[(BASE,r['variable'],'month_D1',str(target.month))].append(r)
        low=max(r['gfs_lower']-r['observed'],r['observed']-r['gfs_upper'],0.)
        high=max(abs(r['gfs_lower']-r['observed']),abs(r['gfs_upper']-r['observed']))
        check('case:'+str(len(checks)),close((r['gfs_lower']+r['gfs_upper'])/2,r['gfs'])
              and close(abs(r['gfs']-r['observed'])-abs(r['hko']-r['observed']),r['paired_delta_ae'])
              and close(low,r['gfs_error_lower']) and close(high,r['gfs_error_upper'])
              and datetime.fromisoformat(r['cutoff_utc']).astimezone(HKT).date()<target)
    for s in scores:
        rows=groups[(s['scenario'],s['variable'],s['group'],s['value'])]
        check('score_denominator:'+str(len(checks)),len(rows)==int(s['n']) and len({r['valid_date'] for r in rows})==int(s['n_dates']))
        for product in ('hko','gfs','gfs_sampled'):
            errors=[r[product]-r['observed'] for r in rows];n=len(errors)
            check('score:'+str(len(checks)),close(sum(map(abs,errors))/n,s[product+'_mae'])
                and close(math.sqrt(sum(e*e for e in errors)/n),s[product+'_rmse']) and close(sum(errors)/n,s[product+'_bias']))
        check('bounds:'+str(len(checks)),close(sum(r['gfs_error_lower'] for r in rows)/len(rows),s['gfs_mae_lower'])
              and close(sum(r['gfs_error_upper'] for r in rows)/len(rows),s['gfs_mae_upper']))
    pairgroups=defaultdict(list)
    for r in pairs:
        lag=str(meta['scenarios'][r['scenario']][1])
        old=lookup[(r['variable'],r['valid_date'],r['old_cutoff_utc'],lag)]
        new=lookup[(r['variable'],r['valid_date'],r['new_cutoff_utc'],lag)]
        ok=(datetime.fromisoformat(r['new_cutoff_utc'])-datetime.fromisoformat(r['old_cutoff_utc'])).total_seconds()==int(r['cadence_hours'])*3600
        for product in ('hko','gfs'):
            benefit=abs(old[product]-new['observed'])-abs(new[product]-new['observed'])
            ok=ok and close(benefit,r[product+'_benefit']) and close(new[product]-old[product],r[product+'_delta'])
        ok=ok and close(float(r['gfs_benefit'])-float(r['hko_benefit']),r['paired_benefit_delta'])
        check('revision:'+str(len(checks)),ok)
        key=(r['scenario'],r['cadence_hours'],r['variable'])
        pairgroups[(*key,'0')].append(r);pairgroups[(*key,r['new_lead'])].append(r)
    for s in summaries:
        rows=pairgroups[(s['scenario'],s['cadence_hours'],s['variable'],s['new_lead'])];p=s['product'];n=len(rows)
        changed=[r for r in rows if abs(float(r[p+'_delta']))>1e-10]
        material=[r for r in rows if abs(float(r[p+'_delta']))>=1-1e-10]
        check('revision_summary:'+str(len(checks)),n==int(s['n_pairs']) and len(changed)==int(s['n_changed'])
            and len(material)==int(s['n_material']) and close(100*len(changed)/n,s['revision_rate_pct'])
            and close(sum(float(r[p+'_benefit']) for r in rows)/n,s['mean_error_reduction'])
            and close(sum(abs(float(r[p+'_delta'])) for r in rows)/n,s['mean_absolute_change'])
            and close(sum(float(s[k]) for k in ('improved_all_pct','worsened_all_pct','tied_all_pct')),100))
    for c in contrasts:
        rows=pairgroups[(c['scenario'],c['cadence_hours'],c['variable'],c['new_lead'])]
        bydate=defaultdict(list)
        for r in rows:bydate[r['valid_date']].append(r)
        gains=[];lower=upper=0.
        for trajectory in bydate.values():
            trajectory.sort(key=lambda r:r['old_cutoff_utc'])
            for product in ('hko','gfs'):
                if c['new_lead']=='0':
                    first,last=trajectory[0],trajectory[-1]
                    endpoint=abs(float(first['old_'+product])-float(first['observed']))-abs(float(last['new_'+product])-float(last['observed']))
                    check('telescoping:'+str(len(checks)),close(endpoint,sum(float(r[product+'_benefit']) for r in trajectory)))
            if c['new_lead']=='0':
                lag=str(meta['scenarios'][c['scenario']][1])
                old=lookup[(c['variable'],trajectory[0]['valid_date'],trajectory[0]['old_cutoff_utc'],lag)]
                new=lookup[(c['variable'],trajectory[-1]['valid_date'],trajectory[-1]['new_cutoff_utc'],lag)]
                lower+=old['gfs_error_lower']-new['gfs_error_upper'];upper+=old['gfs_error_upper']-new['gfs_error_lower']
            gains.extend(float(r['paired_benefit_delta']) for r in trajectory)
        check('paired_benefit:'+str(len(checks)),close(sum(gains)/len(gains),c['gfs_minus_hko_benefit']))
        if c['new_lead']=='0':check('chain_bounds:'+str(len(checks)),close(lower/len(rows),c['gfs_chain_benefit_lower']) and close(upper/len(rows),c['gfs_chain_benefit_upper']))
    # Independent calendar bootstrap using one explicit loop per resample;
    # preserves all seven accuracy leads / six or 26 revision opportunities.
    for variable in ('tmax','tmin'):
        targets=[(r,'accuracy') for r in scores if r['scenario']==BASE and r['variable']==variable and r['group']=='lead' and r['value']=='0']
        targets += [(r,'revision') for r in contrasts if r['scenario']==BASE and r['variable']==variable and r['new_lead']=='0']
        for r,kind in targets:
            data=groups[(BASE,variable,'lead','0')] if kind=='accuracy' else pairgroups[(BASE,r['cadence_hours'],variable,'0')]
            values=defaultdict(list)
            key='paired_delta_ae' if kind=='accuracy' else 'paired_benefit_delta'
            for d in data:values[d['valid_date']].append(float(d[key]))
            daily=[sum(values[(date(2025,1,1)+timedelta(days=i)).isoformat()])/len(values[(date(2025,1,1)+timedelta(days=i)).isoformat()]) for i in range(365)]
            for block in (7,14):
                rng=np.random.default_rng(3522);estimates=[]
                for starts in rng.integers(0,365,size=(2000,math.ceil(365/block))):
                    draw=[(int(a)+b)%365 for a in starts for b in range(block)][:365]
                    estimates.append(sum(daily[i] for i in draw)/365)
                lo,hi=np.quantile(estimates,[.025,.975])
                check('bootstrap:'+kind+variable+str(r.get('cadence_hours',''))+str(block),close(lo,r[f'ci{block}_low']) and close(hi,r[f'ci{block}_high']))
    source_checks={};selection_count=0
    if not args.offline:
        sys.path.insert(0,str(ROOT/'data_management/model_forecasts'))
        from manage_gfs import connect
        from psycopg.types.json import Jsonb
        requests={}
        for r in cases:
            key=(r['valid_date'],r['cutoff_utc'],r['assumed_lag_hours'])
            requests[key]=dict(target=r['valid_date'],cutoff=r['cutoff_utc'],lag=int(r['assumed_lag_hours']),hko_id=int(r['hko_issue_id']),run=r['gfs_run_utc'])
        with connect() as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            mismatches=conn.execute("""WITH requested AS (
                SELECT * FROM jsonb_to_recordset(%s) AS r(target date,cutoff timestamptz,lag int,hko_id bigint,run timestamptz)
            ), runs AS MATERIALIZED (
                SELECT DISTINCT s.run_time_utc FROM project.external_model_source s
                JOIN project.external_model_temperature t USING(source_id)
                WHERE s.model='GFS' AND s.product='pgrb2.0p25' AND t.station_code='HKO'
                AND s.run_time_utc>=TIMESTAMPTZ '2024-12-24 00:00:00+00'
                AND s.run_time_utc<TIMESTAMPTZ '2026-01-01 00:00:00+00')
            SELECT count(*) FROM requested r LEFT JOIN LATERAL (
                SELECT i.forecast_issue_id FROM project.hko_forecast_issue i
                JOIN project.hko_forecast_daily f USING(forecast_issue_id)
                WHERE f.valid_date=r.target AND f.lead_days BETWEEN 1 AND 9
                AND i.bulletin_time_hkt AT TIME ZONE 'Asia/Hong_Kong'<=r.cutoff AND i.published_time_utc<=r.cutoff
                ORDER BY i.bulletin_time_hkt DESC,i.forecast_issue_id DESC LIMIT 1) h ON true
            LEFT JOIN LATERAL (SELECT max(run_time_utc) AS run FROM runs
                WHERE run_time_utc+r.lag*INTERVAL '1 hour'<=r.cutoff) g ON true
            WHERE h.forecast_issue_id IS DISTINCT FROM r.hko_id OR g.run IS DISTINCT FROM r.run
            """,(Jsonb(list(requests.values())),)).fetchone()[0]
            check('all_live_vintage_selections',mismatches==0);selection_count=len(requests)
            truths={(s,d.isoformat()):float(v) for s,d,v in conn.execute("""SELECT s.series_code,o.observation_date,o.value_numeric
                FROM project.hko_observation_series s JOIN project.hko_daily_observation o USING(observation_series_id)
                WHERE s.series_code IN ('obs_hko_daily_tmax','obs_hko_daily_tmin') AND o.observation_date>=DATE '2025-01-01'
                AND o.observation_date<DATE '2026-01-01' AND o.data_completeness='C' AND o.value_numeric IS NOT NULL""")}
            check('all_live_truth_values',all(close(r['observed'],truths[('obs_hko_daily_'+r['variable'],r['valid_date'])]) for r in cases))
        cache=HERE/'cache/snapshot.json.gz'
        check('snapshot_hash',hashlib.sha256(cache.read_bytes()).hexdigest()==meta['input_cache_sha256'])
        def hook(v):
            if set(v)=={'__datetime__'}:return datetime.fromisoformat(v['__datetime__'])
            if set(v)=={'__date__'}:return date.fromisoformat(v['__date__'])
            return v
        with gzip.open(cache,'rt',encoding='utf-8') as f:snapshot=json.load(f,object_hook=hook)
        runs=defaultdict(list);hko={}
        for r in snapshot['gfs']:runs[r['run_time_utc']].append(r)
        for r in snapshot['forecasts']:hko[(r['forecast_issue_id'],r['valid_date'].isoformat())]=r
        native_warnings=[]
        for run,rows in runs.items():
            samples=[r for r in rows if r['short_name']=='2t']
            for r in rows:
                if r['short_name']=='2t':continue
                contained=[p for p in samples if r['interval_start_utc']<=p['valid_time_utc']<=r['valid_time_utc']]
                for point in contained:
                    difference=(point['temperature_c']-r['temperature_c']) if r['short_name']=='tmax' else (r['temperature_c']-point['temperature_c'])
                    excess=difference-max(.02,r['packing_step_c'])-max(.02,point['packing_step_c'])
                    if excess>1e-10:native_warnings.append(dict(run_utc=run.astimezone(UTC).isoformat(),
                        variable=r['short_name'],forecast_hour=r['forecast_hour'],raw_difference_c=difference,
                        excess_after_padding_c=excess,at_start=point['valid_time_utc']==r['interval_start_utc'],
                        at_end=point['valid_time_utc']==r['valid_time_utc']))
        quality=dict(comparison='Instantaneous readings versus extrema on a closed interval, tolerance 1e-10 C after both paddings',
                     warnings=len(native_warnings),at_start=sum(r['at_start'] for r in native_warnings),
                     at_end=sum(r['at_end'] for r in native_warnings),
                     interior=sum(not r['at_start'] and not r['at_end'] for r in native_warnings),
                     max_excess_after_padding_c=max((r['excess_after_padding_c'] for r in native_warnings),default=0.),
                     examples=sorted(native_warnings,key=lambda r:-r['excess_after_padding_c'])[:8],
                     interpretation='All observed warnings are evaluated by position. Boundary convention remains unverified; envelopes remain conditional on compatible interval meanings, not certified continuous-path bounds.')
        (HERE/'native_consistency.json').write_text(json.dumps(quality,indent=2)+'\n',encoding='utf-8',newline='\n')
        for case in cases:
            rows=runs[datetime.fromisoformat(case['gfs_run_utc'])];target=date.fromisoformat(case['valid_date'])
            start=datetime.combine(target,datetime.min.time(),HKT).astimezone(UTC);end=start+timedelta(days=1)
            outer=[r for r in rows if r['short_name']==case['variable'] and r['interval_start_utc']<end and r['valid_time_utc']>start]
            inner=[r for r in outer if start<=r['interval_start_utc'] and r['valid_time_utc']<=end]
            padded=lambda r,sign:r['temperature_c']+sign*max(.02,r['packing_step_c'])
            low=max(padded(r,-1) for r in inner) if case['variable']=='tmax' else min(padded(r,-1) for r in outer)
            high=max(padded(r,1) for r in outer) if case['variable']=='tmax' else min(padded(r,1) for r in inner)
            coverage=sum(any(r['interval_start_utc']<=start+timedelta(hours=h) and r['valid_time_utc']>=start+timedelta(hours=h+1) for r in outer) for h in range(24))
            original=hko[(int(case['hko_issue_id']),case['valid_date'])]
            check('source_case:'+str(len(checks)),coverage==24 and close(low,case['gfs_lower']) and close(high,case['gfs_upper'])
                and close(original['forecast_'+case['variable']+'_c'],case['hko']))
        source_checks=dict(reconstructed_cases=len(cases),live_vintage_mismatches=mismatches,native_instant_vs_interval_warnings=len(native_warnings),
                           warnings_at_start=quality['at_start'],warnings_at_end=quality['at_end'],warnings_interior=quality['interior'])
    receipt=dict(passed=all(c['passed'] for c in checks),checks=len(checks),failed_checks=[c for c in checks if not c['passed']],
                 offline=args.offline,live_selections_checked=selection_count,source_checks=source_checks,database_writes=False,
                 limits='Arithmetic, primary CIs and chain identities verified. Live mode checks selections/truth and cached source reconstructions. Not a new NOAA-byte audit, proof of historical availability, or certification of packing margins.')
    name='reproduction_validation.json' if args.offline else 'validation.json'
    (HERE/name).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(receipt,indent=2))
    return 0 if receipt['passed'] else 1


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        print(json.dumps(dict(error_type=type(exc).__name__,locations=[(Path(f.filename).name,f.lineno) for f in traceback.extract_tb(exc.__traceback__)])));sys.exit(1)
