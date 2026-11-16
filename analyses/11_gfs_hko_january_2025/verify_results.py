"""Independent checks of case arithmetic, source reconstruction and SQL vintages."""
from collections import defaultdict
from datetime import date,datetime,timedelta,timezone
import csv,gzip,hashlib,json,math
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'data_management/model_forecasts'))
from manage_gfs import connect


def hook(v):
    if list(v)==['__datetime__']:return datetime.fromisoformat(v['__datetime__'])
    if list(v)==['__date__']:return date.fromisoformat(v['__date__'])
    return v


def read(name):return list(csv.DictReader((HERE/'results'/name).open(encoding='utf-8')))


def main():
    checks=[]
    def check(name,value):checks.append(dict(check=name,passed=bool(value)))
    metadata=json.loads((HERE/'results/run_metadata.json').read_text(encoding='utf-8'))
    check('analysis_code_hash',hashlib.sha256((HERE/'run_analysis.py').read_bytes()+
          (HERE/'methods.py').read_bytes()).hexdigest()==metadata['code_sha256'])
    check('rain_weight_hash',hashlib.sha256((ROOT/'analyses/01_rainfall/results/psr_area_weights.csv').read_bytes()).hexdigest()==metadata['rain_weights_sha256'])
    check('source_read_only',metadata['database_read_only'] and not metadata['database_writes'])
    cache=HERE/'cache/snapshot.json.gz'
    check('input_snapshot_hash',hashlib.sha256(cache.read_bytes()).hexdigest()==metadata['input_cache_sha256'])
    with gzip.open(cache,'rt',encoding='utf-8') as f:snapshot=json.load(f,object_hook=hook)
    cases=read('paired_cases.csv');scores=read('temperature_scores.csv');contrasts=read('paired_contrasts.csv')
    selected=read('vintage_selection.csv');pairs=read('revision_pairs.csv');summaries=read('revision_summary.csv')
    check('unique_case_keys',len({(r['scenario'],r['variable'],r['valid_date'],r['lead_days']) for r in cases})==len(cases))
    check('six_scenarios_complete',len(cases)==6*31*7*2)
    grouped=defaultdict(list)
    for r in cases:
        for k in ('hko','gfs','gfs_sampled','observed','gfs_lower','gfs_upper','hko_ae','gfs_ae','paired_delta_ae'):
            r[k]=float(r[k])
        grouped[(r['scenario'],r['variable'],int(r['lead_days']))].append(r)
        grouped[(r['scenario'],r['variable'],0)].append(r)
        check('paired_error:'+r['scenario']+r['variable']+r['valid_date']+r['lead_days'],
              abs((abs(r['gfs']-r['observed'])-abs(r['hko']-r['observed']))-r['paired_delta_ae'])<1e-12)
    for r in scores:
        members=grouped[(r['scenario'],r['variable'],int(r['lead_days']))]
        errors=[m[r['product']]-m['observed'] for m in members]
        check('score:'+str((r['scenario'],r['variable'],r['lead_days'],r['product'])),
              int(r['n'])==len(members) and abs(sum(abs(e) for e in errors)/len(errors)-float(r['mae']))<1e-12
              and abs(math.sqrt(sum(e*e for e in errors)/len(errors))-float(r['rmse']))<1e-12
              and abs(sum(errors)/len(errors)-float(r['bias']))<1e-12)
    for r in contrasts:
        members=grouped[(r['scenario'],r['variable'],int(r['lead_days']))]
        check('delta_identity:'+str((r['scenario'],r['variable'],r['lead_days'])),
              abs(sum(m['paired_delta_ae'] for m in members)/len(members)-float(r['delta_mae']))<1e-12)
    # Independent day-cell coverage and extrema calculations from the snapshot.
    by_run=defaultdict(list)
    for r in snapshot['gfs']:by_run[r['run_time_utc']].append(r)
    for case in cases:
        run=datetime.fromisoformat(case['gfs_run_utc']);target=date.fromisoformat(case['valid_date'])
        start=datetime.combine(target,datetime.min.time(),timezone(timedelta(hours=8))).astimezone(timezone.utc)
        end=start+timedelta(days=1)
        rows=[r for r in by_run[run] if r['short_name']==case['variable']]
        outer=[r for r in rows if r['interval_start_utc']<end and r['valid_time_utc']>start]
        inner=[r for r in outer if r['interval_start_utc']>=start and r['valid_time_utc']<=end]
        def coverage(members):
            return sum(any(r['interval_start_utc']<=start+timedelta(hours=h)
                           and r['valid_time_utc']>=start+timedelta(hours=h+1) for r in members) for h in range(24))
        def padding(r):return max(.02,float(r['grib_metadata'][r['message_number']-1]['quantization_step_k']))
        if case['variable']=='tmax':
            lower=max(r['temperature_c']-padding(r) for r in inner)
            upper=max(r['temperature_c']+padding(r) for r in outer)
        else:
            lower=min(r['temperature_c']-padding(r) for r in outer)
            upper=min(r['temperature_c']+padding(r) for r in inner)
        check('reconstruction:'+case['scenario']+case['variable']+case['valid_date']+case['lead_days'],
              coverage(outer)==24 and coverage(inner)==float(case['inner_hours'])
              and abs(lower-case['gfs_lower'])<1e-12 and abs(upper-case['gfs_upper'])<1e-12
              and abs((lower+upper)/2-case['gfs'])<1e-12)
    # All base revisions must connect the same target to adjacent decision days.
    lookup={(r['variable'],r['valid_date'],int(r['lead_days'])):r for r in cases if r['scenario']=='20HKT_lag6'}
    for r in pairs:
        lead=int(r['later_lead']);new=lookup[(r['variable'],r['valid_date'],lead)]
        old=lookup[(r['variable'],r['valid_date'],lead+1)];product=r['product']
        benefit=abs(old[product]-new['observed'])-abs(new[product]-new['observed'])
        check('revision:'+product+r['variable']+r['valid_date']+r['later_lead'],
              abs(benefit-float(r['benefit']))<1e-12
              and abs(new[product]-old[product]-float(r['delta']))<1e-12
              and (date.fromisoformat(new['decision_date'])-date.fromisoformat(old['decision_date'])).days==1)
    for r in summaries:
        members=[p for p in pairs if p['product']==r['product'] and p['variable']==r['variable']
                 and (r['later_lead']=='0' or p['later_lead']==r['later_lead'])]
        changed=[p for p in members if abs(float(p['delta']))>1e-10]
        material=[p for p in members if abs(float(p['delta']))>=1-1e-10]
        check('revision_summary:'+r['product']+r['variable']+r['later_lead'],
              len(members)==int(r['n_pairs']) and len(changed)==int(r['n_changed'])
              and abs(100*len(material)/len(members)-float(r['material_revision_rate_pct']))<1e-12)
    # Rebuild the primary paired interval from daily means with an independent loop.
    for variable in ('tmax','tmin'):
        daily=defaultdict(list)
        for r in grouped[('20HKT_lag6',variable,0)]:daily[r['valid_date']].append(r['paired_delta_ae'])
        vals=np.array([sum(v)/len(v) for _,v in sorted(daily.items())])
        rng=np.random.default_rng(3522);means=[]
        for starts in rng.integers(0,31,size=(2000,5)):
            draw=[(int(first)+offset)%31 for first in starts for offset in range(7)][:31]
            means.append(float(vals[draw].mean()))
        lo,hi=np.quantile(means,[.025,.975])
        saved=next(r for r in contrasts if r['scenario']=='20HKT_lag6' and r['variable']==variable and r['lead_days']=='0')
        check('primary_ci_independent_loop:'+variable,abs(lo-float(saved['ci7_low']))<1e-12 and abs(hi-float(saved['ci7_high']))<1e-12)
    # Check native instantaneous values against same-ending interval extrema,
    # with each field's disclosed padding. These are consistency diagnostics.
    by_source=defaultdict(dict)
    for r in snapshot['gfs']:by_source[str(r['source_id'])][r['step_type']]=r
    crossfield_warnings=0
    for rows in by_source.values():
        if set(rows)=={'instant','max','min'}:
            val=rows['instant']['temperature_c']
            pad=lambda r:max(.02,float(r['grib_metadata'][r['message_number']-1]['quantization_step_k']))
            crossfield_warnings+=val>rows['max']['temperature_c']+pad(rows['instant'])+pad(rows['max']) or val<rows['min']['temperature_c']-pad(rows['instant'])-pad(rows['min'])
    from psycopg.types.json import Jsonb
    request=[dict(valid_date=r['valid_date'],cutoff=r['cutoff_utc'],lag=int(r['gfs_assumed_lag_hours']),
                  hko_id=int(r['hko_issue_id']),gfs_run=r['gfs_run_utc']) for r in selected]
    with connect() as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        mismatches=conn.execute("""
            WITH requested AS (SELECT * FROM jsonb_to_recordset(%s) AS r(
                valid_date date,cutoff timestamptz,lag integer,hko_id bigint,gfs_run timestamptz))
            SELECT count(*) FROM requested r
            LEFT JOIN LATERAL (
                SELECT i.forecast_issue_id FROM project.hko_forecast_issue i
                JOIN project.hko_forecast_daily f USING(forecast_issue_id)
                WHERE f.valid_date=r.valid_date AND f.lead_days BETWEEN 1 AND 9
                  AND i.bulletin_time_hkt AT TIME ZONE 'Asia/Hong_Kong' <= r.cutoff
                  AND i.published_time_utc<=r.cutoff
                ORDER BY i.bulletin_time_hkt DESC,i.forecast_issue_id DESC LIMIT 1
            ) h ON true
            LEFT JOIN LATERAL (
                SELECT max(s.run_time_utc) AS run FROM project.external_model_source s
                WHERE s.model='GFS' AND s.product='pgrb2.0p25'
                  AND s.run_time_utc >= TIMESTAMPTZ '2024-12-24 00:00:00+00'
                  AND s.run_time_utc < TIMESTAMPTZ '2025-01-31 00:00:00+00'
                  AND s.run_time_utc+r.lag*INTERVAL '1 hour'<=r.cutoff
            ) g ON true
            WHERE h.forecast_issue_id IS DISTINCT FROM r.hko_id OR g.run IS DISTINCT FROM r.gfs_run
        """,(Jsonb(request),)).fetchone()[0]
        check('independent_sql_all_vintage_selections',mismatches==0)
    receipt=dict(passed=all(r['passed'] for r in checks),checks=len(checks),
                 failed_checks=[r for r in checks if not r['passed']],
                 selection_rows_verified_live_sql=len(request),selection_mismatches=mismatches,
                 reconstructed_cases_checked=len(cases),native_crossfield_warnings_after_padding=crossfield_warnings,
                 database_writes=False,
                 limits='Checks arithmetic, reconstruction, full selection and primary CI; not historical availability, official spatial targeting or causal explanations.')
    (HERE/'results/verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2));return 0 if receipt['passed'] else 1


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        import traceback
        print(json.dumps({'error_type':type(exc).__name__,'locations':[(Path(f.filename).name,f.lineno) for f in traceback.extract_tb(exc.__traceback__)]}));sys.exit(1)
