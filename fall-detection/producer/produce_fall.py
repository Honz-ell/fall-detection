#!/usr/bin/env python3
"""Phát mẫu FallAllD wrist vào Kafka topic `wearable.fall.v1`.

Ví dụ:
    python producer/produce_fall.py \
        --data ../data/fallalld_wrist_sample.csv \
        --broker localhost:9092 --topic wearable.fall.v1 \
        --sample-rate 100 --speed 60

Thêm `--dry-run sample.jsonl` để không cần Kafka, chỉ ghi bản ghi ra file để kiểm tra.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fall.csv_reader import iter_samples  # noqa: E402

SCHEMA_VERSION = "wearable.fall.v1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Replay FallAllD wrist CSV to Kafka.")
    p.add_argument("--data", type=Path, default=Path("data/fallalld_wrist_sample.csv"))
    p.add_argument("--broker", default="localhost:9092")
    p.add_argument("--topic", default="wearable.fall.v1")
    p.add_argument("--device-id", default="WRIST-01")
    p.add_argument("--sample-rate", type=float, default=100.0,
                   help="Tần số lấy mẫu giả định (Hz) để tạo timestamp.")
    p.add_argument("--speed", type=float, default=60.0, help="Tốc độ replay (x).")
    p.add_argument("--limit", type=int, default=0, help="Số mẫu tối đa; 0 = hết file.")
    p.add_argument("--dry-run", type=Path, default=None,
                   help="Ghi bản ghi ra file JSONL thay vì gửi Kafka.")
    return p.parse_args()


def iso(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds, timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def control_record(device_id: str, epoch: float) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "device_id": device_id,
        "timestamp": iso(epoch),
        "sensor": "__CONTROL__",
        "replay_control": True,
    }


def main() -> int:
    args = parse_args()
    if not args.data.is_file():
        print(f"Không tìm thấy file: {args.data}")
        return 2
    if args.speed <= 0 or args.sample_rate <= 0 or args.limit < 0:
        print("--speed và --sample-rate phải > 0; --limit không âm.")
        return 2

    producer = None
    if args.dry_run is None:
        try:
            from kafka import KafkaProducer
        except ImportError:
            print("Thiếu kafka-python: pip install kafka-python (hoặc dùng --dry-run).")
            return 2
        producer = KafkaProducer(
            bootstrap_servers=args.broker, acks="all", retries=5, linger_ms=10
        )

    out_handle = args.dry_run.open("w", encoding="utf-8") if args.dry_run else None
    base_epoch = time.time()        # mốc thời gian thật cho trường `timestamp`
    base_mono = time.monotonic()    # đồng hồ monotonic cho việc đồng bộ nhịp
    sent = 0
    last_future = None
    print(
        f"Phát {args.data} -> "
        f"{'Kafka ' + args.topic if producer else 'DRY-RUN ' + str(args.dry_run)} | "
        f"rate={args.sample_rate:g} Hz, speed={args.speed:g}x"
    )
    try:
        for sample in iter_samples(args.data):
            event_epoch = base_epoch + sample["sample_index"] / args.sample_rate
            record = {
                "schema_version": SCHEMA_VERSION,
                "device_id": args.device_id,
                "timestamp": iso(event_epoch),
                **{k: v for k, v in sample.items() if k != "sample_index"},
                "sample_index": sample["sample_index"],
            }
            payload = json.dumps(record, separators=(",", ":")).encode("utf-8")
            if producer:
                last_future = producer.send(
                    args.topic, key=args.device_id.encode("utf-8"), value=payload
                )
                sent += 1
                if sent % 250 == 0:
                    last_future.get(timeout=30)
            else:
                out_handle.write(payload.decode("utf-8") + "\n")
                sent += 1
            # Pacing theo monotonic clock để tránh tích lũy sai số.
            target = base_mono + sample["sample_index"] / (args.sample_rate * args.speed)
            wait = target - time.monotonic()
            if wait >= 0.002:
                time.sleep(wait)
            if args.limit and sent >= args.limit:
                break
        if producer and last_future is not None:
            last_future.get(timeout=30)
        # Bản tin điều khiển để Spark chốt cửa sổ cuối.
        tail = control_record(args.device_id, time.time() + 10.0)
        if producer:
            producer.send(args.topic, key=args.device_id.encode("utf-8"),
                          value=json.dumps(tail, separators=(",", ":")).encode()).get(timeout=30)
        elif out_handle:
            out_handle.write(json.dumps(tail, separators=(",", ":")) + "\n")
    except KeyboardInterrupt:
        print("\nĐã nhận Ctrl+C, đang dừng.")
    finally:
        if producer:
            producer.flush()
            producer.close()
        if out_handle:
            out_handle.close()
    print(f"Hoàn tất: đã phát {sent:,} mẫu.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
