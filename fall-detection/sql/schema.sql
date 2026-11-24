-- FallAllD-Wrist v2 schema. labels remain for evaluation, never model input.
CREATE TABLE IF NOT EXISTS window_features (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    acc_mag_mean DOUBLE PRECISION NOT NULL,
    acc_mag_std DOUBLE PRECISION NOT NULL,
    acc_mag_min DOUBLE PRECISION NOT NULL,
    acc_mag_max DOUBLE PRECISION NOT NULL,
    acc_mag_range DOUBLE PRECISION NOT NULL,
    acc_x_std DOUBLE PRECISION NOT NULL,
    acc_y_std DOUBLE PRECISION NOT NULL,
    acc_z_std DOUBLE PRECISION NOT NULL,
    gyro_mag_mean DOUBLE PRECISION NOT NULL,
    gyro_mag_std DOUBLE PRECISION NOT NULL,
    gyro_mag_max DOUBLE PRECISION NOT NULL,
    label_fraction DOUBLE PRECISION CHECK (label_fraction BETWEEN 0 AND 1),
    spark_batch_id BIGINT NOT NULL DEFAULT 0,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (device_id, window_start)
);
CREATE INDEX IF NOT EXISTS idx_window_features_time ON window_features(window_start DESC);
CREATE INDEX IF NOT EXISTS idx_window_features_device_time ON window_features(device_id, window_start DESC);

CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    prediction TEXT NOT NULL CHECK (prediction IN ('FALL', 'ADL')),
    probability DOUBLE PRECISION NOT NULL CHECK (probability BETWEEN 0 AND 1),
    model_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (device_id, window_start)
);
CREATE INDEX IF NOT EXISTS idx_predictions_time ON predictions(window_start DESC);

CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    probability DOUBLE PRECISION NOT NULL CHECK (probability BETWEEN 0 AND 1),
    model_version TEXT NOT NULL,
    disposition TEXT NOT NULL DEFAULT 'OPEN'
        CHECK (disposition IN ('OPEN', 'FALL_CONFIRMED', 'FALSE_ALARM')),
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    UNIQUE (device_id, window_start)
);
CREATE INDEX IF NOT EXISTS idx_alerts_open_time ON alerts(created_at DESC) WHERE disposition='OPEN';
CREATE INDEX IF NOT EXISTS idx_alerts_device_time ON alerts(device_id, created_at DESC);

CREATE TABLE IF NOT EXISTS model_versions (
    version TEXT PRIMARY KEY,
    model_file TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL,
    feature_columns JSONB NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_model_versions_single_active
    ON model_versions (is_active) WHERE is_active;

CREATE TABLE IF NOT EXISTS fall_devices (
    device_id TEXT PRIMARY KEY,
    display_name TEXT,
    location TEXT,
    assigned_to TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ
);

CREATE OR REPLACE VIEW v_window_status AS
SELECT w.id, w.device_id, w.window_start, w.window_end, w.sample_count,
       w.acc_mag_mean, w.acc_mag_std, w.acc_mag_min, w.acc_mag_max, w.acc_mag_range,
       w.acc_x_std, w.acc_y_std, w.acc_z_std, w.gyro_mag_mean, w.gyro_mag_std, w.gyro_mag_max,
       w.label_fraction,
       p.prediction, p.probability, p.model_version,
       a.id AS alert_id, a.disposition AS alert_status, a.acknowledged, a.created_at AS alert_created_at
FROM window_features w
LEFT JOIN predictions p USING (device_id, window_start)
LEFT JOIN alerts a USING (device_id, window_start);
