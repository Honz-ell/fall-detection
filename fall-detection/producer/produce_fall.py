#!/usr/bin/env python3
"""Phát mẫu FallAllD wrist vào Kafka topic `wearable.fall.v1`.

Ví dụ:
    python producer/produce_fall.py \
        --data ../data/fallalld_wrist_sample.csv \
        --broker localhost:9094 --topic wearable.fall.v1 \
        --sample-rate 100 --speed 60

Thêm `--dry-run sample.jsonl` để không cần Kafka, chỉ ghi bản ghi ra file để kiểm tra.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from fall.console import configure_console  # noqa: E402
from fall.csv_reader import iter_samples  # noqa: E402

SCHEMA_VERSION = "wearable.fall.v1"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Replay FallAllD wrist CSV to Kafka.")
    p.add_argument("--data", type=Path, default=Path("data/fallalld_wrist_sample.csv"))
    p.add_argument("--broker", default="localhost:9094")
    p.add_argument("--topic", default="wearable.fall.v1")
    p.add_argument("--device-id", default="WRIST-01")
    p.add_argument("--sample-rate", type=float, default=100.0,
                   help="Tần số lấy mẫu giả định (Hz) để tạo timestamp.")
    p.add_argument("--window-seconds", type=float, default=2.0,
                   help="Độ dài cửa sổ Spark; timestamp đầu được căn theo cửa sổ này.")
    p.add_argument("--watermark-seconds", type=float, default=5.0,
                   help="Watermark Spark, dùng để đóng cửa sổ cuối sau replay.")
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
    configure_console()
    args = parse_args()
    if not args.data.is_file():
        print(f"Không tìm thấy file: {args.data}")
        return 2
    if (args.speed <= 0 or args.sample_rate <= 0 or args.limit < 0
            or args.window_seconds <= 0 or args.watermark_seconds <= 0):
        print("--speed, --sample-rate, --window-seconds và --watermark-seconds phải > 0; --limit không âm.")
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
    # Căn thời điểm đầu vào ranh giới epoch để Spark gom đúng 200 mẫu / 2 giây,
    # giống cách train và scorer chia cửa sổ liên tiếp.
    base_epoch = math.floor(time.time() / args.window_seconds) * args.window_seconds
    base_mono = time.monotonic()    # đồng hồ monotonic cho việc đồng bộ nhịp
    last_event_epoch = base_epoch
    sent = 0
    last_future = None
    print(
        f"Phát {args.data} → "
        f"{'Kafka ' + args.topic if producer else 'DRY-RUN ' + str(args.dry_run)} | "
        f"rate={args.sample_rate:g} Hz, speed={args.speed:g}x"
    )
    try:
        for sample in iter_samples(args.data):
            event_epoch = base_epoch + sample["sample_index"] / args.sample_rate
            last_event_epoch = event_epoch
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
        # Control nằm cùng partition và có event-time đủ xa để watermark đóng
        # cả cửa sổ cuối, dù replay chạy nhanh hơn thời gian thực.
        tail = control_record(
            args.device_id,
            last_event_epoch + args.window_seconds + args.watermark_seconds + 1.0,
        )
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
