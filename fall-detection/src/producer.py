#!/usr/bin/env python3
"""Chunked multi-device CSV replay to Kafka at 238 samples/second/device."""
from __future__ import annotations

import argparse
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from fall.common import REQUIRED_CSV_COLUMNS, SAMPLE_RATE_HZ, WINDOW_SAMPLES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "fallalld_processed_wrist-acc-gyro.csv"
DEFAULT_TOPIC = "wearable.fall.v1"


def iter_csv_samples(data_path: str | Path, chunk_rows: int):
    if chunk_rows <= 0 or chunk_rows % WINDOW_SAMPLES != 0:
        raise ValueError(f"chunk_rows must be a positive multiple of {WINDOW_SAMPLES}")
    dtypes = {name: "float32" for name in REQUIRED_CSV_COLUMNS}
    dtypes["label"] = "int8"
    index = 0
    for chunk in pd.read_csv(data_path, usecols=list(REQUIRED_CSV_COLUMNS), dtype=dtypes,
                             chunksize=chunk_rows, low_memory=False):
        columns = {name: chunk[name].to_numpy() for name in REQUIRED_CSV_COLUMNS}
        for offset in range(len(chunk)):
            yield index, {name: columns[name][offset] for name in REQUIRED_CSV_COLUMNS}
            index += 1


def replay_device(
    *, device_id: str, data_path: Path, broker: str, topic: str, epoch_start: float,
    speed: float, chunk_rows: int, limit: int, dry_run_file, dry_run_lock: threading.Lock,
    failures: list[BaseException],
) -> None:
    producer = None
    sent = 0
    try:
        if dry_run_file is None:
            from kafka import KafkaProducer
            producer = KafkaProducer(bootstrap_servers=broker, acks="all", retries=5, linger_ms=5)
        base_mono = time.monotonic()
        for sample_index, sample in iter_csv_samples(data_path, chunk_rows):
            if limit and sent >= limit:
                break
            event_time = datetime.fromtimestamp(epoch_start + sample_index / SAMPLE_RATE_HZ, timezone.utc)
            record = {
                "device_id": device_id,
                "event_time": event_time.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "sample_index": sample_index,
                "sample_rate_hz": SAMPLE_RATE_HZ,
                **{key: float(sample[key]) for key in ("acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z")},
                "label": int(sample["label"]),  # ground-truth for analysis only, never a model feature
            }
            payload = json.dumps(record, separators=(",", ":")).encode("utf-8")
            if producer is not None:
                producer.send(topic, key=device_id.encode("utf-8"), value=payload)
            else:
                with dry_run_lock:
                    dry_run_file.write(payload.decode("utf-8") + "\n")
            sent += 1
            if sent % 250 == 0 and producer is not None:
                producer.flush(timeout=20)
            target = base_mono + sample_index / (SAMPLE_RATE_HZ * speed)
            delay = target - time.monotonic()
            if delay > 0:
                time.sleep(delay)
        if producer is not None:
            producer.flush(timeout=30)
        print(f"{device_id}: emitted {sent:,} samples")
    except BaseException as exc:
        failures.append(exc)
        print(f"{device_id}: producer failed: {exc}")
    finally:
        if producer is not None:
            producer.close(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--broker", default="localhost:9092")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--devices", default="wrist-01,wrist-02,wrist-03",
                        help="Comma-separated device IDs; each device replays the CSV independently")
    parser.add_argument("--speed", type=float, default=1.0, help="Replay multiplier (1.0 = real time)")
    parser.add_argument("--chunk-rows", type=int, default=WINDOW_SAMPLES * 200,
                        help=f"CSV chunk size; must be a multiple of {WINDOW_SAMPLES}")
    parser.add_argument("--limit", type=int, default=0, help="Maximum samples per device; 0 = whole file")
    parser.add_argument("--dry-run", type=Path, help="Write JSONL without Kafka; used by offline tests")
    args = parser.parse_args()
    devices = [item.strip() for item in args.devices.split(",") if item.strip()]
    if not args.data.is_file():
        parser.error(f"CSV not found: {args.data}")
    if not devices or args.speed <= 0 or args.limit < 0:
        parser.error("Provide at least one device, positive --speed, and nonnegative --limit")
    if args.chunk_rows <= 0 or args.chunk_rows % WINDOW_SAMPLES:
        parser.error(f"--chunk-rows must be a multiple of {WINDOW_SAMPLES}")

    # Anchor every device to the next exact 2-second epoch boundary.
    epoch_start = (int(time.time() // 2) + 1) * 2
    dry_run_file = args.dry_run.open("w", encoding="utf-8") if args.dry_run else None
    lock = threading.Lock()
    failures: list[BaseException] = []
    try:
        threads = [threading.Thread(
            target=replay_device,
            kwargs={"device_id": device, "data_path": args.data, "broker": args.broker,
                    "topic": args.topic, "epoch_start": epoch_start, "speed": args.speed,
                    "chunk_rows": args.chunk_rows, "limit": args.limit, "dry_run_file": dry_run_file,
                    "dry_run_lock": lock, "failures": failures},
            daemon=False,
        ) for device in devices]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        if dry_run_file:
            dry_run_file.close()
    if failures:
        return 1
    print(f"Producer complete: {len(devices)} device(s), rate={SAMPLE_RATE_HZ} Hz/device, start={epoch_start}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
