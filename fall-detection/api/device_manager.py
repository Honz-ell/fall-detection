"""Device Manager API: inventory, labels, locations, and enabled state."""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from api.common import connect

app = FastAPI(title="FallAllD Device Manager API", version="1.0.0")


class DeviceCreate(BaseModel):
    device_id: str = Field(min_length=1, max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=120)
    location: Optional[str] = Field(default=None, max_length=160)
    assigned_to: Optional[str] = Field(default=None, max_length=160)


class DeviceUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=120)
    location: Optional[str] = Field(default=None, max_length=160)
    assigned_to: Optional[str] = Field(default=None, max_length=160)
    active: Optional[bool] = None


def initialize():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fall_devices (
                device_id TEXT PRIMARY KEY,
                display_name TEXT,
                location TEXT,
                assigned_to TEXT,
                active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_seen TIMESTAMPTZ
            )
        """)


@app.on_event("startup")
def startup():
    initialize()


@app.get("/health")
def health():
    try:
        initialize()
        return {"ok": True, "service": "device-manager"}
    except Exception as exc:
        raise HTTPException(503, f"PostgreSQL unavailable: {exc}") from exc


@app.get("/devices")
def list_devices():
    initialize()
    with connect() as conn:
        conn.execute("""
            INSERT INTO fall_devices (device_id, last_seen)
            SELECT device_id, MAX(ingested_at) FROM fall_window_aggregates GROUP BY device_id
            ON CONFLICT (device_id) DO UPDATE SET
              last_seen=GREATEST(fall_devices.last_seen, EXCLUDED.last_seen)
        """)
        rows = conn.execute("""
            SELECT d.device_id, COALESCE(d.display_name, d.device_id), d.location, d.assigned_to,
                   d.active, d.created_at, d.last_seen,
                   COALESCE(s.window_count, 0), s.last_window
            FROM fall_devices d
            LEFT JOIN (
              SELECT device_id, COUNT(*) AS window_count, MAX(window_start) AS last_window
              FROM fall_window_aggregates GROUP BY device_id
            ) s USING (device_id)
            ORDER BY d.device_id
        """).fetchall()
    return {"devices": [
        {"device_id": r[0], "display_name": r[1], "location": r[2], "assigned_to": r[3],
         "active": r[4], "created_at": r[5], "last_seen": r[6], "window_count": r[7],
         "last_window": r[8], "connected": r[6] is not None}
        for r in rows
    ]}


@app.post("/devices", status_code=201)
def add_device(payload: DeviceCreate):
    initialize()
    try:
        with connect() as conn:
            row = conn.execute("""
                INSERT INTO fall_devices (device_id, display_name, location, assigned_to)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (device_id) DO UPDATE SET
                  display_name=COALESCE(EXCLUDED.display_name, fall_devices.display_name),
                  location=COALESCE(EXCLUDED.location, fall_devices.location),
                  assigned_to=COALESCE(EXCLUDED.assigned_to, fall_devices.assigned_to)
                RETURNING device_id, display_name, location, assigned_to, active
            """, (payload.device_id, payload.display_name, payload.location, payload.assigned_to)).fetchone()
        return {"device_id": row[0], "display_name": row[1], "location": row[2],
                "assigned_to": row[3], "active": row[4]}
    except Exception as exc:
        raise HTTPException(409, str(exc)) from exc


@app.patch("/devices/{device_id}")
def update_device(device_id: str, payload: DeviceUpdate):
    initialize()
    updates = payload.dict(exclude_unset=True)
    if not updates:
        raise HTTPException(400, "No device fields supplied")
    with connect() as conn:
        conn.execute("INSERT INTO fall_devices (device_id) VALUES (%s) ON CONFLICT DO NOTHING", (device_id,))
        assignments = ", ".join(f"{column}=%s" for column in updates)
        params = list(updates.values()) + [device_id]
        row = conn.execute(
            f"UPDATE fall_devices SET {assignments} WHERE device_id=%s "
            "RETURNING device_id, display_name, location, assigned_to, active", params
        ).fetchone()
    return {"device_id": row[0], "display_name": row[1], "location": row[2],
            "assigned_to": row[3], "active": row[4]}
