# Phát hiện ngã cho người cao tuổi — Big Data Pipeline (FallAllD)

Đề tài thay thế WESAD/stress của nhóm 8: giữ nguyên stack **Producer → Kafka → Spark
Structured Streaming → PostgreSQL → Grafana**, đổi dữ liệu/bài toán sang **phát hiện
ngã theo thời gian thực** với dữ liệu thiết bị đeo cổ tay FallAllD.

## Kiến trúc

```
 data/fallalld_wrist_sample.csv
        │  producer/produce_fall.py   (replay tốc độ ×N, mẫu 100 Hz)
        ▼
    Kafka topic: wearable.fall.v1
        │  spark/aggregate_fall_stream.py   (cửa sổ 2s, watermark 5s)
        ▼
 PostgreSQL: fall_window_aggregates
        │  scorer/score_fall.py   (RandomForest, poll cửa sổ mới)
        ├─► fall_predictions     (FALL / ADL + xác suất)
        └─► fall_alerts          (cảnh báo ngã)
        ▼
   Grafana dashboard: falld-overview  (:3000)
```

## Dữ liệu
- Nguồn: <https://huggingface.co/datasets/IdaFLab/FallAllD-Wrist> (Saleh et al., IEEE Sensors Journal, 2021; DOI 10.1109/JSEN.2020.3018335).
- Schema: `acc_x,acc_y,acc_z,label,gyro_x,gyro_y,gyro_z`; `label`: `0` = sinh hoạt thường ngày (ADL), `1` = ngã.
- `data/fallalld_wrist_sample.csv` — 40 MB / 348.318 mẫu / 76.160 mẫu ngã (21,9%) để chạy thử.
- Bản đầy đủ (11.971.400 mẫu): `bash data/download_fallalld.sh`.

## Cấu trúc
| Đường dẫn | Vai trò |
|---|---|
| `producer/produce_fall.py` | Đọc CSV → gửi JSON vào Kafka (`--dry-run` để test không cần broker) |
| `spark/aggregate_fall_stream.py` | Structured Streaming: cửa sổ 2s → đặc trưng → Postgres |
| `scorer/score_fall.py` | 3 chế độ: `--from-csv` (offline), `--input-jsonl`, mặc định poll Postgres |
| `train/train_fall_model.py` | Huấn luyện RandomForest trên cửa sổ, lưu model + metrics |
| `src/fall/` | Reader, đặc trưng, cửa sổ — nguồn sự thật dùng chung |
| `sql/001_init.sql` | Schema PostgreSQL |
| `deploy/docker-compose.yml` | Kafka + PostgreSQL + Grafana |
| `grafana/fall-dashboard.json` | Dashboard mẫu |
| `tests/test_offline_pipeline.py` | Kiểm thử đầu–cuối không cần Kafka/Spark |

## Yêu cầu
- Docker Desktop đang chạy (Kafka/PostgreSQL/Grafana/Spark đều chạy bằng Compose)
- Python ≥ 3.10 để train, phát dữ liệu và chạy scorer
- Kết nối Internet lần đầu để Docker tải image và Spark tải Kafka/JDBC connectors

## Chạy thử
Mở PowerShell tại `fall-detection` (trên máy này: `D:\DLLL\data-repo\fall-detection`):

```bash
python -m pip install -r requirements.txt
python train/train_fall_model.py --data data/fallalld_wrist_sample.csv  # tùy chọn: huấn luyện lại
python tests/test_offline_pipeline.py                                 # kiểm tra offline

docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml logs -f spark  # cửa sổ khác để xem log Spark
python producer/produce_fall.py --data data/fallalld_wrist_sample.csv --broker localhost:9094 --speed 60
python scorer/score_fall.py --model models/fall_rf.joblib --postgres-url postgresql://falld:fall_dev_password@localhost:5433/falldetect
```

Grafana ở <http://localhost:3001> (đăng nhập `admin` / `admin`); Spark UI ở <http://localhost:4041>. Compose ánh xạ PostgreSQL ra cổng `5433`; bên trong mạng Docker, Spark vẫn dùng `postgres:5432`. Producer chạy trên Windows kết nối Kafka ở `localhost:9094`, còn Spark trong Compose dùng listener nội bộ `kafka:29092`. Các cổng này tránh đụng Kafka/PostgreSQL/Grafana/Spark UI của bản WESAD.

Chạy Spark trước khi producer để nhận toàn bộ lượt phát. Nếu cần dừng, dùng `docker compose -f deploy/docker-compose.yml down`; dữ liệu và checkpoint được giữ lại.

## Kết quả đo được (trên mẫu 39 MB, cửa sổ 200 mẫu ≈ 2s @100 Hz)
Huấn luyện/tách của `train` (1.741 cửa sổ; test 349; cửa sổ là ngã nếu ít nhất 50% mẫu mang nhãn ngã):

| Chỉ số | ADL | NGÃ |
|---|---|---|
| Precision | 0,91 | 0,81 |
| Recall | 0,96 | **0,66** |
| F1 | 0,93 | **0,72** |

ROC-AUC = **0,9471**. Confusion matrix (test): TN=261, FP=12, FN=26, TP=50.

Các chỉ số này lấy từ một lần train mới với cách gán nhãn cửa sổ đã sửa. Nếu đang dùng model có sẵn từ lần train trước, chạy lại lệnh train ở trên để cập nhật model và `models/metrics.json`.

Đặc trưng quan trọng nhất: `acc_y_mean`, `acc_x_mean`, `acc_z_mean`, `acc_mag_max`.

## Các quyết định kỹ thuật (để báo cáo không bị lệch)
1. **`stddev_pop` trong Spark** khớp `numpy.std` (population std) — dùng `stddev_samp`
   sẽ lệch đặc trưng giữa huấn luyện và streaming.
2. **`label` chỉ dùng để đánh giá**, không đưa vào đặc trưng; nhãn cửa sổ = tỉ lệ mẫu
   `label=1` ≥ 0,5.
3. CSV gốc **không có timestamp** → producer tổng hợp `timestamp = start + i/sample_rate`;
   `sample_rate` mặc định 100 Hz, đổi bằng `--sample-rate`.
4. Tái dùng ~80% hạ tầng repo cũ (`compose.yaml`, Spark job, Model Registry, Grafana);
   thay reader, schema, model và dashboard.
5. **Hạn chế:** chia train/test ngẫu nhiên theo cửa sổ; dữ liệu thật nên chia theo
   người/session để tránh leakage. Kiểm tra offline không đo độ trễ end-to-end; cần bật
   Docker Compose để thử toàn bộ Kafka → Spark → PostgreSQL.

## Bước tiếp theo (đề xuất)
- Chạy thật `docker compose up` + đo latency producer→alert.
- Tăng `--window-samples` / thử thêm model (GradientBoosting) và so sánh.
- Thêm module nhịp tim/giấc ngủ nếu muốn giữ chủ đề cũ.
