#!/usr/bin/env bash
# Download the single original FallAllD-Wrist CSV; the file is intentionally not tracked by Git.
set -euo pipefail
cd "$(dirname "$0")"
URL="https://huggingface.co/datasets/IdaFLab/FallAllD-Wrist/resolve/main/fallalld_processed_wrist-acc-gyro.csv"
OUT="fallalld_processed_wrist-acc-gyro.csv"
echo "Downloading $OUT (~1.37 GB; requires network access to Hugging Face)..."
curl --fail --location --retry 3 --continue-at - --output "$OUT" "$URL"
echo "Downloaded:"
ls -lh "$OUT"
echo "Expected contract from assignment: 11,971,400 rows; 7 columns. Validate with:"
echo "  python ../src/train.py --data $OUT --data-origin real"
