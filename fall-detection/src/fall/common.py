"""Shared FallAllD-Wrist constants, window features, and alert rules."""
from __future__ import annotations

import math
from typing import Iterable, Mapping

import numpy as np

SAMPLE_RATE_HZ = 238
WINDOW_SECONDS = 2
WINDOW_SAMPLES = SAMPLE_RATE_HZ * WINDOW_SECONDS  # 476
WATERMARK_SECONDS = 4
MIN_WINDOW_FRACTION = 0.90
MIN_WINDOW_SAMPLES = math.ceil(WINDOW_SAMPLES * MIN_WINDOW_FRACTION)  # 429
DEFAULT_FALL_THRESHOLD = 0.70
DEFAULT_ALERT_COOLDOWN_SECONDS = 10
STD_DDOF = 1  # sample standard deviation, matches Spark stddev_samp()

FEATURE_COLUMNS = (
    "acc_mag_mean",
    "acc_mag_std",
    "acc_mag_min",
    "acc_mag_max",
    "acc_mag_range",
    "acc_x_std",
    "acc_y_std",
    "acc_z_std",
    "gyro_mag_mean",
    "gyro_mag_std",
    "gyro_mag_max",
)
SENSOR_COLUMNS = ("acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z")
REQUIRED_CSV_COLUMNS = ("acc_x", "acc_y", "acc_z", "label", "gyro_x", "gyro_y", "gyro_z")


def compute_window_features(samples: Mapping[str, Iterable[float]]) -> dict[str, float]:
    """Compute the canonical 11 features for one window (label is never read here).

    `samples` contains the six sensor arrays. Each standard deviation uses ddof=1.
    """
    acc_x = np.asarray(samples["acc_x"], dtype=np.float64)
    acc_y = np.asarray(samples["acc_y"], dtype=np.float64)
    acc_z = np.asarray(samples["acc_z"], dtype=np.float64)
    gyro_x = np.asarray(samples["gyro_x"], dtype=np.float64)
    gyro_y = np.asarray(samples["gyro_y"], dtype=np.float64)
    gyro_z = np.asarray(samples["gyro_z"], dtype=np.float64)
    if len(acc_x) < 2 or any(len(v) != len(acc_x) for v in (acc_y, acc_z, gyro_x, gyro_y, gyro_z)):
        raise ValueError("A feature window needs at least 2 aligned samples per sensor axis")

    acc_mag = np.sqrt(acc_x * acc_x + acc_y * acc_y + acc_z * acc_z)
    gyro_mag = np.sqrt(gyro_x * gyro_x + gyro_y * gyro_y + gyro_z * gyro_z)
    values = {
        "acc_mag_mean": float(np.mean(acc_mag)),
        "acc_mag_std": float(np.std(acc_mag, ddof=STD_DDOF)),
        "acc_mag_min": float(np.min(acc_mag)),
        "acc_mag_max": float(np.max(acc_mag)),
        "acc_mag_range": float(np.max(acc_mag) - np.min(acc_mag)),
        "acc_x_std": float(np.std(acc_x, ddof=STD_DDOF)),
        "acc_y_std": float(np.std(acc_y, ddof=STD_DDOF)),
        "acc_z_std": float(np.std(acc_z, ddof=STD_DDOF)),
        "gyro_mag_mean": float(np.mean(gyro_mag)),
        "gyro_mag_std": float(np.std(gyro_mag, ddof=STD_DDOF)),
        "gyro_mag_max": float(np.max(gyro_mag)),
    }
    return values


def window_label(labels: Iterable[int | float]) -> int:
    """Return FALL (1) when the window's mean sample label is at least 0.5."""
    values = np.asarray(list(labels), dtype=np.float64)
    if values.size == 0:
        raise ValueError("Cannot label an empty window")
    return int(float(np.mean(values)) >= 0.5)


def is_complete_window(sample_count: int, minimum_fraction: float = MIN_WINDOW_FRACTION) -> bool:
    """Whether a window contains at least the configured share of 476 samples."""
    required = math.ceil(WINDOW_SAMPLES * minimum_fraction)
    return sample_count >= required


def should_create_alert(
    probability: float,
    now_epoch: float,
    last_alert_epoch: float | None,
    threshold: float = DEFAULT_FALL_THRESHOLD,
    cooldown_seconds: float = DEFAULT_ALERT_COOLDOWN_SECONDS,
) -> bool:
    """Apply the shared probability threshold and per-device quiet period."""
    if probability < threshold:
        return False
    if last_alert_epoch is None:
        return True
    return now_epoch - last_alert_epoch >= cooldown_seconds
