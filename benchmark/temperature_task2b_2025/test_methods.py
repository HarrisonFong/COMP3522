import unittest
from datetime import date,datetime,timedelta
import numpy as np
from methods import HQ,CORNERS,UTC,HKT,weights,day_window,full_day,select_hko


class AlignmentTests(unittest.TestCase):
    def test_hkt_midnight_converts_to_previous_utc_16(self):
        a,b=day_window(date(2025,1,1))
        self.assertEqual(a,datetime(2024,12,31,16,tzinfo=UTC))
        self.assertEqual(b,datetime(2025,1,1,16,tzinfo=UTC));self.assertEqual((b-a).total_seconds(),86400)

    def test_bilinear_reproduces_plane_and_rejects_extrapolation(self):
        values=np.array([2*y+3*x for y,x in CORNERS])
        self.assertAlmostEqual(float(values@weights()),2*HQ[0]+3*HQ[1])
        self.assertAlmostEqual(float(weights().sum()),1)
        with self.assertRaises(ValueError):weights(23,114.1)

    def test_interpolate_before_extrema_not_after(self):
        record=dict(hours=[15,18,21,24,27,30,33,36,39,42],sources=[])
        for i,h in enumerate(record['hours']):
            # Peaks at different corners occur at different times.
            values=[0,0,0,0];values[i%4]=20
            record['sources'].append(dict(values_c=values))
        out,knots=full_day(datetime(2024,12,31,tzinfo=UTC),record,date(2025,1,1))
        self.assertEqual(out['window_hours'],24);self.assertEqual(knots[0]['forecast_hour'],16);self.assertEqual(knots[-1]['forecast_hour'],40)
        self.assertLess(out['bilinear_tmax'],out['extrema_first_bilinear_tmax'])
        self.assertEqual(out['native_in_day_count'],8)
        self.assertFalse(out['exact_native_daily_extremum'])

    def test_incomplete_window_is_not_scored(self):
        with self.assertRaises(ValueError):full_day(datetime(2024,12,31,tzinfo=UTC),dict(hours=[18,21,24],sources=[dict(values_c=[20]*4)]*3),date(2025,1,1))

    def test_next_day_interior_peak_is_not_a_target_day_extreme(self):
        hours=list(range(15,187,3));rows=[dict(values_c=[20.]*4) for _ in hours]
        rows[hours.index(45)]=dict(values_c=[60.]*4)
        result,knots=full_day(datetime(2024,12,31,tzinfo=UTC),dict(hours=hours,sources=rows),date(2025,1,1))
        self.assertEqual(result['nearest_tmax'],20.);self.assertEqual(result['bilinear_tmax'],20.)
        self.assertEqual(knots[-1]['forecast_hour'],40.)

    def test_archive_backfill_is_not_historical_availability(self):
        cutoff=datetime(2025,1,1,14,tzinfo=HKT)
        r=dict(bulletin_time_hkt=datetime(2025,1,1,11,30),published_time_utc=datetime(2025,1,1,11,30,tzinfo=HKT),
               retrieved_at_utc=datetime(2026,9,11,tzinfo=UTC),forecast_issue_id=1)
        self.assertIs(select_hko([r],cutoff),r);self.assertIsNone(select_hko([r],cutoff,True))


if __name__=='__main__':unittest.main()
