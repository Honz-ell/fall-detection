# Phát hiện té ngã thời gian thực — FallAllD-Wrist

Prototype học thuật minh họa pipeline **Kafka → Spark Structured Streaming → PostgreSQL → Random Forest scorer → Grafana** trên dữ liệu cảm biến đeo cổ tay. Có kèm HTML demo tự chứa và slide thuyết trình tiếng Việt.

> **An toàn và tính trung thực:** hệ thống không phải thiết bị y tế, không chẩn đoán và không tự liên hệ dịch vụ khẩn cấp. `data/fallalld_demo_synthetic.csv`, `models/rf_fall.joblib` và metric hiện có được tạo từ dữ liệu synthetic để kiểm thử pipeline; không đại diện kết quả trên FallAllD thật. Chưa có full CSV trong workspace. Không dùng các metric synthetic để kết luận hiệu năng.

## Nội dung

- `src/fall/common.py`: hợp đồng feature, cửa sổ và ngưỡng.
- `src/train.py`: đọc CSV theo chunk, chia theo thời gian, train RF, ghi model và `metrics.json`.
- `src/make_demo_sample.py`: tạo dữ liệu synthetic có chú thích.
- `src/producer.py`: phát JSON theo tốc độ 238 mẫu/giây cho mỗi device hoặc chạy dry-run.
- `src/spark_stream.py`: Kafka → event-time windows → PostgreSQL.
- `src/scorer.py`: đọc feature chưa chấm, dự đoán FALL/ADL và tạo alert.
- `sql/schema.sql`: bảng feature, predictions, alerts, model/device registry, view.
- `docker-compose.yml`, `Dockerfile`: stack Kafka KRaft, PostgreSQL 16, Spark 3.5, trainer, producer, scorer, Grafana.
- `grafana/provisioning/`: datasource và dashboard.
- `dashboard_demo.html`: demo trình duyệt độc lập, dữ liệu giả lập.
- `docs/FallAllD_BigData_Demo.pptx`: 14 slide tiếng Việt, có speaker notes.
- `tests/test_bigdata_pipeline.py`: kiểm thử offline, không cần Docker/Kafka/DB.

## Quy ước dữ liệu và giả định

- 238 Hz, 2 giây/cửa sổ ⇒ **476 mẫu**. Kích thước CSV chunk phải là bội số của 476; cửa sổ không bị ghép qua chunk.
- Theo số liệu đề bài 11.971.400 mẫu: `11,971,400 / 476 = 25,150` cửa sổ. Đây là phép tính theo con số đầu vào, không xác nhận nội dung file tải về.
- Cần 7 cột: `acc_x, acc_y, acc_z, label, gyro_x, gyro_y, gyro_z`.
- Cửa sổ là FALL khi `mean(label) >= 0.5`.
- Có 11 feature: acc magnitude (mean, sample std `ddof=1`, min, max, range), std của ba trục acc, gyro magnitude (mean, sample std `ddof=1`, max). **Label không được đưa vào model feature.**
- Chia train/test theo thời gian 80/20, không shuffle; RF 300 cây, `balanced_subsample`.
- Stream drop cửa sổ có ít hơn `ceil(0.9 × 476) = 429` mẫu. Ngưỡng mặc định 0.70; cooldown alert mặc định 10 giây/device.
- Dataset không có user ID/timestamp theo yêu cầu dữ liệu này; producer gán ID thiết bị tổng hợp và event-time theo thứ tự mẫu. Không thể đánh giá generalization theo người nếu thiếu metadata tương ứng.

## Chạy kiểm thử offline

Linux/macOS:

```bash
cd fall-detection
python -m venv .venv
source .venv/bin/activate
python -m pip install numpy==2.1.3 pandas==2.2.3 scikit-learn==1.5.2 joblib==1.4.2 kafka-python==2.0.2 psycopg[binary]==3.2.3 python-pptx==1.0.2 pillow==11.1.0
python -m unittest discover -s tests -p 'test_bigdata_pipeline.py' -v
```

PowerShell:

```powershell
cd D:\DLLL\data-repo\fall-detection
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install numpy==2.1.3 pandas==2.2.3 scikit-learn==1.5.2 joblib==1.4.2 kafka-python==2.0.2 "psycopg[binary]==3.2.3" python-pptx==1.0.2 pillow==11.1.0
python -m unittest discover -s tests -p test_bigdata_pipeline.py -v
```

## Tải và train FallAllD thật

Tải CSV đầy đủ khoảng 1.37 GB (cần truy cập Hugging Face từ máy của bạn):

```bash
bash data/download_fallalld.sh
```

Trên PowerShell, có thể tải đúng file CSV theo URL ghi trong script bằng `Invoke-WebRequest`/`curl.exe`; tránh commit dữ liệu lớn. Sau đó:

```bash
python src/train.py --data data/fallalld_processed_wrist-acc-gyro.csv --data-origin real
```

Windows PowerShell dùng cùng lệnh `python src/train.py ...`. Kết quả sẽ ghi `models/rf_fall.joblib` và `models/metrics.json`; xem trường `data_origin` trước khi trích metrics. Script cần ít nhất 10 cửa sổ hoàn chỉnh và cả hai lớp trong tập train. Số metric chỉ có ý nghĩa theo dữ liệu/nhãn và quy tắc chia tập cụ thể; chưa có đánh giá theo participant/session.

## Docker Compose

Yêu cầu Docker Engine/Desktop và Docker Compose v2. `wesad-kafka` của môi trường người dùng đang dùng host port 9092 nên cấu hình project này dùng Kafka host port **19092** và PostgreSQL **5434**, tránh xung đột; Grafana mặc định **3000**.

```bash
cd fall-detection
# 1. Tạo model demo synthetic (không dùng làm kết quả thực)
python src/make_demo_sample.py --windows 40 --output data/fallalld_demo_synthetic.csv
python src/train.py --data data/fallalld_demo_synthetic.csv --data-origin synthetic
# 2. Khởi động

docker compose up --build
```

Lệnh dừng: `docker compose down`. Dữ liệu lưu trong volumes Docker. Compose và tích hợp Spark/Kafka/DB cần được chạy trên máy có Docker để xác nhận môi trường; bài test offline không thay thế integration test.

Các tham số môi trường quan trọng (xem `docker-compose.yml`): `FALL_THRESHOLD` (0–1, mặc định 0.70), `ALERT_COOLDOWN_SECONDS` (mặc định 10), `WINDOW_SECONDS` (2), `WATERMARK_SECONDS` (4), cùng Kafka/PostgreSQL connection settings. Nếu tự chạy các tiến trình ngoài Compose, cần cài PySpark tương thích Spark 3.5 và các dependency Python trong services.

Grafana: `http://localhost:3000` (credential demo trong compose; chỉ dùng local). PostgreSQL từ host: `localhost:5434`; Kafka bootstrap từ host: `localhost:19092`. Không mở stack demo ra Internet.

## HTML dashboard mô phỏng

Mở trực tiếp `dashboard_demo.html` trong trình duyệt. Không cần package/CDN/server. Màn hình gồm pipeline 6 bước, KPI, 3 người theo dõi, canvas lịch sử cửa sổ, nút mô phỏng tình huống, cảnh báo, xác nhận/báo nhầm, điều chỉnh ngưỡng, sáng/tối và responsive. Nhãn **“DEMO MÔ PHỎNG, số liệu giả lập”** luôn thể hiện rõ. Tương tác không gửi SMS/cuộc gọi và không ghi DB.

## Slide

`docs/FallAllD_BigData_Demo.pptx` có 14 slide 16:9, tiếng Việt và speaker notes. Các slide preview PNG và contact sheet nằm trong `docs/slides_preview/`; tạo lại bằng:

```bash
python tools/build_presentation.py
```

Script kiểm tra kích thước/fit text trước khi render PNG; PPTX nhúng các ảnh đã kiểm tra cùng notes. Nếu thay nội dung slide, chạy lại script và xem `contact_sheet.png`. LibreOffice/PowerPoint renderer không có sẵn trong môi trường xây dựng nên chưa kiểm tra hiển thị bằng ứng dụng PowerPoint thực tế.

## Hạn chế / trước khi triển khai

1. Tải và xác thực CSV thật, sample rate, nhãn, row count và nguồn dữ liệu.
2. Chạy train, kiểm tra metrics.json, rồi thay model demo.
3. Chạy Compose và kiểm thử schema/SQL/stream end-to-end; đo độ trễ, throughput, restart/replay và xử lý duplicate.
4. Đánh giá theo người/session nếu có metadata; cân nhắc calibration và chi phí false negatives/positives.
5. Thiết lập quy trình xác minh con người, bảo mật, quyền riêng tư, vận hành và kiểm định lâm sàng thích hợp trước mọi mục đích chăm sóc thật.

Không có metric trên full FallAllD hoặc kết quả đo runtime được tuyên bố trong repo này.
