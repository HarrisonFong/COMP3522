"""Read-only rainfall audit independent of local importer progress files."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from itertools import groupby
from pathlib import Path

import manage_gfs as manager
import stream_gfs_rainfall as rain

UTC = timezone.utc


def verify(start=date(2024,12,24), end=date(2026,1,1), cycles=(0,6,12,18), online=True):
    left=datetime.combine(start,datetime.min.time(),UTC)
    right=datetime.combine(end,datetime.min.time(),UTC)
    scope=(left,right,list(cycles))
    filters="""s.model='GFS' AND s.product='pgrb2.0p25'
        AND s.manifest->'requested_fields'='["APCP"]'::jsonb
        AND s.run_time_utc >= %s AND s.run_time_utc < %s
        AND EXTRACT(HOUR FROM s.run_time_utc AT TIME ZONE 'UTC')=ANY(%s)"""
    checks={}; receipt=dict(verified_at_utc=datetime.now(UTC).isoformat(),
        scope=dict(start=str(start),end_exclusive=str(end),cycles_utc=list(cycles),
                   forecast_hours='3:192:3',station='HKO'),checks=checks)
    samples=[]
    with manager.connect(read_only=True) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        checks['read_only']=conn.execute('SHOW transaction_read_only').fetchone()[0]=='on'
        station=dict(zip(('station_code','station_name','latitude','longitude'),conn.execute(
            "SELECT station_code,station_name,latitude,longitude FROM project.hko_station WHERE station_code='HKO'").fetchone()))
        schedule=conn.execute("""
            WITH expected AS (
                SELECT d+c*INTERVAL '1 hour' AS run,h FROM
                generate_series(%s::timestamptz,%s::timestamptz-INTERVAL '1 day',INTERVAL '1 day') d
                CROSS JOIN unnest(%s::int[]) c CROSS JOIN generate_series(3,192,3) h
            ), actual AS (
                SELECT s.run_time_utc AS run,s.forecast_hour AS h,count(*) AS copies
                FROM project.external_model_source s WHERE """+filters+""" GROUP BY 1,2
            ) SELECT count(*) FILTER(WHERE e.run IS NOT NULL),
                     count(*) FILTER(WHERE e.run IS NOT NULL AND a.run IS NULL),
                     count(*) FILTER(WHERE e.run IS NULL),count(*) FILTER(WHERE a.copies<>1)
              FROM expected e FULL JOIN actual a USING(run,h)
        """,scope+scope).fetchone()
        expected=schedule[0]
        receipt['schedule']=dict(zip(('expected_sources','missing_sources','unexpected_slots','duplicate_slots'),schedule))
        checks['complete_unique_schedule']=schedule[1:]==(0,0,0)
        source_count=source_errors=byte_total=0
        digests={}
        with conn.cursor(name='rain_source_audit') as cur:
            cur.itersize=300
            cur.execute('SELECT s.source_id,s.source_url,s.subset_sha256,s.subset_size_bytes,'
                        's.run_time_utc,s.forecast_hour,s.manifest FROM project.external_model_source s WHERE '+filters,scope)
            for source_id,url,digest,size,run,hour,m in cur:
                source_count+=1;byte_total+=size;run=run.astimezone(UTC)
                wanted=f'{manager.BASE_URL}/gfs.{run:%Y%m%d}/{run.hour:02d}/atmos/gfs.t{run.hour:02d}z.pgrb2.0p25.f{hour:03d}'
                valid=(url==wanted and size>0 and len(digest)==64
                    and all(c in '0123456789abcdef' for c in digest)
                    and source_id==uuid.uuid5(uuid.NAMESPACE_URL,url+'#'+digest)
                    and m.get('source_id')==str(source_id) and m.get('source_url')==url
                    and m.get('subset_sha256')==digest and m.get('subset_size_bytes')==size
                    and m.get('station_snapshot')==[station] and m.get('forecast_hour')==hour
                    and datetime.fromisoformat(m['run_time_utc'])==run
                    and m.get('requested_fields')==['APCP'] and m.get('raw_subset_retained') is False
                    and m.get('storage_mode')=='station_extract_only'
                    and len(m.get('selected_index_lines',[]))==len(m.get('byte_ranges',[]))==2
                    and len(m.get('grib_message_metadata',[]))==2)
                source_errors+=not valid
                digests[source_id]=m.get('decoded_rows_sha256')
                # For a small pilot, verify its first/middle/last positive leads.
                # For a year, verify one varied cycle and positive lead per month.
                if (end-start).days<=2:
                    sample=run==left+timedelta(hours=min(cycles)) and hour in (3,9,192)
                else:
                    sample=(run.year==2025 and run.day==15 and run.hour==((run.month-1)%4)*6
                            and hour==(3,9,96,192)[(run.month-1)%4])
                if sample:samples.append(m)
        receipt['source_audit']=dict(checked=source_count,invalid=source_errors,subset_bytes=byte_total)
        checks['source_provenance']=source_count==expected and source_errors==0
        rows_checked=groups=bad_rows=bad_groups=bad_digests=0
        with conn.cursor(name='rain_row_audit') as cur:
            cur.itersize=2000
            cur.execute('SELECT p.source_id,s.run_time_utc,s.forecast_hour,'+
                ','.join('p.'+c for c in rain.VALUE_COLUMNS)+
                ' FROM project.external_model_precipitation p JOIN project.external_model_source s USING(source_id) '
                "WHERE p.station_code='HKO' AND "+filters+' ORDER BY p.source_id,p.message_number',scope)
            for source_id,group in groupby(cur,key=lambda r:r[0]):
                decoded=[];groups+=1
                for _,run,hour,*values in group:
                    r=dict(zip(rain.VALUE_COLUMNS,values));rows_checked+=1
                    value=r['source_value'];unit=r['source_unit']
                    converted=value*1000 if unit=='m' else value
                    valid=(math.isfinite(value) and value>=0 and math.isfinite(r['precipitation_mm'])
                        and unit in ('kg m**-2','kg m-2','kg m^-2','kg/m^2','mm','m')
                        and r['precipitation_mm']==converted and r['step_type']=='accum'
                        and run<=r['interval_start_utc']<r['valid_time_utc']==run+timedelta(hours=hour)
                        and r['target_latitude']==station['latitude'] and r['target_longitude']==station['longitude']
                        and r['grid_latitude']==22.25 and r['grid_longitude']==114.25
                        and 9<r['grid_distance_km']<11 and r['extraction_method']=='nearest_grid_point')
                    bad_rows+=not valid
                    decoded.append({k:v.astimezone(UTC).isoformat() if isinstance(v,datetime) else v for k,v in r.items()})
                bad_groups+=([r['message_number'] for r in decoded]!=[1,2]
                             or len({r['original_message_number'] for r in decoded})!=2)
                digest=hashlib.sha256(json.dumps(decoded,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                bad_digests+=digest!=digests[source_id]
        receipt['station_audit']=dict(rows_checked=rows_checked,sources_checked=groups,invalid_rows=bad_rows,
                                      invalid_message_groups=bad_groups,decoded_digest_mismatches=bad_digests)
        checks['station_rows']=rows_checked==2*expected and groups==expected and bad_rows==bad_groups==bad_digests==0
        receipt['table_storage_bytes']=dict(conn.execute("""SELECT relname,pg_total_relation_size(oid)
            FROM pg_class WHERE relnamespace='project'::regnamespace AND
            relname IN ('external_model_source','external_model_precipitation','external_model_temperature')""").fetchall())
    receipt['online_samples']=[]
    if online:
        http=rain.engine.session()
        for m in sorted(samples,key=lambda x:(x['run_time_utc'],x['forecast_hour'])):
            content=manager.get_grib_subset(http,m['source_url'],[(a,b,'') for a,b in m['byte_ranges']])
            rows,_=rain.decode(content,m['station_snapshot'],datetime.fromisoformat(m['run_time_utc']),
                               m['forecast_hour'],m['selected_index_lines'])
            digest=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            receipt['online_samples'].append(dict(run_time_utc=m['run_time_utc'],forecast_hour=m['forecast_hour'],
                raw_sha256_matches=hashlib.sha256(content).hexdigest()==m['subset_sha256'],
                decoded_rows_match=digest==m['decoded_rows_sha256']))
        expected_samples=3 if (end-start).days<=2 else 12
        checks['noaa_sample_redownloads']=len(samples)==expected_samples and all(
            r['raw_sha256_matches'] and r['decoded_rows_match'] for r in receipt['online_samples'])
    else:receipt['online_samples_skipped']=True
    receipt['passed']=all(checks.values())
    receipt['limits']='HQ nearest-grid accumulated amounts only. Overlapping messages must not be summed. Does not validate HKT daily totals, historical availability, territory-wide rain or forecast skill. Raw-byte checks are sampled.'
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',type=date.fromisoformat,default=date(2024,12,24))
    parser.add_argument('--end',type=date.fromisoformat,default=date(2026,1,1))
    parser.add_argument('--cycles',type=int,nargs='+',choices=(0,6,12,18),default=[0,6,12,18])
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--output',type=Path,default=manager.HERE/'results'/'gfs_2025_rainfall_verification.json')
    args=parser.parse_args()
    if args.end<=args.start:parser.error('End must follow start')
    try:receipt=verify(args.start,args.end,sorted(set(args.cycles)),not args.offline)
    except Exception as exc:
        print('Rainfall audit failed ('+type(exc).__name__+'). No database writes.',file=sys.stderr);return 1
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt,indent=2))
    return 0 if receipt['passed'] else 1


if __name__=='__main__':sys.exit(main())
