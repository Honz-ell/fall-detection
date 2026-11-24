#!/usr/bin/env python3
"""Spark Structured Streaming: Kafka samples -> 2-second, 11-feature PostgreSQL windows."""
from __future__ import annotations

import os
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession, functions as F
from pyspark.sql.types import DoubleType, IntegerType, StringType, StructField, StructType

from fall.common import (
    FEATURE_COLUMNS, MIN_WINDOW_SAMPLES, SAMPLE_RATE_HZ, WATERMARK_SECONDS, WINDOW_SECONDS,
)

SCHEMA = StructType([
    StructField("device_id", StringType(), False),
    StructField("event_time", StringType(), False),
    StructField("sample_index", IntegerType(), False),
    StructField("sample_rate_hz", IntegerType(), True),
    StructField("acc_x", DoubleType(), False),
    StructField("acc_y", DoubleType(), False),
    StructField("acc_z", DoubleType(), False),
    StructField("gyro_x", DoubleType(), False),
    StructField("gyro_y", DoubleType(), False),
    StructField("gyro_z", DoubleType(), False),
    StructField("label", IntegerType(), True),
])


def aggregate_and_write(batch: DataFrame, batch_id: int) -> None:
    """Write complete-enough windows; label_fraction is retained for evaluation only."""
    import psycopg

    postgres_url = os.environ.get("FALL_POSTGRES_URL", "postgresql://falld:fall_dev_password@postgres:5432/falldetect")
    rows = batch.where(F.col("sample_count") >= MIN_WINDOW_SAMPLES).collect()
    if not rows:
        print(f"batch {batch_id}: no windows with >= {MIN_WINDOW_SAMPLES} samples")
        return
    columns = ["device_id", "window_start", "window_end", "sample_count", *FEATURE_COLUMNS,
               "label_fraction", "spark_batch_id"]
    placeholders = ",".join(["%s"] * len(columns))
    updates = ",".join(f"{name}=EXCLUDED.{name}" for name in columns[2:])
    sql = (
        f"INSERT INTO window_features ({','.join(columns)}) VALUES ({placeholders}) "
        f"ON CONFLICT (device_id, window_start) DO UPDATE SET {updates}"
    )
    values = []
    for row in rows:
        values.append((row.device_id, row.window_start, row.window_end, int(row.sample_count),
                       *[float(row[name]) for name in FEATURE_COLUMNS],
                       float(row.label_fraction or 0.0), int(batch_id)))
    with psycopg.connect(postgres_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, values)
    print(f"batch {batch_id}: persisted {len(values)} windows")


def main() -> None:
    broker = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = os.environ.get("KAFKA_TOPIC", "wearable.fall.v1")
    checkpoint = os.environ.get("SPARK_CHECKPOINT", "/app/runtime/spark-checkpoint")
    spark = (SparkSession.builder.appName("FallAllD-Wrist-Window-Features")
             .config("spark.sql.session.timeZone", "UTC")
             .config("spark.sql.shuffle.partitions", os.environ.get("SPARK_SHUFFLE_PARTITIONS", "2"))
             .getOrCreate())
    spark.sparkContext.setLogLevel("WARN")

    raw = (spark.readStream.format("kafka")
           .option("kafka.bootstrap.servers", broker)
           .option("subscribe", topic)
           .option("startingOffsets", "earliest")
           .option("failOnDataLoss", "false")
           .option("maxOffsetsPerTrigger", os.environ.get("SPARK_MAX_OFFSETS", "100000"))
           .load())
    parsed = (raw.select(F.from_json(F.col("value").cast("string"), SCHEMA).alias("s"))
              .select("s.*")
              .withColumn("event_time", F.to_timestamp(F.regexp_replace("event_time", "Z$", "+00:00")))
              .where(F.col("device_id").isNotNull() & F.col("event_time").isNotNull()))
    samples = (parsed
               .withColumn("acc_mag", F.sqrt(F.col("acc_x")**2 + F.col("acc_y")**2 + F.col("acc_z")**2))
               .withColumn("gyro_mag", F.sqrt(F.col("gyro_x")**2 + F.col("gyro_y")**2 + F.col("gyro_z")**2))
               .withWatermark("event_time", f"{WATERMARK_SECONDS} seconds"))

    aggregated = (samples.groupBy(F.window("event_time", f"{WINDOW_SECONDS} seconds"), "device_id")
        .agg(
            F.count(F.lit(1)).alias("sample_count"),
            F.avg("acc_mag").alias("acc_mag_mean"),
            F.stddev_samp("acc_mag").alias("acc_mag_std"),
            F.min("acc_mag").alias("acc_mag_min"),
            F.max("acc_mag").alias("acc_mag_max"),
            (F.max("acc_mag") - F.min("acc_mag")).alias("acc_mag_range"),
            F.stddev_samp("acc_x").alias("acc_x_std"),
            F.stddev_samp("acc_y").alias("acc_y_std"),
            F.stddev_samp("acc_z").alias("acc_z_std"),
            F.avg("gyro_mag").alias("gyro_mag_mean"),
            F.stddev_samp("gyro_mag").alias("gyro_mag_std"),
            F.max("gyro_mag").alias("gyro_mag_max"),
            F.avg(F.col("label").cast("double")).alias("label_fraction"),
        )
        .select(F.col("window.start").alias("window_start"), F.col("window.end").alias("window_end"),
                "device_id", "sample_count", *FEATURE_COLUMNS, "label_fraction")
    )
    query = (aggregated.writeStream.outputMode("append")
             .foreachBatch(aggregate_and_write)
             .option("checkpointLocation", checkpoint)
             .trigger(processingTime=os.environ.get("SPARK_TRIGGER", "2 seconds"))
             .start())
    print(f"Spark live: topic={topic}, broker={broker}, window={WINDOW_SECONDS}s, watermark={WATERMARK_SECONDS}s, min_samples={MIN_WINDOW_SAMPLES}/{SAMPLE_RATE_HZ*WINDOW_SECONDS}")
    query.awaitTermination()


if __name__ == "__main__":
    main()
