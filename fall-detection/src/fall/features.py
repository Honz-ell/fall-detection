"""Đặc trưng cửa sổ dùng chung cho huấn luyện và scoring.

Giữ danh sách tên đặc trưng ở một chỗ để producer/Spark/scorer không lệch nhau.
"""
from __future__ import annotations

FEATURE_COLUMNS = [
    "acc_mag_mean",
    "acc_mag_std",
    "acc_mag_max",
    "acc_mag_min",
    "acc_x_mean",
    "acc_y_mean",
    "acc_z_mean",
    "gyro_mag_mean",
    "gyro_mag_std",
    "gyro_mag_max",
]

WINDOW_SAMPLES = 200  # ~2 giây ở 100 Hz


def compute_window_features(frame) -> dict:
    """Tính đặc trưng cho một cụm mẫu (pandas DataFrame).

    Hàm này là nguồn sự thật duy nhất; Spark job và scorer phải tính ra
    đúng các cột trong FEATURE_COLUMNS với cùng công thức.
    """
    import numpy as np

    acc = frame[["acc_x", "acc_y", "acc_z"]].to_numpy(dtype="float64")
    gyro = frame[["gyro_x", "gyro_y", "gyro_z"]].to_numpy(dtype="float64")
    acc_mag = np.linalg.norm(acc, axis=1)
    gyro_mag = np.linalg.norm(gyro, axis=1)
    values = {
        "acc_mag_mean": float(np.mean(acc_mag)),
        "acc_mag_std": float(np.std(acc_mag)),
        "acc_mag_max": float(np.max(acc_mag)),
        "acc_mag_min": float(np.min(acc_mag)),
        "acc_x_mean": float(np.mean(acc[:, 0])),
        "acc_y_mean": float(np.mean(acc[:, 1])),
        "acc_z_mean": float(np.mean(acc[:, 2])),
        "gyro_mag_mean": float(np.mean(gyro_mag)),
        "gyro_mag_std": float(np.std(gyro_mag)),
        "gyro_mag_max": float(np.max(gyro_mag)),
    }
    return {name: round(values[name], 5) for name in FEATURE_COLUMNS}
