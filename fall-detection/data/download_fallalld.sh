#!/usr/bin/env bash
# Tải bộ dữ liệu FallAllD (wrist - accelerometer + gyroscope) từ Hugging Face.
# Nguồn: https://huggingface.co/datasets/IdaFLab/FallAllD-Wrist
# Gốc: Saleh et al., "FallAllD: An Open Dataset of Human Falls and Activities of Daily Living",
#       IEEE Sensors Journal, 2021. DOI: 10.1109/JSEN.2020.3018335
set -euo pipefail
cd "$(dirname "$0")"

BASE="https://huggingface.co/datasets"

echo "[1/3] Tải bản CSV đầy đủ (~1.37 GB, 11.971.400 dòng)..."
curl -L --retry 3 -C - -o fallalld_wrist_full.csv \
  "$BASE/IdaFLab/FallAllD-Wrist/resolve/main/fallalld_processed_wrist-acc-gyro.csv"

echo "[2/3] Tải bản Parquet (2 phần ~240 MB mỗi phần, tổng ~480 MB)..."
curl -L --retry 3 -C - -o fallalld_part_0.parquet \
  "$BASE/IdaFLab/fallalld0/resolve/main/dataset_part_0.parquet"
curl -L --retry 3 -C - -o fallalld_part_1.parquet \
  "$BASE/IdaFLab/fallalld1/resolve/main/dataset_part_1.parquet"

echo "[3/3] Xong:"
ls -lh fallalld_wrist_full.csv fallalld_part_*.parquet
echo
echo "Lưu ý GitHub: file >100 MB cần Git LFS."
echo "  git lfs install"
echo "  git lfs track '*.csv' '*.parquet'"
