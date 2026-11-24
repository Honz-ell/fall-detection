"""Spark Structured Streaming: gom mẫu FallAllD theo cửa sổ rồi ghi PostgreSQL.

Cách chạy:
    spark-submit spark/aggregate_fall_stream.py \
        --broker kafka:9092 --topic wearable.fall.v1 \
        --window "2 seconds" --watermark "5 seconds" \
        --postgres-url jdbc:postgresql://postgres:5432/falldetect

Công thức đặc trưng phải khớp `src/fall/features.py`:
  * std dùng `stddev_pop` (ddof=0) vì numpy tính population std.
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from pyspark.sql import SparkSession, functions as F


class MetricsState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values = {
            "falld_spark_stream_up": 0,
            "falld_spark_records_in_batch": 0,
            "falld_spark_input_rows_per_second": 0.0,
            "falld_spark_processed_rows_per_second": 0.0,
            "falld_spark_trigger_execution_ms": 0.0,
        }

    def update(self, progress: dict[str, Any]) -> None:
        duration = progress.get("durationMs") or {}
        values = {
            "falld_spark_stream_up": 1,
            "falld_spark_records_in_batch": float(progress.get("numInputRows") or 0),
            "falld_spark_input_rows_per_second": float(progress.get("inputRowsPerSecond") or 0),
            "falld_spark_processed_rows_per_second": float(
                progress.get("processedRowsPerSecond") or 0
            ),
            "falld_spark_trigger_execution_ms": float(duration.get("triggerExecution") or 0),
        }
        with self._lock:
            self._values = values

    def set_down(self) -> None:
        with self._lock:
            self._values["falld_spark_stream_up"] = 0

    def render(self) -> str:
        lines = []
        for name, value in self._values.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")
        return "\n".join(lines) + "\n"


METRICS = MetricsState()


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/metrics":
            self.send_error(404)
            return
        body = METRICS.render().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        return


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="FallAllD window aggregation (Structured Streaming).")
    p.add_argument("--broker", default="kafka:9092")
    p.add_argument("--topic", default="wearable.fall.v1")
    p.add_argument("--window", default="2 seconds")
    p.add_argument("--watermark", default="5 seconds")
    p.add_argument("--starting-offsets", choices=("earliest", "latest"), default="earliest")
    p.add_argument("--checkpoint-location", default="/opt/project/checkpoints/spark-fall")
    p.add_argument("--postgres-url", default="jdbc:postgresql://postgres:5432/falldetect")
    p.add_argument("--postgres-user", default="falld")
    p.add_argument("--metrics-host", default="0.0.0.0")
    p.add_argument("--metrics-port", type=int, default=9096)
    return p.parse_args()


def write_batch(batch_df, batch_id: int, args: argparse.Namespace) -> None:
    output = batch_df.where(F.col("device_id").isNotNull())
    if not output.take(1):
        print(f"Micro-batch #{batch_id}: không có cửa sổ hợp lệ.")
        return
    (
        output.withColumn("spark_batch_id", F.lit(batch_id).cast("long"))
        .write.format("jdbc")
        .option("url", args.postgres_url)
        .option("dbtable", "fall_window_aggregates")
        .option("user", args.postgres_user)
        .option("password", os.environ.get("FALL_DB_PASSWORD", "fall_dev_password"))
        .option("driver", "org.postgresql.Driver")
        .option("batchsize", "1000")
        .mode("append")
        .save()
    )
    print(f"Đã ghi micro-batch #{batch_id} vào fall_window_aggregates.")


def main() -> None:
    args = parse_args()
    spark = (
        SparkSession.builder.appName("FallAllD-Wrist-Window-Aggregation")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "1")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    raw = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", args.broker)
        .option("subscribe", args.topic)
        .option("startingOffsets", args.starting_offsets)
        .option("failOnDataLoss", "false")
        .load()
        .selectExpr("CAST(value AS STRING) AS json")
    )

    j = lambda path: F.get_json_object("json", path)  # noqa: E731
    events = raw.select(
        j("$.device_id").alias("device_id"),
        F.to_timestamp(j("$.timestamp")).alias("event_time"),
        j("$.acc_x").cast("double").alias("acc_x"),
        j("$.acc_y").cast("double").alias("acc_y"),
        j("$.acc_z").cast("double").alias("acc_z"),
        j("$.gyro_x").cast("double").alias("gyro_x"),
        j("$.gyro_y").cast("double").alias("gyro_y"),
        j("$.gyro_z").cast("double").alias("gyro_z"),
        j("$.label").cast("int").alias("label"),
    ).where(
        F.col("device_id").isNotNull()
        & F.col("event_time").isNotNull()
        & F.col("acc_x").isNotNull()
    )

    measurable = (
        events.withColumn(
            "acc_mag", F.sqrt(F.pow(F.col("acc_x"), 2) + F.pow(F.col("acc_y"), 2) + F.pow(F.col("acc_z"), 2))
        )
        .withColumn(
            "gyro_mag",
            F.sqrt(F.pow(F.col("gyro_x"), 2) + F.pow(F.col("gyro_y"), 2) + F.pow(F.col("gyro_z"), 2)),
        )
        .withWatermark("event_time", args.watermark)
    )

    aggregates = (
        measurable.groupBy(F.window("event_time", args.window), "device_id")
        .agg(
            F.count("*").alias("sample_count"),
            F.round(F.avg("acc_mag"), 5).alias("acc_mag_mean"),
            F.round(F.stddev_pop("acc_mag"), 5).alias("acc_mag_std"),
            F.round(F.max("acc_mag"), 5).alias("acc_mag_max"),
            F.round(F.min("acc_mag"), 5).alias("acc_mag_min"),
            F.round(F.avg("acc_x"), 5).alias("acc_x_mean"),
            F.round(F.avg("acc_y"), 5).alias("acc_y_mean"),
            F.round(F.avg("acc_z"), 5).alias("acc_z_mean"),
            F.round(F.avg("gyro_mag"), 5).alias("gyro_mag_mean"),
            F.round(F.stddev_pop("gyro_mag"), 5).alias("gyro_mag_std"),
            F.round(F.max("gyro_mag"), 5).alias("gyro_mag_max"),
            F.sum(F.when(F.col("label") > 0, 1).otherwise(0)).alias("fall_samples"),
        )
        .select(
            F.col("window.start").alias("window_start"),
            F.col("window.end").alias("window_end"),
            "device_id",
            "sample_count",
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
            "fall_samples",
        )
    )

    query = (
        aggregates.writeStream.outputMode("append")
        .foreachBatch(lambda df, bid: write_batch(df, bid, args))
        .option("checkpointLocation", args.checkpoint_location)
        .trigger(processingTime="2 seconds")
        .start()
    )

    server = ThreadingHTTPServer((args.metrics_host, args.metrics_port), MetricsHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(
        f"Spark đọc topic={args.topic} từ {args.broker}; window={args.window}, "
        f"watermark={args.watermark}; ghi PostgreSQL. Metrics :{args.metrics_port}/metrics"
    )
    try:
        while query.isActive:
            if query.lastProgress is not None:
                METRICS.update(json.loads(query.lastProgress.json))
            time.sleep(1)
        query.awaitTermination()
    except KeyboardInterrupt:
        print("\nDừng stream.")
        query.stop()
    finally:
        METRICS.set_down()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
