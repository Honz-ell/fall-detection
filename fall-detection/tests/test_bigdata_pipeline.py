from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fall.common import (  # noqa: E402
    DEFAULT_ALERT_COOLDOWN_SECONDS, DEFAULT_FALL_THRESHOLD, FEATURE_COLUMNS,
    MIN_WINDOW_SAMPLES, WINDOW_SAMPLES, compute_window_features,
    is_complete_window, should_create_alert, window_label,
)
from make_demo_sample import generate_demo_csv  # noqa: E402
from train import iter_csv_windows, train_model  # noqa: E402
from scorer import probability_fall  # noqa: E402


class FallPipelineOfflineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.csv_path = self.root / "synthetic.csv"
        generate_demo_csv(self.csv_path, windows=40, seed=2026)

    def tearDown(self):
        self.tmp.cleanup()

    def test_contract_window_size_features_and_ddof(self):
        self.assertEqual(WINDOW_SAMPLES, 476)
        self.assertEqual(len(FEATURE_COLUMNS), 11)
        features = compute_window_features({
            "acc_x": [0, 1, 2], "acc_y": [0, 0, 0], "acc_z": [0, 0, 0],
            "gyro_x": [0, 1, 2], "gyro_y": [0, 0, 0], "gyro_z": [0, 0, 0],
        })
        self.assertAlmostEqual(features["acc_x_std"], np.std([0, 1, 2], ddof=1))
        self.assertAlmostEqual(features["acc_mag_std"], np.std([0, 1, 2], ddof=1))
        self.assertEqual(window_label([0, 0, 1, 1]), 1)
        self.assertEqual(window_label([0, 0, 0, 1]), 0)
        self.assertFalse(is_complete_window(MIN_WINDOW_SAMPLES - 1))
        self.assertTrue(is_complete_window(MIN_WINDOW_SAMPLES))

    def test_chunk_reader_never_splits_windows(self):
        rows = list(iter_csv_windows(self.csv_path, chunk_rows=WINDOW_SAMPLES * 3))
        self.assertEqual(len(rows), 40)
        self.assertEqual([label for _, label in rows[:4]], [0, 1, 0, 1])
        with self.assertRaises(ValueError):
            list(iter_csv_windows(self.csv_path, chunk_rows=WINDOW_SAMPLES + 1))

    def test_train_chronologically_and_scorer_uses_only_11_features(self):
        model_path = self.root / "rf_fall.joblib"
        metrics_path = self.root / "metrics.json"
        metrics = train_model(self.csv_path, model_path, metrics_path, chunk_rows=WINDOW_SAMPLES * 4)
        self.assertTrue(model_path.is_file())
        self.assertEqual(metrics["data_origin"], "unknown")
        self.assertEqual(metrics["train_windows"], 32)
        self.assertEqual(metrics["test_windows"], 8)
        self.assertEqual(metrics["n_estimators"], 300)
        self.assertEqual(metrics["std_ddof"], 1)
        self.assertEqual(len(metrics["feature_columns"]), 11)
        model = joblib.load(model_path)
        self.assertEqual(model.n_features_in_, 11)
        rows = list(iter_csv_windows(self.csv_path, chunk_rows=WINDOW_SAMPLES * 4))[:2]
        self.assertEqual(probability_fall(model, [record for record, _ in rows]).shape, (2,))

    def test_threshold_and_per_device_cooldown_rule(self):
        now = 1000.0
        self.assertFalse(should_create_alert(0.69, now, None))
        self.assertTrue(should_create_alert(0.70, now, None))
        self.assertFalse(should_create_alert(0.95, now + 9, now, 0.70, DEFAULT_ALERT_COOLDOWN_SECONDS))
        self.assertTrue(should_create_alert(0.95, now + 10, now, 0.70, DEFAULT_ALERT_COOLDOWN_SECONDS))
        self.assertEqual(DEFAULT_FALL_THRESHOLD, 0.70)

    def test_producer_jsonl_contract_and_aligned_time(self):
        out = self.root / "producer.jsonl"
        result = subprocess.run([
            sys.executable, str(ROOT / "src" / "producer.py"), "--data", str(self.csv_path),
            "--devices", "wrist-a,wrist-b", "--limit", "3", "--speed", "1000",
            "--chunk-rows", str(WINDOW_SAMPLES * 2), "--dry-run", str(out),
        ], text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 6)
        self.assertEqual({r["device_id"] for r in records}, {"wrist-a", "wrist-b"})
        self.assertEqual(records[0]["sample_rate_hz"], 238)
        self.assertTrue(all(set(("acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z", "label")) <= r.keys() for r in records))
        ts = datetime.fromisoformat(records[0]["event_time"].replace("Z", "+00:00"))
        self.assertEqual(ts.timestamp() % 2, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
