-- station
SELECT station_code,station_name,latitude,longitude,elevation_m FROM project.hko_station WHERE station_code='HKO';

-- catalog
SELECT table_name,column_name,data_type,is_nullable FROM information_schema.columns
 WHERE table_schema='project' AND table_name IN ('external_model_source','external_model_temperature',
 'hko_forecast_daily','hko_forecast_issue','hko_daily_observation') ORDER BY 1,ordinal_position;

-- gfs
SELECT s.source_id,s.run_time_utc,s.forecast_hour,t.message_number,t.short_name,t.step_type,
 t.interval_start_utc,t.valid_time_utc,t.temperature_c,t.grid_latitude,t.grid_longitude,t.grid_distance_km,
 (s.manifest->'grib_message_metadata'->(t.message_number-1)->>'quantization_step_k')::float8 AS packing_step_c,
 s.manifest->>'availability_time_utc' AS historical_availability
 FROM project.external_model_source s JOIN project.external_model_temperature t USING(source_id)
 WHERE s.model='GFS' AND s.product='pgrb2.0p25' AND t.station_code='HKO'
 AND s.run_time_utc >= %(run_start)s AND s.run_time_utc < %(run_end)s
 ORDER BY s.run_time_utc,s.forecast_hour,t.message_number;

-- forecasts
SELECT f.forecast_issue_id,i.source_file_id,i.bulletin_time_hkt,i.published_time_utc,
 f.valid_date,f.lead_days,f.forecast_tmax_c,f.forecast_tmin_c
 FROM project.hko_forecast_daily f JOIN project.hko_forecast_issue i USING(forecast_issue_id)
 WHERE f.valid_date >= %(start)s AND f.valid_date < %(end)s AND f.lead_days BETWEEN 1 AND 9
 ORDER BY f.valid_date,i.bulletin_time_hkt,f.forecast_issue_id;

-- observations
SELECT s.series_code,o.observation_date,o.observation_series_id,
 o.value_numeric,o.value_text,o.data_completeness FROM project.hko_daily_observation o
 JOIN project.hko_observation_series s USING(observation_series_id)
 WHERE s.series_code IN ('obs_hko_daily_tmax','obs_hko_daily_tmin')
 AND o.observation_date >= %(start)s AND o.observation_date < %(end)s ORDER BY 1,2;