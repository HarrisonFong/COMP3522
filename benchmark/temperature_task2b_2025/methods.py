"""Midnight-to-midnight temperature alignment, spatial methods and paired scores."""
from datetime import date,datetime,time,timedelta,timezone
import math
import numpy as np

UTC=timezone.utc;HKT=timezone(timedelta(hours=8))
START,END=date(2025,1,1),date(2026,1,1)
HQ=(22.30194444,114.17416667)
CORNERS=((22.25,114.),(22.25,114.25),(22.5,114.),(22.5,114.25))


def weights(latitude=HQ[0],longitude=HQ[1]):
    y=(latitude-22.25)/.25;x=(longitude-114.)/.25
    if not 0<=x<=1 or not 0<=y<=1:raise ValueError('Bilinear extrapolation forbidden')
    result=np.array([(1-y)*(1-x),(1-y)*x,y*(1-x),y*x])
    if abs(result.sum()-1)>1e-12:raise ValueError('Invalid bilinear weight sum')
    return result


def day_window(target):
    left=datetime.combine(target,time(),HKT).astimezone(UTC)
    return left,left+timedelta(days=1)


def full_day(run,record,target):
    left,right=day_window(target)
    hours=np.asarray(record['hours'],dtype=float)
    a=(left-run).total_seconds()/3600;b=(right-run).total_seconds()/3600
    if b-a!=24 or a<hours[0] or b>hours[-1]:raise ValueError('Cannot bracket complete HKT day')
    values=np.asarray([r['values_c'] for r in record['sources']],dtype=float)
    if values.shape!=(len(hours),4) or not np.isfinite(values).all():raise ValueError('Invalid four-cell trajectory')
    inside=(hours>a)&(hours<b)
    knots=np.r_[a,hours[inside],b]
    cells=np.stack([np.interp(knots,hours,values[:,j]) for j in range(4)],axis=1)
    w=weights();near=cells[:,1];bilinear=cells@w
    raw_inside=(hours>=a)&(hours<b)
    # For the explicitly continuous linear proxy, the limit from within the
    # half-open day at its right boundary equals the interpolated endpoint.
    # No next-day interior values are included, and no extrapolation is used.
    output=dict(valid_start_utc=left.isoformat(),valid_end_exclusive_utc=right.isoformat(),window_hours=24,
                nearest_tmax=float(near.max()),nearest_tmin=float(near.min()),
                bilinear_tmax=float(bilinear.max()),bilinear_tmin=float(bilinear.min()),
                sampled_nearest_tmax=float(values[raw_inside,1].max()),sampled_nearest_tmin=float(values[raw_inside,1].min()),
                sampled_bilinear_tmax=float((values[raw_inside]@w).max()),sampled_bilinear_tmin=float((values[raw_inside]@w).min()),
                extrema_first_bilinear_tmax=float(cells.max(axis=0)@w),extrema_first_bilinear_tmin=float(cells.min(axis=0)@w),
                native_in_day_count=int(raw_inside.sum()),midnight_start_interpolated=bool(a not in hours),
                midnight_end_interpolated=bool(b not in hours),temporal_proxy='continuous_piecewise_linear_TMP',
                exact_native_daily_extremum=False)
    return output,[dict(forecast_hour=float(h),nearest_c=float(n),bilinear_c=float(v),
                        cell_sw_c=float(c[0]),cell_se_c=float(c[1]),cell_nw_c=float(c[2]),cell_ne_c=float(c[3]))
                   for h,n,v,c in zip(knots,near,bilinear,cells)]


def select_hko(rows,cutoff,require_capture=False):
    candidates=[r for r in rows if r['bulletin_time_hkt'].replace(tzinfo=HKT)<=cutoff
                and r['published_time_utc'] is not None and r['published_time_utc']<=cutoff
                and (not require_capture or r['retrieved_at_utc'] is not None and r['retrieved_at_utc']<=cutoff)]
    return max(candidates,key=lambda r:(r['bulletin_time_hkt'],r['forecast_issue_id'])) if candidates else None


def ci(values,days,block=7):
    sums=np.zeros(365);counts=np.zeros(365)
    for v,day in zip(values,days):i=(day-START).days;sums[i]+=v;counts[i]+=1
    if not counts.any():return (None,None)
    rng=np.random.default_rng(3522)
    starts=rng.integers(0,365,size=(2000,math.ceil(365/block)))
    draw=((starts[:,:,None]+np.arange(block))%365).reshape(2000,-1)[:,:365]
    denominator=counts[draw].sum(axis=1);keep=denominator>0
    estimates=sums[draw].sum(axis=1)[keep]/denominator[keep]
    return tuple(float(x) for x in np.quantile(estimates,[.025,.975]))


def metrics(forecasts,truth):
    e=np.asarray(forecasts,dtype=float)-np.asarray(truth,dtype=float)
    if not len(e):return dict(n=0,mae=None,rmse=None,bias=None)
    return dict(n=len(e),mae=float(abs(e).mean()),rmse=float(np.sqrt(np.mean(e*e))),bias=float(e.mean()))
