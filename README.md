# Phát hiện ngã cho người cao tuổi — FallAllD

Mã nguồn ở [`fall-detection/`](fall-detection/README.md). Pipeline gồm Producer → Kafka → Spark Structured Streaming → PostgreSQL → scorer → Grafana.

## Chạy thử

Mở PowerShell tại thư mục này:

```powershell
Set-Location .\fall-detection
python -m pip install -r requirements.txt
python tests/test_offline_pipeline.py
docker compose -f deploy/docker-compose.yml up -d
python producer/produce_fall.py --data data/fallalld_wrist_sample.csv --broker localhost:9094 --speed 60
python scorer/score_fall.py --model models/fall_rf.joblib --postgres-url postgresql://falld:fall_dev_password@localhost:5433/falldetect
```

Spark chạy trong Docker Compose. Grafana ở <http://localhost:3001> (`admin` / `admin`). Hướng dẫn chi tiết và giới hạn đánh giá nằm trong [`fall-detection/README.md`](fall-detection/README.md).
