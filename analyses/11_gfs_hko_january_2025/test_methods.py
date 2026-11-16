import unittest
from datetime import date,datetime,timedelta,timezone
from methods import (UTC,HKT,select_run,select_hko,reconstruct,union_hours,
                     error_bounds,block_ci,revision_summary)


class MethodTests(unittest.TestCase):
    def test_latest_available_cycle_changes_with_delay(self):
        cutoff=datetime(2025,1,1,20,tzinfo=HKT)
        runs=[datetime(2025,1,1,h,tzinfo=UTC) for h in (0,6,12,18)]
        self.assertEqual(select_run(runs,cutoff,6).hour,6)
        self.assertEqual(select_run(runs,cutoff,8).hour,0)
        self.assertNotEqual(select_run(runs,cutoff,0).hour,18)

    def test_issue_publication_must_also_precede_cutoff(self):
        rows=[dict(forecast_issue_id=1,bulletin_time_hkt=datetime(2025,1,1,19),
                   published_time_utc=datetime(2025,1,1,11,tzinfo=UTC)),
              dict(forecast_issue_id=2,bulletin_time_hkt=datetime(2025,1,1,19,50),
                   published_time_utc=datetime(2025,1,1,12,10,tzinfo=UTC))]
        self.assertEqual(select_hko(rows,datetime(2025,1,1,20,tzinfo=HKT))['forecast_issue_id'],1)

    def test_overlapping_intervals_are_not_double_counted(self):
        start=datetime(2025,1,1,tzinfo=UTC)
        rows=[dict(interval_start_utc=start,valid_time_utc=start+timedelta(hours=6)),
              dict(interval_start_utc=start+timedelta(hours=3),valid_time_utc=start+timedelta(hours=9))]
        self.assertEqual(union_hours(rows,start,start+timedelta(days=1)),9)

    def test_error_envelope_not_used_as_outcome_chosen_forecast(self):
        self.assertEqual(error_bounds(18,20,19),(0,1))
        self.assertEqual(error_bounds(18,20,22),(2,4))

    def test_calendar_bootstrap_keeps_constant_difference(self):
        dates=[date(2025,1,d) for d in range(1,32) for _ in range(7)]
        self.assertEqual(block_ci([2]*len(dates),dates,repetitions=40),(2.,2.))

    def test_revision_denominators_and_precision(self):
        rows=[]
        for lead,value in zip(range(7,0,-1),(20,20.01,20.02,20.03,20.04,20.05,20.06)):
            rows.append(dict(variable='tmax',valid_date=date(2025,1,8),lead_days=lead,
                             decision_date=date(2025,1,8)-timedelta(days=lead),gfs=value,observed=21))
        summary,pairs,ffi=revision_summary(rows,'gfs')
        pooled=next(r for r in summary if r['later_lead']==0)
        self.assertEqual(pooled['n_pairs'],6)
        self.assertEqual(pooled['revision_rate_pct'],100)
        self.assertEqual(pooled['material_revision_rate_pct'],0)
        self.assertAlmostEqual(ffi[0]['ffi'],0)


if __name__=='__main__':unittest.main()
