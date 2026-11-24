"""Gom mẫu FallAllD thành các cửa sổ đặc trưng (dùng chung train / scorer / kiểm thử)."""
from __future__ import annotations

import numpy as np

from .features import FEATURE_COLUMNS, compute_window_features


def iter_window_records(frame, window_samples: int = 200, fall_ratio: float = 0.5):
    """Sin ra bản ghi cửa sổ: đặc trưng + nhãn + khoảng mẫu.

    Yield dict với các khóa trong FEATURE_COLUMNS, `sample_count`,
    `first_sample`, `last_sample`, `fall_ratio`, `label`.
    """
    if window_samples <= 0:
        raise ValueError("window_samples phải > 0")
    frame = frame.reset_index(drop=True)
    if "sample_index" not in frame.columns:
        frame["sample_index"] = np.arange(len(frame))
    boundaries = np.arange(len(frame)) // window_samples
    for window_index, (_, chunk) in enumerate(frame.groupby(boundaries, sort=True)):
        if len(chunk) < window_samples:
            continue
        feats = compute_window_features(chunk)
        ratio = float((chunk["label"].to_numpy() > 0).mean())
        record = {
            "window_index": window_index,
            "sample_count": int(len(chunk)),
            "first_sample": int(chunk["sample_index"].iloc[0]),
            "last_sample": int(chunk["sample_index"].iloc[-1]),
            "fall_ratio": round(ratio, 4),
            "label": int(ratio >= fall_ratio),
        }
        record.update({name: feats[name] for name in FEATURE_COLUMNS})
        yield record
