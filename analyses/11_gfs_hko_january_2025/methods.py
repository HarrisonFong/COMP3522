"""Frozen, source-independent January trial methods; no database writes."""
from datetime import datetime, date, time, timedelta, timezone
from collections import defaultdict
import math
import numpy as np

UTC = timezone.utc
HKT = timezone(timedelta(hours=8))
START, END = date(2025, 1, 1), date(2025, 2, 1)
SCENARIOS = {
    '20HKT_lag6': (20, 6), '20HKT_lag4': (20, 4),
    '20HKT_lag8': (20, 8), '20HKT_lag12': (20, 12),
    '12HKT_lag6': (12, 6), '16HKT_lag6': (16, 6),
}
BASE = '20HKT_lag6'
COLS = {'tmax': 'forecast_tmax_c', 'tmin': 'forecast_tmin_c',
        'rh_min': 'forecast_rh_min_pct', 'rh_max': 'forecast_rh_max_pct'}


def day_window(target):
    start = datetime.combine(target, time(), HKT).astimezone(UTC)
    return start, start + timedelta(days=1)


def select_hko(rows, cutoff):
    # Retain an older issue if it really is the latest known candidate; report
    # its age instead of silently pretending it was issued on the decision day.
    candidates = [r for r in rows if r['bulletin_time_hkt'].replace(tzinfo=HKT) <= cutoff
                  and r['published_time_utc'] is not None and r['published_time_utc'] <= cutoff]
    return max(candidates, key=lambda r: (r['bulletin_time_hkt'], r['forecast_issue_id'])) if candidates else None


def select_run(runs, cutoff, lag_hours):
    candidates = [run for run in runs if run + timedelta(hours=lag_hours) <= cutoff]
    return max(candidates) if candidates else None


def union_hours(rows, start, end):
    cursor, total = start, 0.
    for left, right in sorted((max(r['interval_start_utc'], start), min(r['valid_time_utc'], end))
                              for r in rows if r['interval_start_utc'] < end and r['valid_time_utc'] > start):
        if right > max(cursor, left):
            total += (right - max(cursor, left)).total_seconds()/3600
        cursor = max(cursor, right)
    return total


def reconstruct(rows, target, variable):
    start, end = day_window(target)
    extrema = [r for r in rows if r['short_name'] == variable]
    outer = [r for r in extrema if r['interval_start_utc'] < end and r['valid_time_utc'] > start]
    inner = [r for r in outer if start <= r['interval_start_utc'] and r['valid_time_utc'] <= end]
    samples = [r for r in rows if r['short_name'] == '2t' and start <= r['valid_time_utc'] < end]
    if union_hours(outer, start, end) != 24 or not inner or len(samples) != 8:
        return None
    if variable == 'tmax':
        lower = max(r['temperature_c']-max(.02,r['packing_step_c']) for r in inner)
        upper = max(r['temperature_c']+max(.02,r['packing_step_c']) for r in outer)
        sampled = max(r['temperature_c'] for r in samples)
    else:
        lower = min(r['temperature_c']-max(.02,r['packing_step_c']) for r in outer)
        upper = min(r['temperature_c']+max(.02,r['packing_step_c']) for r in inner)
        sampled = min(r['temperature_c'] for r in samples)
    if lower > upper:
        return None
    return dict(gfs_lower=lower,gfs_upper=upper,gfs=(lower+upper)/2,gfs_sampled=sampled,
                inner_hours=union_hours(inner,start,end),outer_hours=24.,sample_count=len(samples),
                envelope_width=upper-lower,source_ids=sorted({str(r['source_id']) for r in outer+samples}))


def error_bounds(lower, upper, actual):
    return max(lower-actual,actual-upper,0.), max(abs(lower-actual),abs(upper-actual))


def metrics(forecasts, observed):
    error=np.asarray(forecasts,dtype=float)-np.asarray(observed,dtype=float)
    return dict(n=len(error),mae=float(np.abs(error).mean()),rmse=float(np.sqrt(np.mean(error**2))),
                bias=float(error.mean())) if len(error) else dict(n=0,mae=None,rmse=None,bias=None)


def block_ci(values, dates, block=7, repetitions=2000):
    # Resample calendar dates in moving circular blocks; all leads and products
    # on the same target date move together. Only 31 weather dates are available.
    days=[START+timedelta(days=i) for i in range((END-START).days)]
    sums=np.zeros(len(days));counts=np.zeros(len(days))
    for value,target in zip(values,dates):
        idx=(target-START).days;sums[idx]+=value;counts[idx]+=1
    rng=np.random.default_rng(3522)
    first=rng.integers(0,len(days),size=(repetitions,math.ceil(len(days)/block)))
    draw=((first[:,:,None]+np.arange(block))%len(days)).reshape(repetitions,-1)[:,:len(days)]
    denom=counts[draw].sum(axis=1)
    estimates=sums[draw].sum(axis=1)[denom>0]/denom[denom>0]
    return tuple(float(x) for x in np.quantile(estimates,[.025,.975]))


def revision_summary(cases, product):
    groups=defaultdict(dict)
    for r in cases:
        groups[(r['variable'],r['valid_date'])][r['lead_days']]=r
    pairs=[];ffi=[]
    for (variable,target),trajectory in sorted(groups.items()):
        ordered=[trajectory[lead] for lead in range(7,0,-1) if lead in trajectory]
        if len(ordered)==7:
            values=np.array([r[product] for r in ordered])
            ffi.append(dict(product=product,variable=variable,valid_date=target,
                            ffi=max(0.,float((np.abs(np.diff(values)).sum()-np.ptp(values))/5))))
        for lead in range(1,7):
            if lead not in trajectory or lead+1 not in trajectory: continue
            new,old=trajectory[lead],trajectory[lead+1]
            if (new['decision_date']-old['decision_date']).days!=1: continue
            delta=new[product]-old[product]
            benefit=abs(old[product]-new['observed'])-abs(new[product]-new['observed'])
            pairs.append(dict(product=product,variable=variable,valid_date=target,later_lead=lead,
                              delta=delta,benefit=benefit,changed=abs(delta)>1e-10,
                              material_change=abs(delta)>=1.-1e-10,
                              improved=benefit>1e-10,worsened=benefit < -1e-10))
    summaries=[]
    for variable in sorted({r['variable'] for r in pairs}):
        for lead in range(7):
            members=[r for r in pairs if r['variable']==variable and (lead==0 or r['later_lead']==lead)]
            if not members:continue
            changed=[r for r in members if r['changed']]
            summaries.append(dict(product=product,variable=variable,later_lead=lead,n_pairs=len(members),
                n_dates=len({r['valid_date'] for r in members}),n_changed=len(changed),
                revision_rate_pct=100*len(changed)/len(members),
                material_revision_rate_pct=100*np.mean([r['material_change'] for r in members]),
                mean_absolute_revision=float(np.mean([abs(r['delta']) for r in members])),
                mean_error_reduction_all=float(np.mean([r['benefit'] for r in members])),
                usefulness_changed_pct=100*np.mean([r['improved'] for r in changed]) if changed else None,
                mean_error_reduction_changed=float(np.mean([r['benefit'] for r in changed])) if changed else None,
                mean_ffi=float(np.mean([r['ffi'] for r in ffi if r['variable']==variable]))))
    return summaries,pairs,ffi
