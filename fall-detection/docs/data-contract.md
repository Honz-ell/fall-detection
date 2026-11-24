# Data contract: `wearable.fall.v1`

Mỗi bản ghi là **một mẫu cảm biến** (accel + gyro cùng lúc) của một thiết bị đeo cổ tay.

```json
{
  "schema_version": "wearable.fall.v1",
  "device_id": "WRIST-01",
  "sample_index": 12345,
  "timestamp": "2026-11-23T10:00:00.000Z",
  "acc_x": 9.26, "acc_y": 1.43, "acc_z": -2.51,
  "gyro_x": 0.043, "gyro_y": 0.023, "gyro_z": 0.039,
  "label": 0
}
```

- `device_id`: ID thiết bộ mô phỏng (CSV gốc không có subject theo dòng → gán cố định hoặc theo segment).
- `sample_index`: số thứ tự mẫu trong file.
- `timestamp`: CSV **không có thời gian**; producer tổng hợp = `start + sample_index / sample_rate`.
- `label`: `0` = sinh hoạt thường ngày (ADL), `1` = ngã. **Chỉ dùng để đánh giá, không đưa vào đặc trưng huấn luyện real-time.**
- Cuối replay, producer gửi bản tin `sensor="__CONTROL__"` để Spark chốt cửa sổ cuối.
