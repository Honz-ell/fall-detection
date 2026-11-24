#!/usr/bin/env python3
"""Huấn luyện mô hình phát hiện ngã trên các cửa sổ FallAllD.

Cách dùng:
    python train/train_fall_model.py \
        --data ../data/fallalld_wrist_sample.csv \
        --window-samples 200 --model-out models/fall_rf.joblib

Mô hình là RandomForest nhẹ, chạy được trên CPU và đủ để demo pipeline
(Không cần GPU). Đặc trưng tính bằng `src/fall/features.py` — cùng công thức
với Spark job.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fall.console import configure_console  # noqa: E402
from fall.features import FEATURE_COLUMNS, compute_window_features  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--window-samples", type=int, default=200)
    p.add_argument("--fall-ratio", type=float, default=0.5,
                   help="Cửa sổ được coi là NGÃ nếu tỉ lệ mẫu label=1 >= ngưỡng này.")
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--trees", type=int, default=200)
    p.add_argument("--model-out", type=Path, default=Path("models/fall_rf.joblib"))
    p.add_argument("--metrics-out", type=Path, default=Path("models/metrics.json"))
    return p.parse_args()


def build_windows(frame: pd.DataFrame, window_samples: int) -> tuple[np.ndarray, np.ndarray]:
    """Gom mẫu liên tiếp; trả về (features, tỷ lệ mẫu ngã trong mỗi cửa sổ)."""
    frame = frame.sort_index()
    boundaries = (np.arange(len(frame)) // window_samples)
    features: list[list[float]] = []
    fall_ratios: list[float] = []
    for _, chunk in frame.groupby(boundaries, sort=True):
        if len(chunk) < window_samples:
            continue  # bỏ cửa sổ rút gọn ở cuối
        feats = compute_window_features(chunk)
        features.append([feats[name] for name in FEATURE_COLUMNS])
        fall_ratios.append(float((chunk["label"].to_numpy() > 0).mean()))
    return np.asarray(features, dtype="float32"), np.asarray(fall_ratios, dtype="float32")


def main() -> int:
    configure_console()
    args = parse_args()
    if not args.data.is_file():
        print(f"Không tìm thấy file: {args.data}")
        return 2
    if (args.window_samples <= 0 or not 0 < args.test_size < 1
            or not 0 <= args.fall_ratio <= 1):
        print("--window-samples phải > 0, --test-size trong (0,1), --fall-ratio trong [0,1].")
        return 2

    print(f"Đọc {args.data} ...")
    dtypes = {
        "acc_x": "float32", "acc_y": "float32", "acc_z": "float32",
        "gyro_x": "float32", "gyro_y": "float32", "gyro_z": "float32",
        "label": "int8",
    }
    data = pd.read_csv(
        args.data,
        usecols=list(dtypes),
        dtype=dtypes,
        low_memory=False,
    ).dropna(subset=list(dtypes)).reset_index(drop=True)
    if not len(data):
        print("Không có mẫu hợp lệ trong file.")
        return 3
    print(f"Tổng mẫu: {len(data):,} | ngã: {int(data['label'].sum()):,} "
          f"({data['label'].mean() * 100:.2f}%)")

    x, fall_ratios = build_windows(data, args.window_samples)
    y = (fall_ratios >= args.fall_ratio).astype(int)
    print(f"Cửa sổ ({args.window_samples} mẫu/cửa sổ): {len(y):,} | "
          f"ngã: {int(y.sum()):,} ({y.mean() * 100:.2f}%)")
    if y.sum() == 0 or y.sum() == len(y):
        print("Lớp nhãn đồng nhất — không huấn luyện được. Hãy chỉnh --fall-ratio hoặc lấy dữ liệu khác.")
        return 3

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=args.test_size, random_state=args.seed, stratify=y
    )
    print(f"Train={len(y_train):,} Test={len(y_test):,}")

    model = RandomForestClassifier(
        n_estimators=args.trees,
        max_depth=None,
        min_samples_leaf=2,
        class_weight="balanced",
        n_jobs=-1,
        random_state=args.seed,
    )
    model.fit(x_train, y_train)

    proba = model.predict_proba(x_test)[:, 1]
    pred = (proba >= 0.5).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, pred, average="binary", zero_division=0
    )
    auc = float(roc_auc_score(y_test, proba)) if len(set(y_test)) > 1 else 0.0
    cm = confusion_matrix(y_test, pred).tolist()

    print("\n=== Kết quả trên tập kiểm tra ===")
    print(classification_report(y_test, pred, target_names=["ADL", "FALL"], zero_division=0))
    print(f"ROC-AUC: {auc:.4f} | Precision={precision:.4f} Recall={recall:.4f} F1={f1:.4f}")
    print(f"Confusion matrix [[TN FP],[FN TP]]: {cm}")

    importance = sorted(
        zip(FEATURE_COLUMNS, model.feature_importances_.round(4)), key=lambda kv: -kv[1]
    )
    print("\nĐộ quan trọng đặc trưng:")
    for name, score in importance:
        print(f"  {name:<16} {score:.4f}")

    args.model_out.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, args.model_out)
    metrics = {
        "model_type": "RandomForestClassifier",
        "window_samples": args.window_samples,
        "fall_ratio": args.fall_ratio,
        "feature_columns": FEATURE_COLUMNS,
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "roc_auc": round(auc, 4),
        "confusion_matrix": cm,
        "feature_importance": {name: float(score) for name, score in importance},
    }
    args.metrics_out.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nĐã lưu model: {args.model_out}")
    print(f"Đã lưu metrics: {args.metrics_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
