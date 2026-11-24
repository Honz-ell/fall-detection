# FallAllD – Wrist (Fall Detection)

Bộ dữ liệu mẫu + script tải bản đầy đủ cho đề tài **phát hiện ngã cho người cao tuổi**.

## Nguồn
- Hugging Face: <https://huggingface.co/datasets/IdaFLab/FallAllD-Wrist>
- Gốc: M. Saleh, M. Abbas, R. Le Bouquin Jeannès, *"FallAllD: An Open Dataset of Human Falls and Activities of Daily Living"*, IEEE Sensors Journal, 2021. DOI: 10.1109/JSEN.2020.3018335
- Bản đầy đủ: 15 người, 3 vị trí cảm biến (thắt lưng / cổ tay / cổ), 26.420 file.
  Thư mục này dùng **wrist** (cổ tay): `acc_x,acc_y,acc_z,label,gyro_x,gyro_y,gyro_z`.

## Kích thước
| File | Dung lượng | Số dòng |
|---|---|---|
| `fallalld_wrist_sample.csv` (mẫu, có sẵn) | 39 MB | 348.316 |
| `fallalld_wrist_full.csv` (bản đầy đủ) | 1,37 GB | 11.971.400 |
| `fallalld_part_0.parquet` + `fallalld_part_1.parquet` | ~480 MB | 11.971.400 |

## Schema
| Cột | Ý nghĩa |
|---|---|
| `acc_x, acc_y, acc_z` | Gia tốc (m/s²), cảm biến cổ tay |
| `label` | `0` = hoạt động sinh hoạt thường ngày (ADL), `1` = ngã |
| `gyro_x, gyro_y, gyro_z` | Vận tốc góc (rad/s) |

Trong mẫu 39 MB: 272.156 dòng ADL (0) và 76.160 dòng ngã (1).

## Tải bản đầy đủ
```bash
bash download_fallalld.sh
```

## Đưa lên GitHub
GitHub giới hạn file **100 MB**. `fallalld_wrist_sample.csv` (39 MB) push thẳng được;
bản đầy đủ (1,37 GB) bắt buộc dùng **Git LFS**:
```bash
git lfs install
git lfs track "*.csv" "*.parquet"
git add .gitattributes data/
git commit -m "Add FallAllD wrist dataset (sample + downloader)"
git push
```
