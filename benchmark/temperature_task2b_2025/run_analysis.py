"""Task 2b temperature only: exact HKT windows, two spatial methods, honest gates."""
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,sys,traceback
from collections import Counter,defaultdict
from datetime import date,datetime,time,timedelta
from pathlib import Path
import numpy as np
from methods import UTC,HKT,START,END,CORNERS,HQ,weights,day_window,full_day,select_hko,ci,metrics
from acquire_four_cells import read_run,HOURS
from read_hko import hook

HERE=Path(__file__).resolve().parent
PRODUCTS=('hko','nearest','bilinear')


def dump(name,value):
    (HERE/name).write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8',newline='\n')


def csv_out(name,rows):
    with (HERE/name).open('w',newline='',encoding='utf-8') as f:
        if not rows:f.write('reason\n');return
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def load():
    with gzip.open(HERE/'cache/hko_snapshot.json.gz','rt',encoding='utf-8') as f:hko=json.load(f,object_hook=hook)
    records={};sources=[];missing=[]
    for day in (date(2024,12,25)+timedelta(days=i) for i in range(371)):
        record=read_run(day)
        if record is None:missing.append(str(day));continue
        if [s['hour'] for s in record['sources']]!=list(HOURS):raise ValueError('Missing/duplicate GFS leads')
        records[day]=record
        for s in record['sources']:
            if s['metadata']['startStep']!=s['hour'] or s['metadata']['endStep']!=s['hour']:raise ValueError('Wrong TMP validity')
            sources.append(dict(run_time_utc=record['run_time_utc'],forecast_hour=s['hour'],valid_time_utc=s['valid_time_utc'],
                cell_sw_c=s['values_c'][0],cell_se_c=s['values_c'][1],cell_nw_c=s['values_c'][2],cell_ne_c=s['values_c'][3],
                source_url=s['url'],index_line=s['index_line'],byte_start=s['byte_range'][0],byte_end=s['byte_range'][1],
                subset_sha256=s['subset_sha256'],subset_bytes=s['subset_bytes'],measurement_height_m=s['metadata']['level'],
                native_unit=s['metadata']['units'],packing_type=s['metadata']['packingType']))
    return hko,records,sources,missing


def make_cases(hko,records):
    by_target=defaultdict(list);native=defaultdict(list);observed={}
    for r in hko['gfs_native_extrema']:native[(r['run_time_utc'],r['short_name'])].append(r)
    for r in hko['forecasts']:by_target[r['valid_date']].append(r)
    for r in hko['observations']:
        if r['data_completeness']=='C' and r['value_numeric'] is not None:
            k=(r['series_code'].removeprefix('obs_hko_daily_'),r['observation_date'])
            if k in observed:raise ValueError('Duplicate truth')
            observed[k]=float(r['value_numeric'])
    cases=[];knots=[];exclusions=[];selections=[];counts=Counter()
    for i in range(365):
        target=START+timedelta(days=i);left,right=day_window(target)
        for lead in range(1,8):
            issued=target-timedelta(days=lead)
            run=datetime.combine(issued,time(),UTC)
            cutoff=datetime.combine(issued,time(14),HKT).astimezone(UTC)
            candidate=select_hko(by_target[target],cutoff)
            captured=select_hko(by_target[target],cutoff,True)
            counts['expected_windows']+=1;counts['hko_timestamp_windows']+=candidate is not None
            counts['hko_capture_confirmed_windows']+=captured is not None;counts['gfs_run_present_windows']+=issued in records
            daily,points=full_day(run,records[issued],target) if issued in records else (None,[])
            selection=dict(valid_date=target,lead_days=lead,valid_start_utc=left.isoformat(),valid_end_exclusive_utc=right.isoformat(),
                valid_start_hkt=left.astimezone(HKT).isoformat(),valid_end_exclusive_hkt=right.astimezone(HKT).isoformat(),
                decision_date=issued,cutoff_utc=cutoff.isoformat(),hko_timestamp_issue_id=candidate['forecast_issue_id'] if candidate else None,
                hko_capture_confirmed_issue_id=captured['forecast_issue_id'] if captured else None,gfs_run_utc=run.isoformat(),
                gfs_historical_availability_verified=False)
            selections.append(selection)
            for point in points:knots.append(dict(valid_date=target,lead_days=lead,run_time_utc=run.isoformat(),**point))
            for var in ('tmax','tmin'):
                has_hko=candidate is not None and candidate['forecast_'+var+'_c'] is not None
                truth=observed.get((var,target));counts[var+'_expected']+=1
                counts[var+'_hko_numeric']+=has_hko;counts[var+'_gfs_numeric']+=daily is not None
                counts[var+'_truth_numeric']+=truth is not None
                reason='missing_truth' if truth is None else 'missing_hko_value' if not has_hko else 'missing_gfs_run' if daily is None else None
                if reason:
                    exclusions.append(dict(valid_date=target,lead_days=lead,variable=var,reason=reason));continue
                row=dict(valid_date=target,variable=var,lead_days=lead,decision_date=issued,
                    valid_start_utc=left.isoformat(),valid_end_exclusive_utc=right.isoformat(),window_hours=daily['window_hours'],
                    cutoff_utc=cutoff.isoformat(),hko_issue_id=candidate['forecast_issue_id'],hko_source_file_id=candidate['source_file_id'],
                    hko_bulletin_hkt=candidate['bulletin_time_hkt'].isoformat(),hko_published_utc=candidate['published_time_utc'].astimezone(UTC).isoformat(),
                    hko_capture_utc=candidate['retrieved_at_utc'].astimezone(UTC).isoformat() if candidate['retrieved_at_utc'] else None,
                    hko_capture_before_cutoff=bool(candidate['retrieved_at_utc'] and candidate['retrieved_at_utc']<=cutoff),
                    hko_product_lead=candidate['lead_days'],hko_stale=candidate['bulletin_time_hkt'].date()<issued,
                    gfs_run_utc=run.isoformat(),gfs_initialization_age_hours=(cutoff-run).total_seconds()/3600,
                    observed=truth,hko=float(candidate['forecast_'+var+'_c']),nearest=daily['nearest_'+var],bilinear=daily['bilinear_'+var],
                    nearest_sampled=daily['sampled_nearest_'+var],bilinear_sampled=daily['sampled_bilinear_'+var],
                    bilinear_extrema_first_diagnostic=daily['extrema_first_bilinear_'+var],
                    native_in_day_count=daily['native_in_day_count'],temporal_proxy=daily['temporal_proxy'],
                    midnight_start_interpolated=daily['midnight_start_interpolated'],midnight_end_interpolated=daily['midnight_end_interpolated'],
                    exact_native_daily_extremum=False,operational_availability_verified=False)
                row['nearest_minus_hko_ae']=abs(row['nearest']-truth)-abs(row['hko']-truth)
                row['bilinear_minus_hko_ae']=abs(row['bilinear']-truth)-abs(row['hko']-truth)
                row['bilinear_minus_nearest_ae']=abs(row['bilinear']-truth)-abs(row['nearest']-truth)
                outer=[r for r in native[(run,var)] if r['interval_start_utc']<right and r['valid_time_utc']>left]
                inner=[r for r in outer if left<=r['interval_start_utc'] and r['valid_time_utc']<=right]
                pad=lambda r:max(.02,float(r['packing_step_c']))
                if var=='tmax':
                    low=max(float(r['temperature_c'])-pad(r) for r in inner)
                    high=max(float(r['temperature_c'])+pad(r) for r in outer)
                else:
                    low=min(float(r['temperature_c'])-pad(r) for r in outer)
                    high=min(float(r['temperature_c'])+pad(r) for r in inner)
                row.update(nearest_native_conditional_lower=low,nearest_native_conditional_upper=high,
                           nearest_native_conditional_ae_lower=max(low-truth,truth-high,0.),
                           nearest_native_conditional_ae_upper=max(abs(low-truth),abs(high-truth)))
                cases.append(row);counts[var+'_paired']+=1
    return cases,knots,exclusions,selections,dict(counts)


def summarize(cases):
    scores=[];contrasts=[];temporal=[]
    for variable in ('tmax','tmin'):
        for lead in range(8):
            rows=[r for r in cases if r['variable']==variable and (lead==0 or r['lead_days']==lead)]
            if not rows:continue
            group=dict(variable=variable,lead_days=lead,n_dates=len({r['valid_date'] for r in rows}))
            truth=[r['observed'] for r in rows];dates=[r['valid_date'] for r in rows]
            for product in PRODUCTS:scores.append(group|dict(product=product)|metrics([r[product] for r in rows],truth))
            for contrast in ('nearest_minus_hko_ae','bilinear_minus_hko_ae','bilinear_minus_nearest_ae'):
                differences=[r[contrast] for r in rows];lo,hi=ci(differences,dates);a,b=ci(differences,dates,14)
                contrasts.append(group|dict(contrast=contrast,n=len(rows),delta_mae=float(np.mean(differences)),ci7_low=lo,ci7_high=hi,ci14_low=a,ci14_high=b))
            for product in ('nearest','bilinear'):
                full=metrics([r[product] for r in rows],truth);sampled=metrics([r[product+'_sampled'] for r in rows],truth)
                temporal.append(group|dict(product=product,n=len(rows),full_hkt_window_proxy_mae=full['mae'],native_sample_only_mae=sampled['mae'],
                    mean_abs_midnight_effect=float(np.mean([abs(r[product]-r[product+'_sampled']) for r in rows])),
                    mean_abs_interpolation_order_effect=float(np.mean([abs(r['bilinear_extrema_first_diagnostic']-r['bilinear']) for r in rows])) if product=='bilinear' else 0.,
                    native_interval_conditional_mae_lower=float(np.mean([r['nearest_native_conditional_ae_lower'] for r in rows])) if product=='nearest' else None,
                    native_interval_conditional_mae_upper=float(np.mean([r['nearest_native_conditional_ae_upper'] for r in rows])) if product=='nearest' else None))
    return scores,contrasts,temporal


def revisions(cases):
    paths=defaultdict(dict)
    for r in cases:paths[(r['variable'],r['valid_date'])][r['lead_days']]=r
    pairs=[];summaries=[];comparisons=[]
    for (variable,target),path in sorted(paths.items()):
        for lead in range(1,7):
            if lead not in path or lead+1 not in path:continue
            old,new=path[lead+1],path[lead]
            row=dict(variable=variable,valid_date=target,new_lead=lead,old_lead=lead+1,
                old_cutoff_utc=old['cutoff_utc'],new_cutoff_utc=new['cutoff_utc'],
                old_hko_issue_id=old['hko_issue_id'],new_hko_issue_id=new['hko_issue_id'],
                old_gfs_run_utc=old['gfs_run_utc'],new_gfs_run_utc=new['gfs_run_utc'],observed=new['observed'])
            for product in PRODUCTS:
                row.update({product+'_old':old[product],product+'_new':new[product],product+'_delta':new[product]-old[product],
                    product+'_gain':abs(old[product]-new['observed'])-abs(new[product]-new['observed'])})
            pairs.append(row)
    for variable in ('tmax','tmin'):
        for lead in range(7):
            rows=[r for r in pairs if r['variable']==variable and (lead==0 or r['new_lead']==lead)]
            if not rows:continue
            dates=[r['valid_date'] for r in rows];group=dict(variable=variable,new_lead=lead,n_pairs=len(rows),n_dates=len(set(dates)))
            for product in PRODUCTS:
                change=np.array([r[product+'_delta'] for r in rows]);gain=np.array([r[product+'_gain'] for r in rows]);changed=abs(change)>1e-10;material=abs(change)>=1-1e-10
                lo,hi=ci(gain,dates)
                rounded_old=np.sign([r[product+'_old'] for r in rows])*np.floor(np.abs([r[product+'_old'] for r in rows])+.5)
                rounded_new=np.sign([r[product+'_new'] for r in rows])*np.floor(np.abs([r[product+'_new'] for r in rows])+.5)
                summaries.append(group|dict(product=product,n_changed=int(changed.sum()),n_material=int(material.sum()),
                    revision_rate_pct=float(changed.mean()*100),material_revision_rate_pct=float(material.mean()*100),
                    rounded_revision_rate_pct=float(np.mean(rounded_old!=rounded_new)*100),
                    mean_absolute_change_c=float(abs(change).mean()),mean_revision_gain_c=float(gain.mean()),ci7_low=lo,ci7_high=hi,
                    improvement_pct_all=float((gain>1e-10).mean()*100),worsening_pct_all=float((gain< -1e-10).mean()*100),
                    useful_changed_pct=float((gain[changed]>1e-10).mean()*100) if changed.any() else None,
                    useful_material_pct=float((gain[material]>1e-10).mean()*100) if material.any() else None))
            for a,b in (('nearest','hko'),('bilinear','hko'),('bilinear','nearest')):
                diff=[r[a+'_gain']-r[b+'_gain'] for r in rows];lo,hi=ci(diff,dates);lo14,hi14=ci(diff,dates,14)
                comparisons.append(group|dict(contrast=a+'_minus_'+b,delta_gain_c=float(np.mean(diff)),ci7_low=lo,ci7_high=hi,ci14_low=lo14,ci14_high=hi14))
    return pairs,summaries,comparisons


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--allow-partial',action='store_true');args=p.parse_args()
    hko,records,sources,missing=load()
    if abs(float(hko['station'][0]['latitude'])-HQ[0])>1e-9 or abs(float(hko['station'][0]['longitude'])-HQ[1])>1e-9:
        raise ValueError('HQ coordinates differ from the frozen four-cell extraction contract')
    if missing and not args.allow_partial:raise ValueError(f'Acquisition incomplete: {len(missing)} missing runs')
    cases,knots,excluded,selections,coverage=make_cases(hko,records)
    scores,contrasts,temporal=summarize(cases);pairs,updates,revision_contrasts=revisions(cases)
    for name,rows in [('cases.csv',cases),('window_knots.csv',knots),('source_points.csv',sources),('excluded_cases.csv',excluded),
                      ('vintage_selection.csv',selections),('scores.csv',scores),('spatial_contrasts.csv',contrasts),
                      ('temporal_diagnostics.csv',temporal),('revision_pairs.csv',pairs),('revision_summary.csv',updates),('revision_contrasts.csv',revision_contrasts)]:csv_out(name,rows)
    csv_out('native_interval_inputs.csv',[{k:v.isoformat() if isinstance(v,datetime) else v for k,v in r.items()} for r in hko['gfs_native_extrema']])
    controls={(r['run_time_utc'].astimezone(UTC).date(),r['forecast_hour']):float(r['temperature_c']) for r in hko['gfs_nearest_control']}
    mismatches=[(s['run_time_utc'],s['forecast_hour']) for s in sources if abs(s['cell_se_c']-controls[(datetime.fromisoformat(s['run_time_utc']).date(),s['forecast_hour'])])>1e-10]
    missing_pct={v:100*(1-coverage.get(v+'_paired',0)/2555) for v in ('tmax','tmin')}
    meta=dict(valid_day_definition='HKT [00:00, next 00:00)',target_start=str(START),target_end_exclusive=str(END),
        hko_forecast_selection='latest bulletin and RSS <= decision-date 14:00 HKT; retrospective timestamp proxy',
        gfs_forecast_selection='00 UTC initialization on target_date minus calendar lead',
        valid_window_start_is_not_forecast_selection_cutoff=True,database_writes=False,database_read_only=hko['database_read_only'],
        station=hko['station'][0],gfs_height_m=2,hko_measurement_height_m=None,grid_corners=CORNERS,bilinear_weights=weights().tolist(),
        nearest_grid=CORNERS[1],gfs_runs=len(records),gfs_sources=len(sources),expected_gfs_runs=371,expected_gfs_sources=21518,
        missing_runs=missing,coverage=coverage,forecast_pair_missingness_pct=missing_pct,
        missingness_30pct_gate_passed=all(p<30 for p in missing_pct.values()),
        verified_common_operational_cases=0,operational_availability_evidence_complete=False,exact_native_daily_extrema=False,
        full_year_unqualified_superiority_claim_allowed=False,
        daily_temperature_definition='Extrema of spatially aligned piecewise-linear TMP trajectory restricted to full HKT natural day; temporal proxy',
        independently_imported_nearest_controls=len(sources),nearest_control_mismatches=len(mismatches),
        bootstrap=dict(replicates=2000,seed=3522,block_days=7,sensitivity_block_days=14,unit='calendar target date, all leads/products together'),
        hko_snapshot_sha256=hashlib.sha256((HERE/'cache/hko_snapshot.json.gz').read_bytes()).hexdigest(),
        code_sha256=hashlib.sha256((HERE/'run_analysis.py').read_bytes()+(HERE/'methods.py').read_bytes()).hexdigest(),
        output_hashes={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ('cases.csv','window_knots.csv','source_points.csv','native_interval_inputs.csv','scores.csv','spatial_contrasts.csv','revision_pairs.csv','revision_summary.csv','revision_contrasts.csv','vintage_selection.csv','temporal_diagnostics.csv','excluded_cases.csv')})
    dump('run_metadata.json',meta)
    print(json.dumps(dict(cases=len(cases),missing_runs=len(missing),coverage=coverage,nearest_control_mismatches=len(mismatches),
        pooled_scores=[r for r in scores if r['lead_days']==0],spatial_contrasts=[r for r in contrasts if r['lead_days']==0],
        pooled_updates=[r for r in updates if r['new_lead']==0]),indent=2,default=str))


if __name__=='__main__':
    try:main()
    except Exception as e:
        print(json.dumps(dict(error_type=type(e).__name__,locations=[(Path(f.filename).name,f.lineno) for f in traceback.extract_tb(e.__traceback__)])),file=sys.stderr);sys.exit(1)
