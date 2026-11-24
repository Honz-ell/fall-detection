#!/usr/bin/env python3
"""Train the chronological FallAllD Random Forest from a chunked CSV."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterator

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

from fall.common import (
    FEATURE_COLUMNS, REQUIRED_CSV_COLUMNS, SAMPLE_RATE_HZ, WINDOW_SAMPLES,
    WINDOW_SECONDS, compute_window_features, window_label,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "fallalld_processed_wrist-acc-gyro.csv"
DEFAULT_MODEL = ROOT / "models" / "rf_fall.joblib"
DEFAULT_METRICS = ROOT / "models" / "metrics.json"


def iter_csv_windows(
    data_path: str | Path,
    chunk_rows: int = WINDOW_SAMPLES * 200,
    max_windows: int | None = None,
) -> Iterator[tuple[dict[str, float], int]]:
    """Yield whole windows from aligned CSV chunks; never stitch a window across chunks."""
    if chunk_rows <= 0 or chunk_rows % WINDOW_SAMPLES != 0:
        raise ValueError(f"chunk_rows must be a positive multiple of {WINDOW_SAMPLES}")
    dtypes = {name: "float32" for name in REQUIRED_CSV_COLUMNS}
    dtypes["label"] = "int8"
    yielded = 0
    for chunk in pd.read_csv(
        data_path, usecols=list(REQUIRED_CSV_COLUMNS), dtype=dtypes,
        chunksize=chunk_rows, low_memory=False,
    ):
        whole = len(chunk) // WINDOW_SAMPLES
        for i in range(whole):
            start = i * WINDOW_SAMPLES
            window = chunk.iloc[start : start + WINDOW_SAMPLES]
            features = compute_window_features({name: window[name].to_numpy() for name in (
                "acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z"
            )})
            yield features, window_label(window["label"].to_numpy())
            yielded += 1
            if max_windows is not None and yielded >= max_windows:
                return


def train_model(
    data_path: str | Path,
    model_path: str | Path = DEFAULT_MODEL,
    metrics_path: str | Path = DEFAULT_METRICS,
    chunk_rows: int = WINDOW_SAMPLES * 200,
    test_fraction: float = 0.2,
    n_estimators: int = 300,
    random_state: int = 42,
    data_origin: str = "unknown",
) -> dict:
    if not 0.05 <= test_fraction <= 0.5:
        raise ValueError("test_fraction must be between 0.05 and 0.5")
    data_path = Path(data_path)
    records = list(iter_csv_windows(data_path, chunk_rows=chunk_rows))
    if len(records) < 10:
        raise ValueError(f"Need at least 10 complete windows; found {len(records)}")
    X = np.asarray([[row[0][key] for key in FEATURE_COLUMNS] for row in records], dtype=np.float64)
    y = np.asarray([row[1] for row in records], dtype=np.int8)

    # Strict chronological split; no shuffling, so adjacent windows do not cross the split.
    split = int(math.floor(len(records) * (1.0 - test_fraction)))
    split = min(max(split, 1), len(records) - 1)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]
    if np.unique(y_train).size < 2:
        raise ValueError("The chronological training portion contains only one class; add earlier FALL and ADL windows")

    model = RandomForestClassifier(
        n_estimators=n_estimators,
        class_weight="balanced_subsample",
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    predicted = model.predict(X_test)
    matrix = confusion_matrix(y_test, predicted, labels=[0, 1])
    fall_precision = precision_score(y_test, predicted, pos_label=1, zero_division=0)
    fall_recall = recall_score(y_test, predicted, pos_label=1, zero_division=0)
    fall_f1 = f1_score(y_test, predicted, pos_label=1, zero_division=0)
    metrics = {
        "source_file": data_path.name,
        "data_origin": data_origin,
        "source_rows_used": len(records) * WINDOW_SAMPLES,
        "source_windows": len(records),
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "window_seconds": WINDOW_SECONDS,
        "window_samples": WINDOW_SAMPLES,
        "window_label_rule": "mean(label) >= 0.5 => FALL",
        "std_ddof": 1,
        "train_test_split": "chronological; first 80% train, final 20% test; no shuffle",
        "train_windows": int(len(X_train)),
        "test_windows": int(len(X_test)),
        "n_estimators": int(n_estimators),
        "class_weight": "balanced_subsample",
        "feature_columns": list(FEATURE_COLUMNS),
        "fall_precision": float(fall_precision),
        "fall_recall": float(fall_recall),
        "fall_f1": float(fall_f1),
        "confusion_matrix_labels_0_1": matrix.astype(int).tolist(),
        "feature_importance": {
            name: float(value) for name, value in sorted(
                zip(FEATURE_COLUMNS, model.feature_importances_), key=lambda item: item[1], reverse=True
            )
        },
    }
    model_path, metrics_path = Path(model_path), Path(metrics_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--chunk-rows", type=int, default=WINDOW_SAMPLES * 200,
                        help=f"CSV chunk size; must be a multiple of {WINDOW_SAMPLES}")
    parser.add_argument("--test-fraction", type=float, default=0.2)
    parser.add_argument("--data-origin", choices=("real", "synthetic", "unknown"), default="unknown")
    args = parser.parse_args()
    if not args.data.is_file():
        parser.error(f"CSV not found: {args.data}")
    metrics = train_model(args.data, args.model, args.metrics, args.chunk_rows, args.test_fraction, data_origin=args.data_origin)
    print(f"Windows: {metrics['source_windows']:,} (train {metrics['train_windows']:,}, test {metrics['test_windows']:,})")
    print(f"FALL precision={metrics['fall_precision']:.4f} recall={metrics['fall_recall']:.4f} F1={metrics['fall_f1']:.4f}")
    print("Confusion matrix [[TN, FP], [FN, TP]]:", metrics["confusion_matrix_labels_0_1"])
    print(f"Saved model: {args.model}\nSaved metrics: {args.metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
