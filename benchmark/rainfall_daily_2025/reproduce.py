"""Verify the published fixed-CSV workflow results; optionally redraw the clear figure."""
import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def read_csv(name):
    with (HERE/name).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def verify():
    manifest = json.loads((HERE/'publication_manifest.json').read_text(encoding='utf-8'))
    for name, sha in manifest['sha256'].items():
        assert hashlib.sha256((HERE/name).read_bytes()).hexdigest() == sha, name
    rows = read_csv('daily_comparison.csv')
    days = np.array([np.datetime64(r['date_hkt']) for r in rows])
    assert len(rows) == 365 and days[0] == np.datetime64('2025-01-01')
    assert days[-1] == np.datetime64('2025-12-31')
    assert np.all(np.diff(days) == np.timedelta64(1, 'D'))
    def values(key):
        return np.array([float(r[key]) if r[key] else np.nan for r in rows])
    y = values('hq_observed_numeric_mm')
    forecasts = {'GFS_nearest': values('gfs_nearest_mm'),
                 'GFS_bilinear': values('gfs_bilinear_mm'),
                 'HKO_reused': values('hko_original_composite_mm'), 'zero_rain': np.zeros(365)}
    hko = forecasts['HKO_reused']
    trace = np.array([r['hq_observed_text'] == 'Trace' for r in rows])
    common = np.isfinite(y) & np.isfinite(hko)
    assert trace.sum() == 53 and np.isfinite(y).sum() == 312 and common.sum() == 308
    assert np.isfinite(hko).sum() == 360
    assert all(np.isfinite(forecasts[k]).all() for k in ('GFS_nearest', 'GFS_bilinear'))
    windows = read_csv('gfs_valid_windows.csv')
    grouped = defaultdict(list)
    for w in windows:
        start, end = (datetime.fromisoformat(w[k]) for k in ('valid_start_hkt', 'valid_end_hkt'))
        issue = datetime.fromisoformat(w['issue_time_utc'])
        latest = start.astimezone(issue.tzinfo)
        latest = latest.replace(hour=(latest.hour//6)*6, minute=0, second=0, microsecond=0)
        assert issue == latest <= start < end and not w['available_time_utc']
        assert w['selection_basis'] == 'issue_time' and int(w['negative_corner_increments']) == 0
        assert (end-start).total_seconds()/3600 == float(w['duration_hours'])
        assert (start-issue).total_seconds()/3600 == float(w['lead_start_hours'])
        assert (end-issue).total_seconds()/3600 == float(w['lead_end_hours'])
        grouped[w['date_hkt']].append((start, end, w))
    assert len(windows) == 1825 and len({w['issue_time_utc'] for w in windows}) == 1461
    for row in rows:
        segments = grouped[row['date_hkt']]
        assert len(segments) == 5 and sum((b-a).total_seconds() for a, b, _ in segments) == 86400
        assert segments[0][0].hour == 0 and segments[-1][1] == segments[0][0]+timedelta(days=1)
        assert all(a[1] == b[0] for a, b in zip(segments, segments[1:]))
        for method in ('nearest', 'bilinear'):
            totals = [float(w[f'{method}_rainfall_mm']) for _, _, w in segments]
            assert min(totals) >= 0
            assert math.isclose(sum(totals), float(row[f'gfs_{method}_mm']), abs_tol=1e-9)
    rng = np.random.default_rng(3522)
    blocks = rng.integers(0, 365, (2000, math.ceil(365/7)))
    indices = ((blocks[:, :, None]+np.arange(7)) % 365).reshape(2000, -1)[:, :365]
    def ci(loss):
        return np.nanquantile(np.nanmean(loss[indices], axis=1), [.025, .975])
    result = json.loads((HERE/'results.json').read_text(encoding='utf-8'))
    for expected in result['metrics']:
        mask = np.isfinite(y) if expected['scope'] == 'gfs_all_numeric' else common.copy()
        if expected['scope'].startswith('exclude'):
            mask &= days != np.datetime64('2025-05-30')
        error = np.where(mask, forecasts[expected['product']]-y, np.nan)
        delta = np.where(mask & np.isfinite(hko), abs(error)-abs(hko-y), np.nan)
        assert int(mask.sum()) == expected['n']
        for key, actual in [('mae', np.nanmean(abs(error))), ('rmse', np.sqrt(np.nanmean(error**2))),
                            ('bias', np.nanmean(error)), ('mae_minus_hko', np.nanmean(delta)),
                            ('mae_ci', ci(abs(error))), ('paired_difference_ci', ci(delta))]:
            np.testing.assert_allclose(actual, expected[key], rtol=0, atol=1e-10, err_msg=key)
    difference = np.where(common, abs(forecasts['GFS_bilinear']-y)-abs(forecasts['GFS_nearest']-y), np.nan)
    np.testing.assert_allclose(np.nanmean(difference), result['bilinear_minus_nearest_common_mae'], atol=1e-10)
    np.testing.assert_allclose(ci(difference), result['bilinear_minus_nearest_common_mae_ci'], atol=1e-10)
    for expected in result['common_trace_inclusive_bounds']:
        forecast = forecasts[expected['product']]
        lower = np.where(trace, np.maximum(forecast-.05, 0), abs(forecast-y))
        upper = np.where(trace, np.maximum(abs(forecast), abs(forecast-.05)), abs(forecast-y))
        eligible = np.isfinite(hko)
        np.testing.assert_allclose([lower[eligible].mean(), upper[eligible].mean()],
                                   expected['mae_identification_bounds'], atol=1e-10)
    print('PASS: file hashes; 365 dates; 1,825 disjoint windows; all metrics, bootstrap CIs and Trace bounds.')
    return days, y, forecasts


def plot(days, observed, forecasts):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    curves = [('HKO successive nowcasts', 'HKO_reused', '#0072B2'),
              ('GFS successive runs: nearest grid', 'GFS_nearest', '#D55E00'),
              ('GFS successive runs: bilinear interpolation', 'GFS_bilinear', '#009E73')]
    fig, axes = plt.subplots(3, 1, figsize=(15, 10), sharex=True, sharey=True, constrained_layout=True)
    for ax, (label, key, color) in zip(axes, curves):
        assert np.nanmax(forecasts[key]) <= 420 and np.nanmax(observed) <= 420
        ax.plot(days, observed, color='#222222', linestyle=(0, (5, 3)), linewidth=1.3,
                label='HQ observation (numeric days)', zorder=3)
        ax.plot(days, forecasts[key], color=color, linewidth=1.5, label=label, zorder=2)
        count = np.isfinite(forecasts[key]).sum()
        ax.set_title(f'{label}  |  complete forecast days: {count}/365', loc='left',
                     fontsize=12, fontweight='bold', color=color)
        ax.set_ylabel('Daily rainfall (mm)', fontsize=11)
        ax.set_ylim(-8, 420)
        ax.set_yticks([0, 100, 200, 300, 400])
        ax.grid(axis='y', color='#dddddd', linewidth=.7)
        ax.spines[['top', 'right']].set_visible(False)
        ax.legend(loc='upper right', fontsize=10, framealpha=.95)
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator())
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    axes[-1].set_xlim(np.datetime64('2025-01-01'), np.datetime64('2026-01-01'))
    axes[-1].set_xlabel('2025 | HKT daily windows: 00:00-24:00', fontsize=11)
    fig.suptitle('2025 daily rainfall workflows vs HKO Headquarters observation\n'
                 'Same axes in every panel; all source extremes retained.\n'
                 'Trace observations (53 days) and incomplete HKO forecasts (5 days) remain gaps.\n'
                 'Mixed forecast leads; issue time is not verified availability.', fontsize=12)
    target = HERE/'reproduced_comparison.png'
    fig.savefig(target, dpi=180)
    plt.close(fig)
    print(f'Saved {target.name}; published figures unchanged.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    data = verify()
    if args.plot:
        plot(*data)
