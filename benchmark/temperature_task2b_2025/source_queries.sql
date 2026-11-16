-- station
SELECT station_code,station_name,latitude,longitude,elevation_m FROM project.hko_station WHERE station_code='HKO';

-- forecasts
SELECT f.forecast_issue_id,i.source_file_id,i.bulletin_time_hkt,i.published_time_utc,
 s.retrieved_at_utc,s.relative_path,f.valid_date,f.lead_days,f.forecast_tmax_c,f.forecast_tmin_c
 FROM project.hko_forecast_daily f JOIN project.hko_forecast_issue i USING(forecast_issue_id)
 JOIN project.hko_source_file s USING(source_file_id)
 WHERE f.valid_date>=DATE '2025-01-01' AND f.valid_date<DATE '2026-01-01' AND f.lead_days BETWEEN 1 AND 9
 ORDER BY f.valid_date,i.bulletin_time_hkt,i.forecast_issue_id;

-- observations
SELECT o.observation_series_id,s.series_code,o.observation_date,o.value_text,o.value_numeric,o.data_completeness
 FROM project.hko_daily_observation o JOIN project.hko_observation_series s USING(observation_series_id)
 WHERE s.series_code IN ('obs_hko_daily_tmax','obs_hko_daily_tmin')
 AND o.observation_date>=DATE '2025-01-01' AND o.observation_date<DATE '2026-01-01' ORDER BY 1,3;

-- gfs_nearest_control
SELECT s.run_time_utc,s.forecast_hour,t.temperature_c,t.grid_latitude,t.grid_longitude
 FROM project.external_model_temperature t JOIN project.external_model_source s USING(source_id)
 WHERE s.model='GFS' AND s.product='pgrb2.0p25' AND t.station_code='HKO' AND t.short_name='2t'
 AND s.run_time_utc>=TIMESTAMPTZ '2024-12-25 00:00:00+00'
 AND s.run_time_utc<TIMESTAMPTZ '2025-12-31 00:00:00+00'
 AND EXTRACT(HOUR FROM s.run_time_utc AT TIME ZONE 'UTC')=0 AND s.forecast_hour BETWEEN 15 AND 186
 ORDER BY 1,2;

-- gfs_native_extrema
SELECT s.run_time_utc,s.forecast_hour,t.short_name,t.interval_start_utc,t.valid_time_utc,t.temperature_c,
 (s.manifest->'grib_message_metadata'->(t.message_number-1)->>'quantization_step_k')::float8 AS packing_step_c
 FROM project.external_model_temperature t JOIN project.external_model_source s USING(source_id)
 WHERE s.model='GFS' AND s.product='pgrb2.0p25' AND t.station_code='HKO' AND t.short_name IN ('tmax','tmin')
 AND s.run_time_utc>=TIMESTAMPTZ '2024-12-25 00:00:00+00' AND s.run_time_utc<TIMESTAMPTZ '2025-12-31 00:00:00+00'
 AND EXTRACT(HOUR FROM s.run_time_utc AT TIME ZONE 'UTC')=0 ORDER BY 1,2,3;