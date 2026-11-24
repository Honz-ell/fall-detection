import { NextResponse } from "next/server";
import { Pool } from "pg";

export const dynamic = "force-dynamic";
const globalForPg = globalThis as typeof globalThis & { fallPool?: Pool };
const pool = globalForPg.fallPool ?? new Pool({
  connectionString: process.env.FALL_POSTGRES_URL || "postgresql://falld:fall_dev_password@localhost:5434/falldetect",
  max: 5,
  connectionTimeoutMillis: 3000,
});
if (process.env.NODE_ENV !== "production") globalForPg.fallPool = pool;

export async function GET() {
  try {
    const client = await pool.connect();
    try {
      const [summary, latest, alerts, timeline, counts] = await Promise.all([
        client.query(`SELECT COUNT(*) FILTER (WHERE window_start >= NOW() - INTERVAL '15 minutes' AND window_start <= NOW())::int AS windows_15m,
                             COUNT(DISTINCT device_id)::int AS devices,
                             MAX(window_start) AS latest_window, MAX(ingested_at) AS latest_ingested
                      FROM window_features`),
        client.query(`SELECT window_start, device_id, sample_count, acc_mag_mean, acc_mag_max,
                             gyro_mag_mean, label_fraction AS fall_samples
                      FROM window_features ORDER BY window_start DESC LIMIT 1`),
        client.query(`SELECT a.id, a.created_at, a.device_id, a.window_start, a.probability AS score,
                             a.acknowledged, w.acc_mag_max, w.acc_mag_mean, w.gyro_mag_mean, w.sample_count
                      FROM alerts a LEFT JOIN window_features w
                        ON w.device_id=a.device_id AND w.window_start=a.window_start
                      ORDER BY a.created_at DESC LIMIT 8`),
        client.query(`SELECT w.window_start AS time, w.device_id, w.acc_mag_max,
                             COALESCE(p.prediction, CASE WHEN w.label_fraction >= 0.5 THEN 'FALL' ELSE 'ADL' END) AS prediction,
                             COALESCE(p.probability, 0) AS score, w.sample_count, w.label_fraction AS fall_samples
                      FROM window_features w LEFT JOIN predictions p
                        ON p.device_id=w.device_id AND p.window_start=w.window_start
                      ORDER BY w.window_start DESC LIMIT 60`),
        client.query(`SELECT COUNT(*) FILTER (WHERE disposition='OPEN' AND NOT acknowledged)::int AS open_alerts,
                             COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '15 minutes' AND created_at <= NOW())::int AS alerts_15m
                      FROM alerts`),
      ]);
      return NextResponse.json({
        ok: true,
        summary: { ...summary.rows[0], ...counts.rows[0], latest: latest.rows[0] || null },
        alerts: alerts.rows,
        timeline: timeline.rows.reverse(),
      }, { headers: { "Cache-Control": "no-store" } });
    } finally {
      client.release();
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Database connection failed";
    return NextResponse.json({ ok: false, error: message }, { status: 503 });
  }
}
