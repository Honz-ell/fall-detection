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
- `data/fallalld_wrist_sample.csv` — 39 MB / 348.318 mẫu / 76.160 mẫu ngã (21,9%) để chạy thử.
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
| `grafana/fall-dashboard.json` | Dashboard Grafana |
| `dashboard/` | Giao diện web demo local, cập nhật dữ liệu PostgreSQL mỗi 5 giây |
| `tests/test_offline_pipeline.py` | Kiểm thử đầu–cuối không cần Kafka/Spark |

## Yêu cầu
- Docker + Docker Compose (Kafka/Postgres/Grafana)
- Python ≥ 3.10 (`requirements.txt`)
- `spark-submit` (PySpark 3.5) cho Spark job

## Chạy thử
```bash
make install                 # pip install -r requirements.txt
python train/train_fall_model.py --data data/fallalld_wrist_sample.csv
python tests/test_offline_pipeline.py --data data/fallalld_wrist_sample.csv

make up                      # kafka + postgres + grafana (:9092 / :5432 / :3000)
make producer                # phát dữ liệu vào Kafka
make spark                   # spark-submit job tổng hợp
make scorer                  # dự đoán + cảnh báo vào PostgreSQL
make down
```

### Mở giao diện demo trực quan

Khi PostgreSQL đang chạy, mở thêm PowerShell tại thư mục `fall-detection/`:

```powershell
python .\dashboard\app.py --postgres-url "postgresql://falld:fall_dev_password@localhost:5433/falldetect" --port 8501
```

Mở <http://localhost:8501>. Dashboard hiển thị trạng thái dữ liệu, số cửa sổ phân tích,
biểu đồ gia tốc, các dự đoán FALL/ADL và luồng xử lý. Với Compose dùng cổng PostgreSQL
mặc định, thay `5433` bằng `5432`. Dừng giao diện bằng `Ctrl+C`.

## Kết quả đo được (trên mẫu 39 MB, cửa sổ 200 mẫu ≈ 2s @100 Hz)
Huấn luyện/tách của `train` (1.741 cửa sổ; test 349):

| Chỉ số | ADL | NGÃ |
|---|---|---|
| Precision | 0,93 | 0,80 |
| Recall | 0,95 | 0,72 |
| F1 | 0,94 | **0,76** |

ROC-AUC = **0,9554**. Confusion matrix (test): TN=262, FP=13, FN=21, TP=53.

`scorer` chạy trên **toàn bộ** mẫu (gồm cả cửa sổ đã huấn luyện) được P=0,9615 /
R=0,9211 / F1=0,9409 — con số này **lạc quan**, dùng để kiểm thử pipeline chứ không
dùng báo cáo. Báo cáo lấy số của tập test ở trên.

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
   người/session để tránh leakage. Spark/Kafka chưa chạy trong sandbox (không có Docker),
   cần chạy thật trên máy có Docker để xác nhận độ trễ end-to-end.

## Bước tiếp theo (đề xuất)
- Chạy thật `docker compose up` + đo latency producer→alert.
- Tăng `--window-samples` / thử thêm model (GradientBoosting) và so sánh.
- Thêm module nhịp tim/giấc ngủ nếu muốn giữ chủ đề cũ.
