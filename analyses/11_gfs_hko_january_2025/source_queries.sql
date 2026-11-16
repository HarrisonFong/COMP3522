-- station
SELECT station_code,station_name,latitude,longitude,elevation_m FROM project.hko_station WHERE station_code='HKO';

-- catalog
SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='project' AND table_name IN ('external_model_source','external_model_temperature','hko_forecast_daily','hko_forecast_issue') ORDER BY table_name,ordinal_position;

-- gfs
SELECT s.source_id,s.run_time_utc,s.forecast_hour,s.subset_sha256,
 s.manifest->'grib_message_metadata' AS grib_metadata,
 s.manifest->>'availability_time_utc' AS availability_time_utc,
 t.message_number,t.short_name,t.step_type,t.interval_start_utc,t.valid_time_utc,t.temperature_c,
 t.grid_latitude,t.grid_longitude,t.grid_distance_km,t.target_latitude,t.target_longitude
 FROM project.external_model_source s JOIN project.external_model_temperature t USING(source_id)
 WHERE s.model='GFS' AND s.product='pgrb2.0p25' AND t.station_code='HKO'
 AND s.run_time_utc >= %(run_start)s AND s.run_time_utc < %(run_end)s
 ORDER BY s.run_time_utc,s.forecast_hour,t.message_number;

-- forecasts
SELECT f.forecast_issue_id,i.source_file_id,i.bulletin_time_hkt,i.published_time_utc,
 f.valid_date,f.lead_days,f.forecast_tmin_c,f.forecast_tmax_c,f.forecast_rh_min_pct,
 f.forecast_rh_max_pct,f.psr,f.weather,i.general_situation
 FROM project.hko_forecast_daily f JOIN project.hko_forecast_issue i USING(forecast_issue_id)
 WHERE f.valid_date >= %(start)s AND f.valid_date < %(end)s
 AND f.lead_days BETWEEN 1 AND 9
 ORDER BY f.valid_date,i.bulletin_time_hkt,f.forecast_issue_id;

-- observations
SELECT o.observation_series_id,s.series_code,o.observation_date,
 o.value_numeric,o.value_text,o.data_completeness FROM project.hko_daily_observation o
 JOIN project.hko_observation_series s USING(observation_series_id)
 WHERE o.observation_date >= DATE '2024-12-23' AND o.observation_date < %(end)s
 AND (s.series_code IN ('obs_hko_daily_tmax','obs_hko_daily_tmin','obs_hko_daily_rainfall')
      OR o.observation_series_id=ANY(%(rain_ids)s))
 ORDER BY o.observation_series_id,o.observation_date;

-- rh_reports
SELECT report_id,report_date,bulletin_date,bulletin_time,
 report_json->>'ReportTimeInfoDate' AS source_observation_date,
 report_json->>'HKOReadingsMinRH' AS observed_rh_min_text,
 report_json->>'HKOReadingsMaxRH' AS observed_rh_max_text,
 report_json->>'NoteDesc3' AS source_quality_note
 FROM project.hko_multistation_report WHERE report_date >= %(start)s AND report_date < %(end)s
 ORDER BY report_date;

-- climate
WITH h AS (
 SELECT s.series_code,o.value_numeric,
 make_date(2000,EXTRACT(MONTH FROM o.observation_date)::int,EXTRACT(DAY FROM o.observation_date)::int)-DATE '2000-01-01' AS ref
 FROM project.hko_daily_observation o JOIN project.hko_observation_series s USING(observation_series_id)
 WHERE s.series_code IN ('obs_hko_daily_tmax','obs_hko_daily_tmin')
 AND o.observation_date >= DATE '1991-01-01' AND o.observation_date < DATE '2021-01-01'
 AND o.value_numeric IS NOT NULL AND o.data_completeness='C'), d AS (
 SELECT target::date AS valid_date,make_date(2000,1,EXTRACT(DAY FROM target)::int)-DATE '2000-01-01' AS ref
 FROM generate_series(%(start)s::timestamp,%(end)s::timestamp-INTERVAL '1 day',INTERVAL '1 day') target)
 SELECT d.valid_date,h.series_code,avg(h.value_numeric) AS climatology_mean,count(*) AS history_n
 FROM d JOIN h ON LEAST(abs(d.ref-h.ref),366-abs(d.ref-h.ref))<=2
 GROUP BY d.valid_date,h.series_code ORDER BY 1,2;