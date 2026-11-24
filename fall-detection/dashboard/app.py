#!/usr/bin/env python3
"""Tiny local web dashboard for the FallAllD demo (no extra web framework)."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import psycopg

ROOT = Path(__file__).resolve().parent


def json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Cannot JSON-encode {type(value).__name__}")


def read_dashboard_data(dsn: str) -> dict:
    with psycopg.connect(dsn, connect_timeout=3) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FILTER (WHERE window_start >= NOW() - INTERVAL '15 minutes'),
                       COUNT(DISTINCT device_id), MAX(window_start), MAX(ingested_at)
                FROM fall_window_aggregates
            """)
            windows_15m, devices, latest_window, latest_ingested = cur.fetchone()

            cur.execute("""
                SELECT window_start, device_id, sample_count, acc_mag_mean, acc_mag_max,
                       gyro_mag_mean, fall_samples
                FROM fall_window_aggregates
                ORDER BY window_start DESC LIMIT 1
            """)
            row = cur.fetchone()
            latest = None if row is None else {
                "window_start": row[0], "device_id": row[1], "sample_count": row[2],
                "acc_mag_mean": row[3], "acc_mag_max": row[4],
                "gyro_mag_mean": row[5], "fall_samples": row[6],
            }

            cur.execute("""
                SELECT COUNT(*) FILTER (WHERE NOT acknowledged),
                       COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '15 minutes')
                FROM fall_alerts
            """)
            open_alerts, alerts_15m = cur.fetchone()

            cur.execute("""
                SELECT a.window_start, a.device_id, a.acc_mag_max,
                       COALESCE(p.prediction, CASE WHEN a.fall_samples > 0 THEN 'FALL' ELSE 'ADL' END),
                       COALESCE(p.score, 0), a.sample_count, a.fall_samples
                FROM fall_window_aggregates a
                LEFT JOIN fall_predictions p
                  ON p.device_id = a.device_id AND p.window_start = a.window_start
                ORDER BY a.window_start DESC LIMIT 60
            """)
            timeline = [dict(zip(
                ("time", "device_id", "acc_mag_max", "prediction", "score", "sample_count", "fall_samples"), r
            )) for r in reversed(cur.fetchall())]

            cur.execute("""
                SELECT a.id, a.created_at, a.device_id, a.window_start, a.score, a.acknowledged,
                       w.acc_mag_max, w.acc_mag_mean, w.gyro_mag_mean, w.sample_count
                FROM fall_alerts a
                LEFT JOIN fall_window_aggregates w
                  ON w.device_id = a.device_id AND w.window_start = a.window_start
                ORDER BY a.created_at DESC LIMIT 8
            """)
            fields = ("id", "created_at", "device_id", "window_start", "score", "acknowledged",
                      "acc_mag_max", "acc_mag_mean", "gyro_mag_mean", "sample_count")
            alerts = [dict(zip(fields, r)) for r in cur.fetchall()]

    return {
        "ok": True,
        "summary": {
            "windows_15m": windows_15m or 0,
            "devices": devices or 0,
            "latest_window": latest_window,
            "latest_ingested": latest_ingested,
            "open_alerts": open_alerts or 0,
            "alerts_15m": alerts_15m or 0,
            "latest": latest,
        },
        "timeline": timeline,
        "alerts": alerts,
    }


def make_handler(dsn: str):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/dashboard":
                try:
                    payload = json.dumps(read_dashboard_data(dsn), default=json_default).encode("utf-8")
                    self.send_response(200)
                except Exception as exc:
                    payload = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                    self.send_response(503)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if path in ("/", "/index.html"):
                content = (ROOT / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            self.send_error(404)

        def do_POST(self):  # noqa: N802
            match = re.fullmatch(r"/api/alerts/(\d+)/acknowledge", urlparse(self.path).path)
            if not match:
                self.send_error(404)
                return
            try:
                with psycopg.connect(dsn, connect_timeout=3) as conn:
                    row = conn.execute(
                        "UPDATE fall_alerts SET acknowledged = TRUE WHERE id = %s RETURNING id",
                        (int(match.group(1)),),
                    ).fetchone()
                if row is None:
                    self.send_error(404, "Không tìm thấy cảnh báo")
                    return
                payload = json.dumps({"ok": True, "id": row[0]}).encode("utf-8")
                self.send_response(200)
            except Exception as exc:
                payload = json.dumps({"ok": False, "error": str(exc)}).encode("utf-8")
                self.send_response(503)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt, *args):
            print(f"[{self.log_date_time_string()}] {fmt % args}")

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local FallAllD live dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    parser.add_argument("--postgres-url", default=os.getenv(
        "FALL_POSTGRES_URL", "postgresql://falld:fall_dev_password@localhost:5433/falldetect"
    ))
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.postgres_url))
    print(f"FallAllD dashboard: http://localhost:{args.port}  (Ctrl+C để dừng)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng dashboard.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
