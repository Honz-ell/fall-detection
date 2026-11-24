# Phát hiện ngã cho người cao tuổi — Big Data Pipeline

Đề tài môn **Dữ liệu Lớn** (nhóm 8\) — pipeline end-to-end: **Producer → Kafka → Spark Structured Streaming → PostgreSQL → Scorer → Grafana**, dữ liệu thiết bị đeo cổ tay **FallAllD**.

> Code đầy đủ nằm trong thư mục [`fall-detection/`](http://fall-detection/). Mô tả chi tiết, lệnh từng bước và con số đánh giá: [`fall-detection/README.md`](http://fall-detection/README.md).

## Kiến trúc

```
 fall-detection/data/fallalld_wrist_sample.csv
        │  producer/produce_fall.py
        ▼
   Kafka topic: wearable.fall.v1
        │  spark/aggregate_fall_stream.py   (cửa sổ 2s, watermark 5s)
        ▼
 PostgreSQL: fall_window_aggregates
        │  scorer/score_fall.py             (RandomForest)
        ├─► fall_predictions   (FALL / ADL + xác suất)
        └─► fall_alerts        (cảnh báo ngã)
        ▼
 Grafana dashboard :3000
```

## Dữ liệu

| Nguồn | Link |
| :---- | :---- |
| Hugging Face `IdaFLab/FallAllD-Wrist` | [https\://huggingface.co/datasets/IdaFLab/FallAllD-Wrist](https://huggingface.co/datasets/IdaFLab/FallAllD-Wrist) |
| Bản đầy đủ (.zip, Git LFS) | `fallalld_processed_wrist-acc-gyro.zip` (repo này) |
| Mẫu chạy thử 39 MB | `fall-detection/data/fallalld_wrist_sample.csv` |

Bản gốc: Saleh et al., *FallAllD*, IEEE Sensors Journal, 2021\. DOI 10.1109/JSEN.2020.3018335.

## Chạy nhanh

```sh
cd fall-detection
python -m pip install -r requirements.txt
python train/train_fall_model.py --data data/fallalld_wrist_sample.csv
python tests/test_offline_pipeline.py --data data/fallalld_wrist_sample.csv

docker compose -f deploy/docker-compose.yml up -d      # kafka + postgres + grafana
python producer/produce_fall.py --data data/fallalld_wrist_sample.csv --broker localhost:9092
spark-submit spark/aggregate_fall_stream.py --broker kafka:9092
python scorer/score_fall.py --model models/fall_rf.joblib
```

## Kết quả (mẫu 39 MB, cửa sổ 200 mẫu)

|  | Precision | Recall | F1 |
| :---- | :---- | :---- | :---- |
| ADL | 0,93 | 0,95 | 0,94 |
| **NGÃ** | 0,80 | **0,72** | **0,76** |

ROC-AUC \= **0,9554** (tách train/test, RandomForest 200 cây).

## Cấu trúc repo

| Đường dẫn | Nội dung |
| :---- | :---- |
| `fall-detection/producer/` | Đọc CSV → Kafka (`wearable.fall.v1`) |
| `fall-detection/spark/` | Structured Streaming tổng hợp theo cửa sổ → Postgres |
| `fall-detection/scorer/` | Phân loại ngã, ghi predictions/alerts |
| `fall-detection/train/` | Huấn luyện model, lưu `models/` |
| `fall-detection/src/fall/` | Reader, đặc trưng, cửa sổ (dùng chung) |
| `fall-detection/sql/`, `deploy/`, `grafana/` | Schema, Docker Compose, dashboard |
| `fall-detection/tests/` | Kiểm thử offline đầu–cuối |

## Lưu ý

- File `.csv`/`.zip` lớn được Git LFS quản lý (`.gitattributes`).  
- Repo khác `Vic-Hwang85/data` giữ bản đầy đủ 1,37 GB; repo này tập trung **code**.