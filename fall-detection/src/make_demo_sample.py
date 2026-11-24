#!/usr/bin/env python3
"""Generate a small, explicitly synthetic FallAllD-schema CSV for demos/tests."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from fall.common import REQUIRED_CSV_COLUMNS, SAMPLE_RATE_HZ, WINDOW_SAMPLES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "fallalld_demo_synthetic.csv"


def generate_demo_csv(output: str | Path, windows: int = 40, seed: int = 2026, fall_every: int = 2) -> int:
    if windows < 10:
        raise ValueError("Generate at least 10 windows for a chronological train/test split")
    if fall_every < 2:
        raise ValueError("fall_every must be >= 2 so the demo contains ADL windows")
    rng = np.random.default_rng(seed)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    time = np.arange(WINDOW_SAMPLES, dtype=np.float64) / SAMPLE_RATE_HZ
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REQUIRED_CSV_COLUMNS)
        writer.writeheader()
        for w in range(windows):
            is_fall = (w % fall_every) == (fall_every - 1)
            phase = rng.uniform(0, 2 * np.pi)
            # Ordinary activity: low-amplitude periodic wrist motion around gravity.
            ax = 0.25 * np.sin(2 * np.pi * 1.2 * time + phase) + rng.normal(0, 0.08, WINDOW_SAMPLES)
            ay = 0.35 * np.sin(2 * np.pi * 0.8 * time + phase / 2) + rng.normal(0, 0.08, WINDOW_SAMPLES)
            az = 9.81 + 0.22 * np.sin(2 * np.pi * 1.0 * time) + rng.normal(0, 0.1, WINDOW_SAMPLES)
            gx = 0.12 * np.sin(2 * np.pi * time) + rng.normal(0, 0.05, WINDOW_SAMPLES)
            gy = 0.10 * np.cos(2 * np.pi * 0.7 * time) + rng.normal(0, 0.05, WINDOW_SAMPLES)
            gz = 0.08 * np.sin(2 * np.pi * 0.5 * time) + rng.normal(0, 0.05, WINDOW_SAMPLES)
            labels = np.zeros(WINDOW_SAMPLES, dtype=np.int8)
            if is_fall:
                labels[:] = 1  # window-level FALL label at least 50% by construction
                # Synthetic impact + post-impact rotation; only for software demonstration.
                center = WINDOW_SAMPLES // 2 + int(rng.integers(-15, 16))
                lo, hi = max(0, center - 12), min(WINDOW_SAMPLES, center + 18)
                ax[lo:hi] += rng.choice([-1, 1]) * rng.uniform(16, 24)
                ay[lo:hi] += rng.uniform(8, 14)
                az[lo:hi] += rng.uniform(18, 28)
                gx[lo:hi] += rng.uniform(2.5, 4.5)
                gy[lo:hi] += rng.uniform(2.0, 4.0)
                labels[lo:hi] = 1
            for i in range(WINDOW_SAMPLES):
                writer.writerow({
                    "acc_x": f"{ax[i]:.6f}", "acc_y": f"{ay[i]:.6f}", "acc_z": f"{az[i]:.6f}",
                    "label": int(labels[i]), "gyro_x": f"{gx[i]:.6f}", "gyro_y": f"{gy[i]:.6f}", "gyro_z": f"{gz[i]:.6f}",
                })
    return windows * WINDOW_SAMPLES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--windows", type=int, default=40)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--fall-every", type=int, default=2)
    args = parser.parse_args()
    rows = generate_demo_csv(args.output, args.windows, args.seed, args.fall_every)
    print(f"Synthetic demo written: {args.output} ({rows:,} rows = {args.windows} windows × {WINDOW_SAMPLES})")
    print("WARNING: synthetic values for software demo only; not real FallAllD observations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
