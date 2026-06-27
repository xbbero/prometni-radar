-- Shema baze za sustav prikupljanja prometnih podataka. PostgreSQL.
-- Sve naredbe su idempotentne (IF NOT EXISTS) pa se mogu pokretati više puta.

CREATE TABLE IF NOT EXISTS route (
    route_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name     TEXT NOT NULL UNIQUE
);

-- Uređeni niz točaka relacije: origin (seq=0), međutočke, destination (zadnji seq).
-- Dionica (leg) nastaje IZMEĐU dvije susjedne točke.
CREATE TABLE IF NOT EXISTS route_point (
    route_id BIGINT  NOT NULL REFERENCES route(route_id) ON DELETE CASCADE,
    seq      INTEGER NOT NULL,
    label    TEXT    NOT NULL,
    lat      DOUBLE PRECISION,
    lng      DOUBLE PRECISION,
    PRIMARY KEY (route_id, seq)
);

-- Jedno mjerenje = jedan API poziv. Sažetak cijele relacije.
CREATE TABLE IF NOT EXISTS measurement (
    measurement_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    route_id           BIGINT NOT NULL REFERENCES route(route_id),
    requested_at_utc   TIMESTAMPTZ NOT NULL,
    departure_utc      TIMESTAMPTZ NOT NULL,
    local_date         DATE    NOT NULL,
    local_time         TEXT    NOT NULL,
    weekday            INTEGER NOT NULL,   -- 0=Pon ... 6=Ned
    hour               INTEGER NOT NULL,
    month              INTEGER NOT NULL,
    year               INTEGER NOT NULL,
    traffic_model      TEXT    NOT NULL,
    routing_preference TEXT    NOT NULL,
    distance_m         INTEGER,
    duration_s         INTEGER,            -- s prometom
    static_duration_s  INTEGER,            -- bez prometa (free-flow / povijesni prosjek)
    delay_s            INTEGER,            -- duration_s - static_duration_s
    raw_json           JSONB               -- cijeli odgovor (za naknadno re-parsiranje)
);

-- Jedna dionica jednog mjerenja.
CREATE TABLE IF NOT EXISTS leg_measurement (
    leg_id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    measurement_id    BIGINT  NOT NULL REFERENCES measurement(measurement_id) ON DELETE CASCADE,
    seq               INTEGER NOT NULL,
    from_label        TEXT    NOT NULL,
    to_label          TEXT    NOT NULL,
    distance_m        INTEGER,
    duration_s        INTEGER,
    static_duration_s INTEGER,
    delay_s           INTEGER
);

-- Blagdani i produženi vikendi.
CREATE TABLE IF NOT EXISTS holiday (
    holiday_date    DATE PRIMARY KEY,
    name            TEXT NOT NULL,
    is_long_weekend INTEGER NOT NULL DEFAULT 0
)
;
CREATE INDEX IF NOT EXISTS idx_meas_route_date ON measurement(route_id, local_date);
CREATE INDEX IF NOT EXISTS idx_meas_wday_hour  ON measurement(route_id, weekday, hour);
CREATE INDEX IF NOT EXISTS idx_meas_month      ON measurement(route_id, month);
CREATE INDEX IF NOT EXISTS idx_leg_meas        ON leg_measurement(measurement_id, seq)
