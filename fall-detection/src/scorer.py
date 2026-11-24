#!/usr/bin/env python3
"""Poll unscored windows, classify with RF, and create cooldown-protected alerts."""
from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

from fall.common import (
    DEFAULT_ALERT_COOLDOWN_SECONDS, DEFAULT_FALL_THRESHOLD, FEATURE_COLUMNS,
    should_create_alert,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = ROOT / "models" / "rf_fall.joblib"


def probability_fall(model, feature_rows: list[dict]) -> np.ndarray:
    """Predict using only the canonical 11 sensor-derived feature columns."""
    if not feature_rows:
        return np.empty((0,), dtype=np.float64)
    X = np.asarray([[float(row[name]) for name in FEATURE_COLUMNS] for row in feature_rows], dtype=np.float64)
    classes = list(model.classes_)
    if 1 not in classes:
        raise ValueError("Loaded classifier has no FALL class (1)")
    return model.predict_proba(X)[:, classes.index(1)]


def score_once(
    conn, model, threshold: float, cooldown_seconds: float,
    last_alert_by_device: dict[str, float], limit: int = 500,
) -> tuple[int, int]:
    """Score one DB batch; returns (predictions_written, alerts_written)."""
    columns = ",".join(FEATURE_COLUMNS)
    rows = conn.execute(
        f"SELECT w.device_id, w.window_start, {columns} "
        "FROM window_features w LEFT JOIN predictions p "
        "ON p.device_id=w.device_id AND p.window_start=w.window_start "
        "WHERE p.device_id IS NULL ORDER BY w.window_start, w.device_id LIMIT %s FOR UPDATE OF w SKIP LOCKED",
        (limit,),
    ).fetchall()
    if not rows:
        conn.commit()
        return 0, 0
    feature_records = [dict(zip(FEATURE_COLUMNS, row[2:])) for row in rows]
    probabilities = probability_fall(model, feature_records)
    predictions_written = alerts_written = 0
    for row, probability in zip(rows, probabilities):
        device_id, window_start = row[0], row[1]
        prediction = "FALL" if probability >= threshold else "ADL"
        inserted = conn.execute(
            "INSERT INTO predictions (device_id, window_start, prediction, probability, model_version) "
            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (device_id, window_start) DO NOTHING RETURNING id",
            (device_id, window_start, prediction, float(probability), os.environ.get("FALL_MODEL_VERSION", "rf-fall-v1")),
        ).fetchone()
        if inserted is None:
            continue
        predictions_written += 1
        now_epoch = datetime.now(timezone.utc).timestamp()
        last_epoch = last_alert_by_device.get(device_id)
        if should_create_alert(float(probability), now_epoch, last_epoch, threshold, cooldown_seconds):
            conn.execute(
                "INSERT INTO alerts (device_id, window_start, probability, model_version) VALUES (%s, %s, %s, %s)",
                (device_id, window_start, float(probability), os.environ.get("FALL_MODEL_VERSION", "rf-fall-v1")),
            )
            last_alert_by_device[device_id] = now_epoch
            alerts_written += 1
    conn.commit()
    return predictions_written, alerts_written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--postgres-url", default=os.getenv("FALL_POSTGRES_URL", "postgresql://falld:fall_dev_password@localhost:5434/falldetect"))
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    if not args.model.is_file():
        parser.error(f"Model file missing: {args.model}; train it with src/train.py first")
    if args.poll_seconds <= 0 or args.batch_size <= 0:
        parser.error("poll-seconds and batch-size must be positive")

    import psycopg

    threshold = float(os.getenv("FALL_PROB_THRESHOLD", str(DEFAULT_FALL_THRESHOLD)))
    cooldown = float(os.getenv("FALL_ALERT_COOLDOWN_SECONDS", str(DEFAULT_ALERT_COOLDOWN_SECONDS)))
    if not 0 <= threshold <= 1 or cooldown < 0:
        parser.error("FALL_PROB_THRESHOLD must be 0..1 and FALL_ALERT_COOLDOWN_SECONDS nonnegative")
    model = joblib.load(args.model)
    if getattr(model, "n_features_in_", None) != len(FEATURE_COLUMNS):
        parser.error(f"Model expects {getattr(model, 'n_features_in_', '?')} features; pipeline contract has {len(FEATURE_COLUMNS)}")
    last_alert_by_device: dict[str, float] = {}
    with psycopg.connect(args.postgres_url, autocommit=False) as conn:
        previous = conn.execute("SELECT device_id, MAX(created_at) FROM alerts GROUP BY device_id").fetchall()
        for device_id, timestamp in previous:
            if timestamp is not None:
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                last_alert_by_device[device_id] = timestamp.timestamp()
        print(f"Scorer active: threshold={threshold:.2f}, cooldown={cooldown:g}s, model={args.model}")
        while True:
            try:
                count, alert_count = score_once(conn, model, threshold, cooldown, last_alert_by_device, args.batch_size)
                if count:
                    print(f"scored {count} window(s); created {alert_count} alert(s)")
                else:
                    time.sleep(args.poll_seconds)
            except KeyboardInterrupt:
                print("\nScorer stopped")
                break
            except Exception as exc:
                conn.rollback()
                print(f"scorer batch error: {exc}")
                time.sleep(max(args.poll_seconds, 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
