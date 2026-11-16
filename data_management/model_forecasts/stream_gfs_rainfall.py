"""Low-disk original GFS APCP acquisition, retaining both accumulation messages.

Defaults match the temperature run dates and all four cycles. Native rainfall
is absent at lead zero, so leads 3:192:3 are the 64 required positive leads.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import signal
import sys
import uuid

import manage_gfs as manager
import stream_gfs as engine

UTC=timezone.utc
VALUE_COLUMNS=(
    'station_code','message_number','original_message_number','parameter_id','short_name',
    'parameter_name','step_type','interval_start_utc','valid_time_utc','target_latitude',
    'target_longitude','grid_latitude','grid_longitude','grid_distance_km','extraction_method',
    'source_value','source_unit','precipitation_mm',
)


def tasks(start,end,cycles):
    for run,hour in engine.tasks(start,end,cycles):
        if hour>0:yield run,hour


def selected_ranges(index_text):
    lines=[line.split(':') for line in index_text.splitlines()]
    if not lines or any(len(r)<6 for r in lines):raise ValueError('Malformed NOAA index')
    offsets=[int(r[1]) for r in lines]
    if any(b<=a for a,b in zip(offsets,offsets[1:])):raise ValueError('Non-monotonic NOAA index')
    return [(int(r[1]),int(lines[i+1][1])-1 if i+1<len(lines) else None,':'.join(r))
            for i,r in enumerate(lines) if r[3]=='APCP' and r[4]=='surface']


def to_mm(value,unit):
    if not math.isfinite(value) or value<0:raise ValueError('Negative/missing rainfall')
    if unit in ('kg m**-2','kg m-2','kg m^-2','kg/m^2','mm'):return value
    if unit=='m':return value*1000.
    raise ValueError('Unsupported accumulated precipitation unit')


def decode(content,stations,run,hour,index_lines):
    import eccodes as ec
    position=0;number=0;rows=[];metadata=[]
    while position<len(content):
        prefix=content[position:position+16]
        if len(prefix)!=16 or prefix[:4]!=b'GRIB' or prefix[7]!=2:raise ValueError('Expected GRIB2')
        size=int.from_bytes(prefix[8:16],'big')
        if size<20 or position+size>len(content):raise ValueError('Truncated GRIB2')
        gid=ec.codes_new_from_message(content[position:position+size])
        try:
            number+=1
            actual=datetime.strptime(f"{ec.codes_get(gid,'dataDate'):08d}{ec.codes_get(gid,'dataTime'):04d}",'%Y%m%d%H%M').replace(tzinfo=UTC)
            if actual!=run:raise ValueError('Wrong initialization')
            ec.codes_set(gid,'stepUnits',1)
            left=float(ec.codes_get(gid,'startStep'));right=float(ec.codes_get(gid,'endStep'))
            if right!=hour or not 0<=left<right:raise ValueError('Wrong accumulation interval')
            identity=tuple(ec.codes_get(gid,k) for k in ('discipline','parameterCategory','parameterNumber'))
            if identity!=(0,1,8) or ec.codes_get(gid,'stepType')!='accum' or ec.codes_get(gid,'typeOfLevel')!='surface':
                raise ValueError('Expected surface total accumulated precipitation')
            unit=str(ec.codes_get(gid,'units'))
            original_number=int(index_lines[number-1].split(':')[0])
            meta={k:ec.codes_get(gid,k) for k in (
                'paramId','shortName','units','stepType','startStep','endStep','discipline',
                'parameterCategory','parameterNumber','productDefinitionTemplateNumber',
                'typeOfStatisticalProcessing','packingType','binaryScaleFactor','decimalScaleFactor',
                'bitsPerValue','Ni','Nj','iDirectionIncrementInDegrees','jDirectionIncrementInDegrees',
            ) if ec.codes_is_defined(gid,k)}
            meta['original_message_number']=original_number
            if 'binaryScaleFactor' in meta and 'decimalScaleFactor' in meta:
                meta['quantization_step_native_units']=2.**meta['binaryScaleFactor']/10.**meta['decimalScaleFactor']
            metadata.append(meta)
            for station in stations:
                point=ec.codes_grib_find_nearest(gid,station['latitude'],station['longitude'],npoints=1)[0]
                value=float(point['value'])
                if value==ec.codes_get(gid,'missingValue'):raise ValueError('Missing precipitation at station')
                rows.append(dict(station_code=station['station_code'],message_number=number,
                    original_message_number=original_number,parameter_id=int(ec.codes_get(gid,'paramId')),
                    short_name=str(ec.codes_get(gid,'shortName')),parameter_name=str(ec.codes_get(gid,'name')),
                    step_type='accum',interval_start_utc=(run+timedelta(hours=left)).isoformat(),
                    valid_time_utc=(run+timedelta(hours=right)).isoformat(),
                    target_latitude=station['latitude'],target_longitude=station['longitude'],
                    grid_latitude=float(point['lat']),grid_longitude=(float(point['lon'])+180)%360-180,
                    grid_distance_km=float(point['distance']),extraction_method='nearest_grid_point',
                    source_value=value,source_unit=unit,precipitation_mm=to_mm(value,unit)))
        finally:ec.codes_release(gid)
        position+=size
    if number!=2 or len(rows)!=2*len(stations) or len(index_lines)!=2:
        raise ValueError('Expected both original APCP messages per positive lead')
    return rows,metadata


def fetch(task,stations):
    run,hour=task
    name=f'gfs.t{run.hour:02d}z.pgrb2.0p25.f{hour:03d}'
    url=f'{manager.BASE_URL}/gfs.{run:%Y%m%d}/{run.hour:02d}/atmos/{name}'
    http=engine.session();response=http.get(url+'.idx',timeout=(15,60));response.raise_for_status()
    ranges=selected_ranges(response.text)
    if len(ranges)!=2:raise ValueError('Missing expected APCP message family')
    content=manager.get_grib_subset(http,url,ranges)
    rows,metadata=decode(content,stations,run,hour,[r[2] for r in ranges])
    digest=hashlib.sha256(content).hexdigest()
    manifest=dict(manifest_version=manager.MANIFEST_VERSION,
        source_id=str(uuid.uuid5(uuid.NAMESPACE_URL,url+'#'+digest)),provider='NOAA',model='GFS',
        product='pgrb2.0p25',run_time_utc=run.isoformat(),forecast_hour=hour,source_url=url,index_url=url+'.idx',
        retrieved_at_utc=datetime.now(UTC).isoformat(),
        subset_relative_path=f'not-retained/rainfall/{run:%Y%m%d}/{run.hour:02d}/{name}.APCP.grib2',
        subset_sha256=digest,subset_size_bytes=len(content),requested_fields=['APCP'],
        selected_index_lines=[r[2] for r in ranges],byte_ranges=[[r[0],r[1]] for r in ranges],
        station_snapshot=stations,availability_time_utc=None,
        availability_note='Historical publication time not established; retrieval time is provenance only.',
        field_family='precipitation',storage_mode='station_extract_only',raw_subset_retained=False,
        grib_message_metadata=metadata,
        accumulation_note='Both original messages retained, including coincident early windows. Do not sum overlapping periods or both messages.',
        decoded_rows_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest())
    return manifest,rows


def setup():
    with manager.connect(read_only=False) as conn:
        conn.execute((manager.HERE/'rainfall_schema.sql').read_text(encoding='utf-8'))


def statements():
    from psycopg import sql
    source_sql=engine.insert_statements()[0]
    columns=('source_id',*VALUE_COLUMNS)
    value_sql=sql.SQL('INSERT INTO project.external_model_precipitation ({}) VALUES ({}) '
                      'ON CONFLICT(source_id,station_code,message_number) DO NOTHING').format(
        sql.SQL(',').join(map(sql.Identifier,columns)),sql.SQL(',').join(sql.Placeholder() for _ in columns))
    return source_sql,value_sql


def commit(conn,sql,manifest,rows):
    from psycopg.types.json import Jsonb
    with conn.transaction():
        conn.execute(sql[0],[manifest[k] for k in engine.SOURCE_COLUMNS]+[Jsonb(manifest)])
        with conn.cursor() as cur:
            cur.executemany(sql[1],[[manifest['source_id']]+[r[k] for k in VALUE_COLUMNS] for r in rows])
        actual=conn.execute('SELECT '+','.join(VALUE_COLUMNS)+
            ' FROM project.external_model_precipitation WHERE source_id=%s AND station_code=ANY(%s) '
            'ORDER BY message_number,station_code',(manifest['source_id'],[r['station_code'] for r in manifest['station_snapshot']])).fetchall()
        expected=sorted(rows,key=lambda r:(r['message_number'],r['station_code']))
        if len(actual)!=len(expected):raise ValueError('Precipitation readback count mismatch')
        for values,row in zip(actual,expected):
            for key,value in zip(VALUE_COLUMNS,values):
                other=datetime.fromisoformat(row[key]) if isinstance(value,datetime) else row[key]
                if value!=other:raise ValueError('Precipitation readback value mismatch: '+key)
        identity=conn.execute('SELECT subset_sha256,subset_size_bytes FROM project.external_model_source WHERE source_id=%s',
                              (manifest['source_id'],)).fetchone()
        if identity!=(manifest['subset_sha256'],manifest['subset_size_bytes']):raise ValueError('Source identity mismatch')


def completed(conn,start,end,cycles,stations):
    rows=conn.execute("""
        SELECT s.run_time_utc,s.forecast_hour,s.manifest->'station_snapshot',p.station_code,
               array_agg(p.message_number ORDER BY p.message_number),
               count(DISTINCT p.original_message_number),bool_and(p.step_type='accum')
        FROM project.external_model_source s JOIN project.external_model_precipitation p USING(source_id)
        WHERE s.model='GFS' AND s.product='pgrb2.0p25' AND s.manifest->'requested_fields'='["APCP"]'::jsonb
          AND s.run_time_utc >= %s AND s.run_time_utc < %s
          AND EXTRACT(HOUR FROM s.run_time_utc AT TIME ZONE 'UTC')=ANY(%s) AND p.station_code=ANY(%s)
        GROUP BY s.source_id,s.run_time_utc,s.forecast_hour,p.station_code
    """,(datetime.combine(start,datetime.min.time(),UTC),datetime.combine(end,datetime.min.time(),UTC),
          cycles,[r['station_code'] for r in stations])).fetchall()
    found={}
    for run,hour,snapshot,station,messages,originals,valid in rows:
        if snapshot==stations and messages==[1,2] and originals==2 and valid:
            found.setdefault((run,hour),set()).add(station)
    required={r['station_code'] for r in stations}
    return {key for key,value in found.items() if value==required}


def audit(conn,args):
    return conn.execute("""
        SELECT count(*) FROM project.external_model_precipitation p
        JOIN project.external_model_source s USING(source_id)
        WHERE s.model='GFS' AND s.run_time_utc >= %s AND s.run_time_utc < %s AND p.station_code='HKO'
          AND (p.valid_time_utc <> s.run_time_utc+s.forecast_hour*INTERVAL '1 hour'
               OR p.interval_start_utc < s.run_time_utc OR p.interval_start_utc>=p.valid_time_utc
               OR p.step_type<>'accum' OR p.precipitation_mm<0
               OR NOT p.precipitation_mm < 'Infinity'::float8)
    """,(datetime.combine(args.start,datetime.min.time(),UTC),
          datetime.combine(args.end,datetime.min.time(),UTC))).fetchone()[0]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',type=date.fromisoformat,default=date(2024,12,24))
    parser.add_argument('--end',type=date.fromisoformat,default=date(2026,1,1))
    parser.add_argument('--cycles',type=int,nargs='+',choices=(0,6,12,18),default=[0,6,12,18])
    parser.add_argument('--workers',type=int,default=16)
    parser.add_argument('--max-errors',type=int,default=12)
    parser.add_argument('--status',type=Path,default=manager.HERE/'downloads'/'gfs_2025_rainfall_status.json')
    args=parser.parse_args();args.cycles=sorted(set(args.cycles))
    if args.end<=args.start or not 1<=args.workers<=24 or args.max_errors<1:parser.error('Invalid range/worker count')
    signal.signal(signal.SIGINT,lambda *_:engine._stop.set())
    signal.signal(signal.SIGTERM,lambda *_:engine._stop.set())
    adapter=engine.ImportAdapter('precipitation','3:192:3',256,tasks,fetch,statements,commit,completed,audit,setup)
    try:return engine.run(args,adapter)
    except Exception as exc:
        print('Rainfall import failed ('+type(exc).__name__+'). Committed sources are resumable.',file=sys.stderr)
        return 1


if __name__=='__main__':sys.exit(main())
