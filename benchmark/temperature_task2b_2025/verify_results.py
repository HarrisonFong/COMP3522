"""Independent frozen-evidence audit; optional live SQL and original NOAA controls."""
from collections import defaultdict
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import argparse,csv,hashlib,json,math,sys,traceback
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
UTC=timezone.utc;HKT=timezone(timedelta(hours=8))


def read(name):
    with (HERE/name).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))


def equal(a,b):return abs(float(a)-float(b))<1e-9


def bootstrap(values,block):
    # Independent per-resample loop, all 365 target-day means kept paired.
    rng=np.random.default_rng(3522);estimates=[]
    for starts in rng.integers(0,365,size=(2000,math.ceil(365/block))):
        indices=[(int(start)+j)%365 for start in starts for j in range(block)][:365]
        estimates.append(sum(values[i] for i in indices)/365)
    return np.quantile(estimates,[.025,.975])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--live',action='store_true');parser.add_argument('--online-controls',action='store_true');args=parser.parse_args()
    checks=[]
    def check(label,value):checks.append(dict(check=label,passed=bool(value)))
    meta=json.loads((HERE/'run_metadata.json').read_text())
    cases=read('cases.csv');sources=read('source_points.csv');scores=read('scores.csv');contrasts=read('spatial_contrasts.csv')
    pairs=read('revision_pairs.csv');summaries=read('revision_summary.csv');revision_contrasts=read('revision_contrasts.csv')
    check('database_read_only',meta['database_read_only'] and not meta['database_writes'])
    check('complete_schedule',meta['gfs_runs']==371 and meta['gfs_sources']==21518 and len(sources)==21518 and not meta['missing_runs'])
    check('all_primary_cases',len(cases)==5110 and len({(r['variable'],r['valid_date'],r['lead_days']) for r in cases})==5110)
    check('honest_claim_gates',not meta['full_year_unqualified_superiority_claim_allowed'] and not meta['exact_native_daily_extrema'] and meta['verified_common_operational_cases']==0)
    for file,digest in meta['output_hashes'].items():check('hash:'+file,hashlib.sha256((HERE/file).read_bytes()).hexdigest()==digest)
    check('code_hash',hashlib.sha256((HERE/'run_analysis.py').read_bytes()+(HERE/'methods.py').read_bytes()).hexdigest()==meta['code_sha256'])
    x=(114.17416667-114)/.25;y=(22.30194444-22.25)/.25
    def interpolate(c):return (1-y)*((1-x)*c[0]+x*c[1])+y*((1-x)*c[2]+x*c[3])
    raw=defaultdict(dict)
    native=defaultdict(list)
    for r in read('native_interval_inputs.csv'):native[(datetime.fromisoformat(r['run_time_utc']),r['short_name'])].append(r)
    for r in sources:
        h=int(r['forecast_hour']);run=datetime.fromisoformat(r['run_time_utc'])
        vals=[float(r['cell_'+corner+'_c']) for corner in ('sw','se','nw','ne')]
        raw[r['run_time_utc']][h]=vals
        check('source:'+str(len(checks)),run.hour==0 and datetime.fromisoformat(r['valid_time_utc'])==run+timedelta(hours=h)
            and r['measurement_height_m']=='2' and r['native_unit']=='K' and all(math.isfinite(v) for v in vals)
            and len(r['subset_sha256'])==64 and int(r['subset_bytes'])==int(r['byte_end'])-int(r['byte_start'])+1)
    groups=defaultdict(list);lookup={}
    for r in cases:
        for key in ('observed','hko','nearest','bilinear','nearest_sampled','bilinear_sampled'):r[key]=float(r[key])
        target=date.fromisoformat(r['valid_date']);lead=int(r['lead_days']);run=datetime.fromisoformat(r['gfs_run_utc'])
        left=datetime.combine(target,datetime.min.time(),HKT).astimezone(UTC);right=left+timedelta(days=1)
        a=(left-run).total_seconds()/3600;b=(right-run).total_seconds()/3600
        times=sorted(raw[r['gfs_run_utc']]);knots=[a]+[h for h in times if a<h<b]+[b]
        def at(h):
            if h in raw[r['gfs_run_utc']]:return raw[r['gfs_run_utc']][h]
            before=max(t for t in times if t<h);after=min(t for t in times if t>h)
            w=(h-before)/(after-before)
            return [u*(1-w)+v*w for u,v in zip(raw[r['gfs_run_utc']][before],raw[r['gfs_run_utc']][after])]
        cells=[at(h) for h in knots];near=[c[1] for c in cells];bili=[interpolate(c) for c in cells]
        extreme=max if r['variable']=='tmax' else min
        cutoff=datetime.fromisoformat(r['cutoff_utc'])
        check('aligned_case:'+str(len(checks)),left.isoformat()==r['valid_start_utc'] and right.isoformat()==r['valid_end_exclusive_utc']
            and float(r['window_hours'])==24 and cutoff.astimezone(HKT).hour==14
            and run.date()==target-timedelta(days=lead) and run.hour==0
            and datetime.fromisoformat(r['hko_bulletin_hkt']).replace(tzinfo=HKT)<=cutoff
            and datetime.fromisoformat(r['hko_published_utc'])<=cutoff
            and equal(extreme(near),r['nearest']) and equal(extreme(bili),r['bilinear'])
            and int(r['native_in_day_count'])==8 and r['exact_native_daily_extremum']=='False')
        intersect=[n for n in native[(run,r['variable'])] if datetime.fromisoformat(n['interval_start_utc'])<right and datetime.fromisoformat(n['valid_time_utc'])>left]
        contained=[n for n in intersect if datetime.fromisoformat(n['interval_start_utc'])>=left and datetime.fromisoformat(n['valid_time_utc'])<=right]
        def padded(n,sign):return float(n['temperature_c'])+sign*max(.02,float(n['packing_step_c']))
        low=max(padded(n,-1) for n in contained) if r['variable']=='tmax' else min(padded(n,-1) for n in intersect)
        high=max(padded(n,1) for n in intersect) if r['variable']=='tmax' else min(padded(n,1) for n in contained)
        check('native_temporal_diagnostic:'+str(len(checks)),equal(low,r['nearest_native_conditional_lower']) and equal(high,r['nearest_native_conditional_upper']))
        def hours_covered(intervals):
            return sum(any(datetime.fromisoformat(q['interval_start_utc'])<=left+timedelta(hours=h)
                and datetime.fromisoformat(q['valid_time_utc'])>=left+timedelta(hours=h+1) for q in intervals) for h in range(24))
        check('native_coverage:'+str(len(checks)),hours_covered(contained)==21 and hours_covered(intersect)==24)
        for name,a_product,b_product in [('nearest_minus_hko_ae','nearest','hko'),('bilinear_minus_hko_ae','bilinear','hko'),('bilinear_minus_nearest_ae','bilinear','nearest')]:
            check('error:'+str(len(checks)),equal(abs(r[a_product]-r['observed'])-abs(r[b_product]-r['observed']),r[name]))
        groups[(r['variable'],'0')].append(r);groups[(r['variable'],r['lead_days'])].append(r)
        lookup[(r['variable'],r['valid_date'],r['lead_days'])]=r
    for s in scores:
        rows=groups[(s['variable'],s['lead_days'])];errors=[r[s['product']]-r['observed'] for r in rows];n=len(rows)
        check('score:'+str(len(checks)),n==int(s['n']) and equal(sum(map(abs,errors))/n,s['mae']) and equal(math.sqrt(sum(e*e for e in errors)/n),s['rmse']) and equal(sum(errors)/n,s['bias']))
    for c in contrasts:
        rows=groups[(c['variable'],c['lead_days'])]
        check('contrast:'+str(len(checks)),equal(sum(float(r[c['contrast']]) for r in rows)/len(rows),c['delta_mae']))
    pairgroups=defaultdict(list)
    for r in pairs:
        old=lookup[(r['variable'],r['valid_date'],r['old_lead'])];new=lookup[(r['variable'],r['valid_date'],r['new_lead'])]
        check('revision_time:'+str(len(checks)),(datetime.fromisoformat(r['new_cutoff_utc'])-datetime.fromisoformat(r['old_cutoff_utc'])).total_seconds()==86400)
        for product in ('hko','nearest','bilinear'):
            gain=abs(old[product]-new['observed'])-abs(new[product]-new['observed'])
            check('revision:'+str(len(checks)),equal(gain,r[product+'_gain']) and equal(new[product]-old[product],r[product+'_delta']))
        pairgroups[(r['variable'],'0')].append(r);pairgroups[(r['variable'],r['new_lead'])].append(r)
    for s in summaries:
        rows=pairgroups[(s['variable'],s['new_lead'])];p=s['product'];n=len(rows)
        changed=[r for r in rows if abs(float(r[p+'_delta']))>1e-10]
        material=[r for r in rows if abs(float(r[p+'_delta']))>=1-1e-10]
        check('revision_summary:'+str(len(checks)),n==int(s['n_pairs']) and len(changed)==int(s['n_changed']) and len(material)==int(s['n_material'])
              and equal(sum(float(r[p+'_gain']) for r in rows)/n,s['mean_revision_gain_c']))
    for variable in ('tmax','tmin'):
        for product in ('hko','nearest','bilinear'):
            rows=pairgroups[(variable,'0')]
            gains=sum(float(r[product+'_gain']) for r in rows)
            endpoint=sum(abs(lookup[(variable,(date(2025,1,1)+timedelta(days=i)).isoformat(),'7')][product]-lookup[(variable,(date(2025,1,1)+timedelta(days=i)).isoformat(),'7')]['observed'])
                -abs(lookup[(variable,(date(2025,1,1)+timedelta(days=i)).isoformat(),'1')][product]-lookup[(variable,(date(2025,1,1)+timedelta(days=i)).isoformat(),'1')]['observed']) for i in range(365))
            check('telescoping:'+variable+product,equal(gains,endpoint))
        targets=[c for c in contrasts if c['variable']==variable and c['lead_days']=='0']
        for c in targets:
            daily=defaultdict(list)
            for r in groups[(variable,'0')]:daily[r['valid_date']].append(float(r[c['contrast']]))
            values=[np.mean(daily[(date(2025,1,1)+timedelta(days=i)).isoformat()]) for i in range(365)]
            for block in (7,14):
                lo,hi=bootstrap(values,block);check('bootstrap:'+variable+c['contrast']+str(block),equal(lo,c[f'ci{block}_low']) and equal(hi,c[f'ci{block}_high']))
        for c in (r for r in revision_contrasts if r['variable']==variable and r['new_lead']=='0'):
            a,b=c['contrast'].split('_minus_');daily=defaultdict(list)
            for r in pairgroups[(variable,'0')]:daily[r['valid_date']].append(float(r[a+'_gain'])-float(r[b+'_gain']))
            values=[np.mean(daily[(date(2025,1,1)+timedelta(days=i)).isoformat()]) for i in range(365)]
            for block in (7,14):
                lo,hi=bootstrap(values,block);check('revision_bootstrap:'+variable+c['contrast']+str(block),equal(lo,c[f'ci{block}_low']) and equal(hi,c[f'ci{block}_high']))
    live_count=None;online=[]
    if args.live:
        sys.path.insert(0,str(ROOT/'data_management/model_forecasts'))
        from manage_gfs import connect
        from psycopg.types.json import Jsonb
        requests=[dict(target=r['valid_date'],cutoff=r['cutoff_utc'],id=int(r['hko_timestamp_issue_id'])) for r in read('vintage_selection.csv')]
        with connect() as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
            mismatches=conn.execute("""WITH r AS (SELECT * FROM jsonb_to_recordset(%s) AS r(target date,cutoff timestamptz,id bigint))
                SELECT count(*) FROM r LEFT JOIN LATERAL (
                  SELECT i.forecast_issue_id FROM project.hko_forecast_daily f JOIN project.hko_forecast_issue i USING(forecast_issue_id)
                  WHERE f.valid_date=r.target AND f.lead_days BETWEEN 1 AND 9
                  AND i.bulletin_time_hkt AT TIME ZONE 'Asia/Hong_Kong'<=r.cutoff AND i.published_time_utc<=r.cutoff
                  ORDER BY i.bulletin_time_hkt DESC,i.forecast_issue_id DESC LIMIT 1) h ON true
                WHERE h.forecast_issue_id IS DISTINCT FROM r.id""",(Jsonb(requests),)).fetchone()[0]
            check('all_live_hko_vintages',mismatches==0);live_count=len(requests)
            match=[dict(target=r['valid_date'],variable=r['variable'],id=int(r['hko_issue_id']),forecast=r['hko'],truth=r['observed']) for r in cases]
            value_mismatches=conn.execute("""WITH r AS (SELECT * FROM jsonb_to_recordset(%s)
                AS r(target date,variable text,id bigint,forecast float8,truth float8))
                SELECT count(*) FROM r LEFT JOIN project.hko_forecast_daily f ON f.forecast_issue_id=r.id AND f.valid_date=r.target
                LEFT JOIN project.hko_observation_series s ON s.series_code='obs_hko_daily_'||r.variable
                LEFT JOIN project.hko_daily_observation o ON o.observation_series_id=s.observation_series_id AND o.observation_date=r.target
                WHERE (CASE WHEN r.variable='tmax' THEN f.forecast_tmax_c ELSE f.forecast_tmin_c END)::float8 IS DISTINCT FROM r.forecast
                OR o.value_numeric::float8 IS DISTINCT FROM r.truth OR o.data_completeness IS DISTINCT FROM 'C'""",(Jsonb(match),)).fetchone()[0]
            check('all_live_hko_forecasts_and_truth',value_mismatches==0)
            fresh=conn.execute("""SELECT s.run_time_utc,s.forecast_hour,t.temperature_c FROM project.external_model_source s
                JOIN project.external_model_temperature t USING(source_id) WHERE s.model='GFS' AND s.product='pgrb2.0p25'
                AND t.station_code='HKO' AND t.short_name='2t' AND s.run_time_utc>=TIMESTAMPTZ '2024-12-25 00:00:00+00'
                AND s.run_time_utc<TIMESTAMPTZ '2025-12-31 00:00:00+00' AND s.forecast_hour BETWEEN 15 AND 186
                AND EXTRACT(HOUR FROM s.run_time_utc AT TIME ZONE 'UTC')=0""").fetchall()
            controls={(run.astimezone(UTC).isoformat(),int(h)):float(v) for run,h,v in fresh}
            check('fresh_live_nearest_controls',len(controls)==21518 and all(equal(s['cell_se_c'],controls[(s['run_time_utc'],int(s['forecast_hour']))]) for s in sources))
        check('existing_nearest_data_control',meta['nearest_control_mismatches']==0 and meta['independently_imported_nearest_controls']==21518)
    if args.online_controls:
        import eccodes as ec,requests
        sys.path.insert(0,str(ROOT/'data_management/model_forecasts'))
        from manage_gfs import get_grib_subset
        http=requests.Session()
        for month in range(1,13):
            hour=(15,42,120,186)[(month-1)%4]
            r=next(s for s in sources if datetime.fromisoformat(s['run_time_utc']).date()==date(2025,month,15) and int(s['forecast_hour'])==hour)
            raw_bytes=get_grib_subset(http,r['source_url'],[(int(r['byte_start']),int(r['byte_end']),'')]);gid=ec.codes_new_from_message(raw_bytes)
            try:
                check('control_geometry:'+str(month),ec.codes_get(gid,'Ni')==1440 and ec.codes_get(gid,'Nj')==721
                      and ec.codes_get(gid,'latitudeOfFirstGridPointInDegrees')==90 and ec.codes_get(gid,'longitudeOfFirstGridPointInDegrees')==0
                      and ec.codes_get(gid,'jScansPositively')==0 and ec.codes_get(gid,'iScansNegatively')==0)
                vals=ec.codes_get_values(gid)
                independently_decoded=[float(vals[round((90-lat)/.25)*1440+round(lon/.25)])-273.15 for lat,lon in ((22.25,114),(22.25,114.25),(22.5,114),(22.5,114.25))]
                actual=[float(r['cell_'+c+'_c']) for c in ('sw','se','nw','ne')]
                okay=hashlib.sha256(raw_bytes).hexdigest()==r['subset_sha256'] and all(equal(a,b) for a,b in zip(actual,independently_decoded))
                check('original_noaa_control:'+str(month),okay);online.append(dict(month=month,url=r['source_url'],sha256=r['subset_sha256'],four_cells_match=okay))
            finally:ec.codes_release(gid)
    result=dict(passed=all(c['passed'] for c in checks),checks=len(checks),failed_checks=[c for c in checks if not c['passed']],
        live_hko_selections=live_count,online_controls=online,database_writes=False,
        limits='Valid-window, spatial order, arithmetic, paired CIs and revisions verified. Four-cell raw source checks sampled. Does not certify historical availability or exact native daily extrema.')
    output='validation.json' if args.live or args.online_controls else 'reproduction_validation.json'
    (HERE/output).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(result,indent=2))
    return 0 if result['passed'] else 1


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print(json.dumps(dict(error_type=type(e).__name__,locations=[(Path(f.filename).name,f.lineno) for f in traceback.extract_tb(e.__traceback__)])));sys.exit(1)
