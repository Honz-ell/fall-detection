#!/usr/bin/env python3
"""Dự đoán NGÃ trên các cửa sổ và ghi kết quả.

Ba chế độ:
  1) `--from-csv`     : đọc CSV FallAllD → cửa sổ → dự đoán → in đánh giá (offline, để kiểm thử).
  2) `--input-jsonl`  : đọc file JSONL các cửa sổ (mỗi dòng có đủ đặc trưng) → ghi JSONL kết quả.
  3) mặc định (poll)  : đọc cửa sổ mới từ PostgreSQL `fall_window_aggregates`
                       → ghi `fall_predictions`; nếu ngã thì ghi `fall_alerts`.

Ví dụ:
    python scorer/score_fall.py --from-csv --data ../data/fallalld_wrist_sample.csv \
        --model models/fall_rf.joblib
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fall.features import FEATURE_COLUMNS  # noqa: E402
from fall.windows import iter_window_records  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Chấm điểm/phân loại ngã theo cửa sổ.")
    p.add_argument("--model", type=Path, default=Path("models/fall_rf.joblib"))
    p.add_argument("--data", type=Path, help="CSV FallAllD (dùng với --from-csv).")
    p.add_argument("--input-jsonl", type=Path, help="File JSONL các cửa sổ đầu vào.")
    p.add_argument("--output-jsonl", type=Path, help="Ghi kết quả ra JSONL.")
    p.add_argument("--window-samples", type=int, default=200)
    p.add_argument("--fall-ratio", type=float, default=0.5)
    p.add_argument("--threshold", type=float, default=0.5)
    p.add_argument("--postgres-url", default="postgresql://falld:fall_dev_password@localhost:5432/falldetect")
    p.add_argument("--limit", type=int, default=500, help="Số cửa sổ tối đa mỗi lần poll.")
    return p.parse_args()


def load_model(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy model: {path}. Chạy train/train_fall_model.py trước.")
    return joblib.load(path)


def predict(model, records: list[dict], threshold: float) -> list[dict]:
    if not records:
        return []
    matrix = np.asarray([[float(r.get(name, 0.0)) for name in FEATURE_COLUMNS] for r in records])
    proba = model.predict_proba(matrix)[:, 1]
    results = []
    for record, score in zip(records, proba):
        results.append(
            {
                "device_id": record.get("device_id", "WRIST-01"),
                "window_start": record.get("window_start"),
                "prediction": "FALL" if score >= threshold else "ADL",
                "score": round(float(score), 4),
                "model_version": record.get("model_version", "rf-v1"),
            }
        )
    return results


def evaluate(results: list[dict], labels: list[int]) -> None:
    y_true = np.asarray(labels)
    y_pred = np.asarray([1 if r["prediction"] == "FALL" else 0 for r in results])
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    print(f"TN={tn} FP={fp} FN={fn} TP={tp}")
    print(f"Precision={precision:.4f} Recall={recall:.4f} F1={f1:.4f}")


def run_from_csv(args: argparse.Namespace, model) -> int:
    import pandas as pd

    dtypes = {
        "acc_x": "float32", "acc_y": "float32", "acc_z": "float32",
        "gyro_x": "float32", "gyro_y": "float32", "gyro_z": "float32",
        "label": "int8",
    }
    frame = pd.read_csv(
        args.data, usecols=list(dtypes), dtype=dtypes, low_memory=False
    ).reset_index(drop=True)
    frame["sample_index"] = np.arange(len(frame))
    records = list(iter_window_records(frame, args.window_samples, args.fall_ratio))
    results = predict(model, records, args.threshold)
    labels = [r["label"] for r in records]
    print(f"Số cửa sổ: {len(records):,}")
    evaluate(results, labels)
    falls = [r for r in results if r["prediction"] == "FALL"]
    print(f"Số cửa sổ báo NGÃ: {len(falls):,}")
    if args.output_jsonl:
        args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.output_jsonl.open("w", encoding="utf-8") as fh:
            for record, result in zip(records, results):
                fh.write(json.dumps({**record, **result}, separators=(",", ":")) + "\n")
        print(f"Đã ghi: {args.output_jsonl}")
    return 0


def run_jsonl(args: argparse.Namespace, model) -> int:
    records = [json.loads(line) for line in args.input_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    results = predict(model, records, args.threshold)
    if args.output_jsonl:
        args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with args.output_jsonl.open("w", encoding="utf-8") as fh:
            for result in results:
                fh.write(json.dumps(result, separators=(",", ":")) + "\n")
    else:
        for result in results:
            print(json.dumps(result, ensure_ascii=False))
    return 0


def run_poll(args: argparse.Namespace, model) -> int:
    try:
        import psycopg
    except ImportError:
        print("Thiếu psycopg: pip install 'psycopg[binary]'")
        return 2
    columns = ", ".join(["id", "device_id", "window_start"] + FEATURE_COLUMNS)
    cursor = None
    last_id = 0
    print(f"Đang poll PostgreSQL cho cửa sổ mới (model={args.model})...")
    try:
        with psycopg.connect(args.postgres_url, connect_timeout=5) as conn:
            while True:
                cursor = conn.execute(
                    f"SELECT {columns} FROM fall_window_aggregates WHERE id > %s "
                    f"ORDER BY id LIMIT %s",
                    (last_id, args.limit),
                )
                rows = cursor.fetchall()
                if not rows:
                    conn.commit()
                    import time
                    time.sleep(2)
                    continue
                records = [dict(zip(["id", "device_id", "window_start"] + FEATURE_COLUMNS, row)) for row in rows]
                results = predict(model, records, args.threshold)
                for record, result in zip(records, results):
                    last_id = max(last_id, int(record["id"]))
                    conn.execute(
                        "INSERT INTO fall_predictions (device_id, window_start, prediction, score, model_version) "
                        "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (device_id, window_start) DO UPDATE "
                        "SET prediction=EXCLUDED.prediction, score=EXCLUDED.score, created_at=NOW()",
                        (result["device_id"], record["window_start"], result["prediction"],
                         result["score"], result["model_version"]),
                    )
                    if result["prediction"] == "FALL":
                        conn.execute(
                            "INSERT INTO fall_alerts (device_id, window_start, score) VALUES (%s,%s,%s)",
                            (result["device_id"], record["window_start"], result["score"]),
                        )
                        print(f"⚠️  NGÃ: {result['device_id']} @ {record['window_start']} score={result['score']}")
                conn.commit()
    except KeyboardInterrupt:
        print("\nDừng poll.")
    return 0


def main() -> int:
    args = parse_args()
    model = load_model(args.model)
    if args.data:
        # tương thích: --data ngầm hiểu là chế độ offline
        return run_from_csv(args, model)
    if args.input_jsonl:
        return run_jsonl(args, model)
    return run_poll(args, model)


if __name__ == "__main__":
    raise SystemExit(main())
