-- PostgreSQL schema cho pipeline phát hiện ngã FallAllD

CREATE TABLE IF NOT EXISTS fall_window_aggregates (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    sample_count BIGINT NOT NULL,
    acc_mag_mean DOUBLE PRECISION NOT NULL,
    acc_mag_std DOUBLE PRECISION NOT NULL,
    acc_mag_max DOUBLE PRECISION NOT NULL,
    acc_mag_min DOUBLE PRECISION NOT NULL,
    acc_x_mean DOUBLE PRECISION NOT NULL,
    acc_y_mean DOUBLE PRECISION NOT NULL,
    acc_z_mean DOUBLE PRECISION NOT NULL,
    gyro_mag_mean DOUBLE PRECISION NOT NULL,
    gyro_mag_std DOUBLE PRECISION NOT NULL,
    gyro_mag_max DOUBLE PRECISION NOT NULL,
    fall_samples BIGINT NOT NULL,
    spark_batch_id BIGINT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (device_id, window_start)
);

CREATE INDEX IF NOT EXISTS idx_fall_windows_time
    ON fall_window_aggregates (window_start DESC);
CREATE INDEX IF NOT EXISTS idx_fall_windows_device_time
    ON fall_window_aggregates (device_id, window_start DESC);
CREATE INDEX IF NOT EXISTS idx_fall_windows_batch
    ON fall_window_aggregates (spark_batch_id);

CREATE TABLE IF NOT EXISTS fall_predictions (
    device_id TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    prediction TEXT NOT NULL CHECK (prediction IN ('FALL', 'ADL')),
    score DOUBLE PRECISION NOT NULL CHECK (score >= 0 AND score <= 1),
    model_version TEXT NOT NULL DEFAULT 'rf-v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (device_id, window_start)
);

CREATE INDEX IF NOT EXISTS idx_fall_predictions_time
    ON fall_predictions (window_start DESC);

CREATE TABLE IF NOT EXISTS fall_alerts (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fall_alerts_unack
    ON fall_alerts (created_at DESC) WHERE NOT acknowledged;

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
