#!/usr/bin/env python3
"""Kiểm thử offline đầu-cuối mà không cần Kafka/Spark/PostgreSQL.

Chạy:  python tests/test_offline_pipeline.py --data ../data/fallalld_wrist_sample.csv
Kiểm tra: producer sinh bản ghi hợp lệ, cửa sổ có đủ đặc trưng,
và mô hình đạt recall tối thiểu trên dữ liệu mẫu.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np  # noqa: E402
from fall.console import configure_console  # noqa: E402
from fall.features import FEATURE_COLUMNS  # noqa: E402
from fall.windows import iter_window_records  # noqa: E402


def main() -> int:
    configure_console()
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=ROOT / "data" / "fallalld_wrist_sample.csv")
    ap.add_argument("--model", type=Path, default=ROOT / "models" / "fall_rf.joblib")
    ap.add_argument("--min-recall", type=float, default=0.6)
    args = ap.parse_args()

    if not args.data.is_file():
        print(f"Không tìm thấy dữ liệu: {args.data}")
        return 2
    if not args.model.is_file():
        print("Chưa có model; chạy: python train/train_fall_model.py --data <csv>")
        return 2

    # 1) Producer phải sinh bản ghi hợp lệ
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "sample.jsonl"
        proc = subprocess.run(
            [sys.executable, str(ROOT / "producer" / "produce_fall.py"),
             "--data", str(args.data), "--limit", "50",
             "--dry-run", str(out), "--speed", "1000"],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        lines = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) >= 50, f"Producer chỉ sinh {len(lines)} bản ghi"
    first = next(r for r in lines if r.get("sensor") != "__CONTROL__")
    assert first["schema_version"] == "wearable.fall.v1"
    assert all(key in first for key in ("acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z", "label"))
    print(f"[1/3] Producer OK: {len(lines)} bản ghi, schema đúng.")

    # 2) Cửa sổ có đủ đặc trưng
    import pandas as pd
    frame = pd.read_csv(args.data, low_memory=False)
    records = list(iter_window_records(frame))
    assert records, "Không sinh được cửa sổ nào"
    assert all(name in records[0] for name in FEATURE_COLUMNS)
    print(f"[2/3] Cửa sổ OK: {len(records):,} cửa sổ, đủ {len(FEATURE_COLUMNS)} đặc trưng.")

    # 3) Model đạt recall tối thiểu
    import joblib
    model = joblib.load(args.model)
    matrix = np.asarray([[r[name] for name in FEATURE_COLUMNS] for r in records], dtype=float)
    proba = model.predict_proba(matrix)[:, 1]
    y = np.asarray([r["label"] for r in records])
    pred = (proba >= 0.5).astype(int)
    tp = int(((y == 1) & (pred == 1)).sum())
    fn = int(((y == 1) & (pred == 0)).sum())
    recall = tp / (tp + fn) if tp + fn else 0.0
    assert recall >= args.min_recall, f"Recall {recall:.3f} < {args.min_recall}"
    print(f"[3/3] Model OK: recall={recall:.3f} (>= {args.min_recall}).")
    print("\nTẤT CẢ KIỂM THỬ ĐẠT.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
