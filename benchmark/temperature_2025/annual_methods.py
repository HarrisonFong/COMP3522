"""2025 methods; the daily-extremum rule preserves the January trial protocol."""
from datetime import date, datetime, time, timedelta, timezone
import math
import numpy as np

UTC=timezone.utc
HKT=timezone(timedelta(hours=8))
START,END=date(2025,1,1),date(2026,1,1)
BASE='20HKT_lag6'
SCENARIOS={BASE:(20,6),'20HKT_lag4':(20,4),'20HKT_lag8':(20,8),
           '20HKT_lag12':(20,12),'12HKT_lag6':(12,6),'16HKT_lag6':(16,6),
           '02HKT_lag6':(2,6),'08HKT_lag6':(8,6),'14HKT_lag6':(14,6)}


def union_hours(intervals,start,end):
    cursor=start;seconds=0.
    for left,right in sorted((max(a,start),min(b,end)) for a,b in intervals if a<end and b>start):
        seconds+=max(0.,(right-max(cursor,left)).total_seconds());cursor=max(cursor,right)
    return seconds/3600


def reconstruct(rows,target,variable):
    start=datetime.combine(target,time(),HKT).astimezone(UTC);end=start+timedelta(days=1)
    outer=[r for r in rows if r['short_name']==variable and r['interval_start_utc']<end and r['valid_time_utc']>start]
    inner=[r for r in outer if start<=r['interval_start_utc'] and r['valid_time_utc']<=end]
    samples=[r['temperature_c'] for r in rows if r['short_name']=='2t' and start<=r['valid_time_utc']<end]
    if not inner or len(samples)!=8 or union_hours([(r['interval_start_utc'],r['valid_time_utc']) for r in outer],start,end)!=24:
        return None
    if variable=='tmax':
        lower=max(r['temperature_c']-max(.02,r['packing_step_c']) for r in inner)
        upper=max(r['temperature_c']+max(.02,r['packing_step_c']) for r in outer)
        sampled=max(samples)
    else:
        lower=min(r['temperature_c']-max(.02,r['packing_step_c']) for r in outer)
        upper=min(r['temperature_c']+max(.02,r['packing_step_c']) for r in inner)
        sampled=min(samples)
    if lower>upper:return None
    return dict(gfs_lower=lower,gfs_upper=upper,gfs=(lower+upper)/2,gfs_sampled=sampled,
                inner_hours=union_hours([(r['interval_start_utc'],r['valid_time_utc']) for r in inner],start,end),
                source_count=len({r['source_id'] for r in outer}),envelope_width=upper-lower)


def error_bounds(lower,upper,truth):
    return max(lower-truth,truth-upper,0.),max(abs(lower-truth),abs(upper-truth))


def ci(values,dates,block=7):
    sums=np.zeros(365);counts=np.zeros(365)
    for value,day in zip(values,dates):
        i=(day-START).days;sums[i]+=value;counts[i]+=1
    if not counts.sum():return (None,None)
    rng=np.random.default_rng(3522)
    first=rng.integers(0,365,size=(2000,math.ceil(365/block)))
    draw=((first[:,:,None]+np.arange(block))%365).reshape(2000,-1)[:,:365]
    den=counts[draw].sum(axis=1);keep=den>0
    return tuple(float(x) for x in np.quantile(sums[draw].sum(axis=1)[keep]/den[keep],[.025,.975]))


def rounded(value):
    return math.copysign(math.floor(abs(value)+.5),value)


def revision(old,new):
    if old['valid_date']!=new['valid_date'] or old['variable']!=new['variable']:
        raise ValueError('Revision must hold target and variable fixed')
    result={}
    for product in ('hko','gfs'):
        delta=new[product]-old[product]
        benefit=abs(old[product]-new['observed'])-abs(new[product]-new['observed'])
        result.update({product+'_delta':delta,product+'_benefit':benefit,
                       product+'_rounded_changed':rounded(old[product])!=rounded(new[product])})
    a,b=error_bounds(old['gfs_lower'],old['gfs_upper'],old['observed'])
    c,d=error_bounds(new['gfs_lower'],new['gfs_upper'],new['observed'])
    result['gfs_benefit_lower']=a-d;result['gfs_benefit_upper']=b-c
    result['paired_benefit_delta']=result['gfs_benefit']-result['hko_benefit']
    return result
