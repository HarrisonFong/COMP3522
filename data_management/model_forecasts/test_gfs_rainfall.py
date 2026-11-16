"""Rainfall-specific coverage, interval, conversion and native-decoder checks."""
import unittest
from datetime import date,datetime,timezone
from unittest.mock import MagicMock
import stream_gfs_rainfall as rain


class RainfallTests(unittest.TestCase):
    def test_year_schedule_excludes_only_zero(self):
        items=list(rain.tasks(date(2024,12,24),date(2026,1,1),[0,6,12,18]))
        self.assertEqual(len(items),95488)
        self.assertEqual(len(set(items)),len(items))
        self.assertTrue(all(hour>0 for _,hour in items))

    def test_selects_both_accumulations_not_rate(self):
        index='\n'.join([
            '1:0:d=2025010100:PRATE:surface:9 hour fcst:',
            '2:100:d=2025010100:APCP:surface:6-9 hour acc fcst:',
            '3:200:d=2025010100:APCP:surface:0-9 hour acc fcst:',
            '4:300:d=2025010100:ACPCP:surface:6-9 hour acc fcst:',
        ])
        self.assertEqual([(a,b) for a,b,_ in rain.selected_ranges(index)],[(100,199),(200,299)])
        self.assertEqual(rain.selected_ranges('1:0:d=2025010100:TMP:2 m above ground:anl:'),[])

    def test_amount_conversion_and_bad_values(self):
        self.assertEqual(rain.to_mm(2.,'kg m**-2'),2.)
        self.assertEqual(rain.to_mm(.002,'m'),2.)
        self.assertEqual(rain.to_mm(0.,'mm'),0.)
        for value,unit in [(-1.,'mm'),(float('nan'),'mm'),(float('inf'),'mm'),(1.,'kg m**-2 s**-1')]:
            with self.assertRaises(ValueError):rain.to_mm(value,unit)

    def test_partial_or_missing_accumulation_does_not_resume(self):
        conn=MagicMock();run=datetime(2025,1,1,tzinfo=timezone.utc)
        stations=[dict(station_code='HKO',latitude=22.3,longitude=114.17)]
        conn.execute.return_value.fetchall.return_value=[
            (run,3,stations,'HKO',[1,2],2,True),
            (run,6,stations,'HKO',[1],1,True),
            (run,9,stations,'HKO',[1,2],1,True),
        ]
        self.assertEqual(rain.completed(conn,date(2025,1,1),date(2026,1,1),[0],stations),{(run,3)})

    def test_native_decoder_preserves_duplicate_early_windows(self):
        import eccodes as ec
        gid=ec.codes_grib_new_from_samples('regular_ll_sfc_grib2')
        try:
            for key,value in [('centre','kwbc'),('dataDate',20250101),('dataTime',0),('discipline',0),
                              ('parameterCategory',1),('parameterNumber',8),
                              ('stepType','accum'),('stepUnits',1),('startStep',0),('endStep',3)]:
                ec.codes_set(gid,key,value)
            ec.codes_set_values(gid,[2.]*ec.codes_get(gid,'numberOfDataPoints'))
            message=ec.codes_get_message(gid)
        finally:ec.codes_release(gid)
        run=datetime(2025,1,1,tzinfo=timezone.utc)
        stations=[dict(station_code='TEST',latitude=40.,longitude=10.)]
        lines=['2:100:d=2025010100:APCP:surface:0-3 hour acc fcst:',
               '3:200:d=2025010100:APCP:surface:0-3 hour acc fcst:']
        rows,metadata=rain.decode(message+message,stations,run,3,lines)
        self.assertEqual(len(rows),2)
        self.assertEqual([r['original_message_number'] for r in rows],[2,3])
        self.assertAlmostEqual(rows[0]['precipitation_mm'],2.,places=4)
        self.assertEqual(rows[0]['interval_start_utc'],rows[1]['interval_start_utc'])
        with self.assertRaises(ValueError):rain.decode(message,stations,run,3,lines[:1])
        with self.assertRaises(ValueError):rain.decode(message+message,stations,run,6,lines)


if __name__=='__main__':unittest.main()
