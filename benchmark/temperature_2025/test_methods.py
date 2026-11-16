import unittest
from datetime import date,datetime,timedelta
from annual_methods import UTC,HKT,union_hours,reconstruct,error_bounds,revision,rounded


class AnnualMethodsTests(unittest.TestCase):
    def test_union_does_not_count_overlap_twice(self):
        t=datetime(2025,1,1,tzinfo=UTC)
        self.assertEqual(union_hours([(t,t+timedelta(hours=6)),(t+timedelta(hours=3),t+timedelta(hours=9))],t,t+timedelta(hours=24)),9)

    def test_cross_midnight_extreme_is_only_an_outer_bound(self):
        day=date(2025,1,2);start=datetime(2025,1,2,tzinfo=HKT).astimezone(UTC);rows=[]
        for h in range(-1,27,3):
            end=start+timedelta(hours=h)
            rows.append(dict(short_name='tmax',interval_start_utc=end-timedelta(hours=3),valid_time_utc=end,
                             temperature_c=40. if h==2 else 20.,packing_step_c=.01,source_id=str(h)))
            rows.append(dict(short_name='2t',interval_start_utc=end,valid_time_utc=end,temperature_c=19.))
        result=reconstruct(rows,day,'tmax')
        self.assertAlmostEqual(result['gfs_lower'],19.98);self.assertAlmostEqual(result['gfs_upper'],40.02)
        self.assertIsNone(reconstruct(rows[:-3],day,'tmax'))

    def test_zero_error_inside_envelope_is_a_bound(self):
        self.assertEqual(error_bounds(19.,21.,20.),(0.,1.))
        self.assertEqual(error_bounds(19.,21.,23.),(2.,4.))

    def test_updating_can_worsen_or_leave_error_tied(self):
        old=dict(valid_date=date(2025,1,1),variable='tmax',observed=20.,hko=19.,gfs=19.,gfs_lower=18.9,gfs_upper=19.1)
        new=old|dict(hko=21.,gfs=22.,gfs_lower=21.9,gfs_upper=22.1)
        r=revision(old,new)
        self.assertEqual(r['hko_delta'],2.);self.assertEqual(r['hko_benefit'],0.)
        self.assertEqual(r['gfs_benefit'],-1.)
        self.assertLessEqual(r['gfs_benefit_lower'],-1.);self.assertGreaterEqual(r['gfs_benefit_upper'],-1.)
        with self.assertRaises(ValueError):revision(old,new|dict(variable='tmin'))

    def test_common_precision_uses_documented_half_up(self):
        self.assertEqual(rounded(20.5),21.);self.assertEqual(rounded(-.5),-1.)


if __name__=='__main__':unittest.main()
