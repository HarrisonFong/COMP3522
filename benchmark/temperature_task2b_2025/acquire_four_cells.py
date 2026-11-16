"""Bounded-memory, resumable original NOAA TMP four-cell extraction. No DB writes."""
from __future__ import annotations
import argparse,gzip,hashlib,json,math,os,sys,time,traceback
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'data_management/model_forecasts'))
import manage_gfs as manager
import stream_gfs as engine
UTC=timezone.utc
HQ=(22.30194444,114.17416667)
CORNERS=((22.25,114.),(22.25,114.25),(22.5,114.),(22.5,114.25))
HOURS=tuple(range(15,187,3))
CACHE=HERE/'cache/four_cells'


def decode(content,run,hour):
    import eccodes as ec
    if len(content)<20 or content[:4]!=b'GRIB' or int.from_bytes(content[8:16],'big')!=len(content):
        raise ValueError('Expected exactly one complete TMP GRIB2 message')
    gid=ec.codes_new_from_message(content)
    try:
        ec.codes_set(gid,'stepUnits',1)
        actual=datetime.strptime(f"{ec.codes_get(gid,'dataDate'):08d}{ec.codes_get(gid,'dataTime'):04d}",'%Y%m%d%H%M').replace(tzinfo=UTC)
        if actual!=run or ec.codes_get(gid,'endStep')!=hour:raise ValueError('Wrong forecast initialization or lead')
        if (ec.codes_get(gid,'shortName')!='2t' or ec.codes_get(gid,'stepType')!='instant'
            or ec.codes_get(gid,'typeOfLevel')!='heightAboveGround' or ec.codes_get(gid,'level')!=2
            or ec.codes_get(gid,'units')!='K'):raise ValueError('Wrong temperature definition')
        points=ec.codes_grib_find_nearest(gid,*HQ,npoints=4)
        values={(float(p['lat']),(float(p['lon'])+180)%360-180):float(p['value'])-273.15 for p in points}
        if set(values)!=set(CORNERS):raise ValueError('Wrong bracketing grid cells')
        if any(not math.isfinite(v) or not -100<v<70 for v in values.values()):raise ValueError('Missing/invalid four-cell temperature')
        meta={k:ec.codes_get(gid,k) for k in ('paramId','shortName','stepType','startStep','endStep','typeOfLevel','level','units','packingType','binaryScaleFactor','decimalScaleFactor','Ni','Nj')}
        return [values[c] for c in CORNERS],meta
    finally:ec.codes_release(gid)


def run_path(day):return CACHE/(str(day)+'.json.gz')


def read_run(day):
    path=run_path(day)
    if not path.exists():return None
    with gzip.open(path,'rt',encoding='utf-8') as f:record=json.load(f)
    if record['date']!=str(day) or tuple(record['hours'])!=HOURS or record['hq']!=list(HQ) or record['corners']!=[list(c) for c in CORNERS]:
        raise ValueError('Four-cell cache contract mismatch')
    expected=record.pop('record_sha256')
    if hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()!=expected:
        raise ValueError('Four-cell cache content digest mismatch')
    record['record_sha256']=expected
    return record


def acquire(day):
    cached=read_run(day)
    if cached:return dict(date=str(day),cached=True,sources=58,bytes=0)
    run=datetime.combine(day,datetime.min.time(),UTC);http=engine.session();sources=[]
    for hour in HOURS:
        url=f'{manager.BASE_URL}/gfs.{day:%Y%m%d}/00/atmos/gfs.t00z.pgrb2.0p25.f{hour:03d}'
        response=http.get(url+'.idx',timeout=(15,60));response.raise_for_status()
        ranges=manager.selected_ranges(response.text,['TMP'])
        if len(ranges)!=1:raise ValueError('Expected one 2m TMP index entry')
        raw=manager.get_grib_subset(http,url,ranges);values,metadata=decode(raw,run,hour)
        sources.append(dict(hour=hour,valid_time_utc=(run+timedelta(hours=hour)).isoformat(),values_c=values,
            url=url,index_line=ranges[0][2],byte_range=list(ranges[0][:2]),subset_sha256=hashlib.sha256(raw).hexdigest(),
            subset_bytes=len(raw),metadata=metadata))
    record=dict(date=str(day),run_time_utc=run.isoformat(),cycle_utc=0,hq=list(HQ),corners=[list(c) for c in CORNERS],
                hours=list(HOURS),sources=sources,retrieved_at_utc=datetime.now(UTC).isoformat(),raw_retained=False)
    record['record_sha256']=hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    CACHE.mkdir(parents=True,exist_ok=True)
    temp=run_path(day).with_suffix(f'.{os.getpid()}.tmp')
    with gzip.open(temp,'wt',encoding='utf-8') as f:json.dump(record,f,separators=(',',':'))
    temp.replace(run_path(day))
    return dict(date=str(day),cached=False,sources=len(sources),bytes=sum(s['subset_bytes'] for s in sources))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',type=date.fromisoformat,default=date(2024,12,25));p.add_argument('--end',type=date.fromisoformat,default=date(2025,12,31))
    p.add_argument('--workers',type=int,default=16);args=p.parse_args()
    if args.end<=args.start or not 1<=args.workers<=24:p.error('Invalid date range or worker count')
    days=[args.start+timedelta(days=i) for i in range((args.end-args.start).days)]
    cached=sum(read_run(d) is not None for d in days);pending=[d for d in days if not run_path(d).exists()]
    CACHE.parent.mkdir(parents=True,exist_ok=True)
    state=dict(state='running',expected_runs=len(days),complete_runs=cached,expected_sources=len(days)*58,
               downloaded_bytes=0,errors=[],raw_storage='in_memory_only',database_writes=False)
    status=CACHE.parent/'acquisition_status.json';start=time.monotonic()
    def save():status.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8',newline='\n')
    save();print(f'Starting {len(pending)} runs; {cached} cached; {len(days)*58} TMP sources expected',flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(acquire,d):(d,0) for d in pending}
        while futures:
            for future in as_completed(list(futures)):
                day,attempt=futures.pop(future)
                try:result=future.result()
                except Exception as exc:
                    if attempt<2:futures[pool.submit(acquire,day)]=(day,attempt+1)
                    else:state['errors'].append(dict(date=str(day),error_type=type(exc).__name__))
                else:
                    state['complete_runs']+=1;state['downloaded_bytes']+=result['bytes']
                    print(f"Committed extract {day}: {state['complete_runs']}/{len(days)} runs; {state['downloaded_bytes']/1e9:.2f} GB transferred",flush=True)
                state['elapsed_seconds']=round(time.monotonic()-start,1);save()
    state['state']='complete' if state['complete_runs']==len(days) else 'incomplete';save();print(json.dumps(state,indent=2))
    return 0 if state['state']=='complete' else 1


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        print(json.dumps(dict(error_type=type(exc).__name__,locations=[(Path(f.filename).name,f.lineno) for f in traceback.extract_tb(exc.__traceback__)])),file=sys.stderr);sys.exit(1)
