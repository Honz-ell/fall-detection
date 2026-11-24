"""Đọc file CSV FallAllD (wrist) thành từng mẫu cảm biến.

Schema cố định: acc_x,acc_y,acc_z,label,gyro_x,gyro_y,gyro_z
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

COLUMNS = ("acc_x", "acc_y", "acc_z", "label", "gyro_x", "gyro_y", "gyro_z")


class SchemaError(ValueError):
    """File CSV không đúng schema FallAllD."""


def iter_samples(path: str | Path) -> Iterator[dict]:
    """Sin ra từng mẫu ở dạng dict float/int, kèm số thứ tự `sample_index`."""
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise SchemaError(
                f"Thiếu cột {sorted(missing)} trong {path}. Cần {list(COLUMNS)}."
            )
        for index, row in enumerate(reader):
            yield {
                "sample_index": index,
                "acc_x": float(row["acc_x"]),
                "acc_y": float(row["acc_y"]),
                "acc_z": float(row["acc_z"]),
                "gyro_x": float(row["gyro_x"]),
                "gyro_y": float(row["gyro_y"]),
                "gyro_z": float(row["gyro_z"]),
                "label": int(float(row["label"])),
            }


def iter_pandas(path: str | Path, chunksize: int = 200_000):
    """Đọc theo từng khối bằng pandas (dùng cho huấn luyện)."""
    import pandas as pd

    return pd.read_csv(
        path,
        usecols=list(COLUMNS),
        dtype={
            "acc_x": "float32",
            "acc_y": "float32",
            "acc_z": "float32",
            "gyro_x": "float32",
            "gyro_y": "float32",
            "gyro_z": "float32",
            "label": "int8",
        },
        chunksize=chunksize,
    )


def count_rows(path: str | Path) -> int:
    with Path(path).open("rb") as handle:
        return max(0, sum(1 for _ in handle) - 1)
