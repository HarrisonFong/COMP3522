-- Authorized GFS rainfall extension. Existing source/temperature/HKO tables
-- remain intact. Apply inside a transaction and refresh the canonical guide.
CREATE TABLE IF NOT EXISTS project.external_model_precipitation (
    source_id uuid NOT NULL REFERENCES project.external_model_source(source_id),
    station_code text NOT NULL REFERENCES project.hko_station(station_code),
    message_number integer NOT NULL CHECK (message_number > 0),
    original_message_number integer NOT NULL CHECK (original_message_number > 0),
    parameter_id integer NOT NULL,
    short_name text NOT NULL,
    parameter_name text NOT NULL,
    step_type text NOT NULL CHECK (step_type = 'accum'),
    interval_start_utc timestamptz NOT NULL,
    valid_time_utc timestamptz NOT NULL,
    target_latitude double precision NOT NULL,
    target_longitude double precision NOT NULL,
    grid_latitude double precision NOT NULL,
    grid_longitude double precision NOT NULL,
    grid_distance_km double precision NOT NULL CHECK (grid_distance_km >= 0),
    extraction_method text NOT NULL CHECK (extraction_method = 'nearest_grid_point'),
    source_value double precision NOT NULL CHECK (source_value >= 0 AND source_value < 'Infinity'::double precision),
    source_unit text NOT NULL,
    precipitation_mm double precision NOT NULL CHECK (precipitation_mm >= 0 AND precipitation_mm < 'Infinity'::double precision),
    PRIMARY KEY (source_id, station_code, message_number),
    CHECK (interval_start_utc < valid_time_utc)
);
CREATE INDEX IF NOT EXISTS external_model_precipitation_valid_time_idx
ON project.external_model_precipitation (valid_time_utc, station_code);
