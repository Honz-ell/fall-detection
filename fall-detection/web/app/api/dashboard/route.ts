import { NextResponse } from "next/server";
import { Pool } from "pg";

export const dynamic = "force-dynamic";
const globalForPg = globalThis as typeof globalThis & { fallPool?: Pool };
const pool = globalForPg.fallPool ?? new Pool({
  connectionString: process.env.FALL_POSTGRES_URL || "postgresql://falld:fall_dev_password@localhost:5433/falldetect",
  max: 5,
  connectionTimeoutMillis: 3000,
});
if (process.env.NODE_ENV !== "production") globalForPg.fallPool = pool;

export async function GET() {
  try {
    const client = await pool.connect();
    try {
      const [summary, latest, alerts, timeline] = await Promise.all([
        client.query(`SELECT COUNT(*) FILTER (WHERE window_start >= NOW() - INTERVAL '15 minutes')::int AS windows_15m,
                             COUNT(DISTINCT device_id)::int AS devices,
                             MAX(window_start) AS latest_window, MAX(ingested_at) AS latest_ingested
                      FROM fall_window_aggregates`),
        client.query(`SELECT window_start, device_id, sample_count, acc_mag_mean, acc_mag_max,
                             gyro_mag_mean, fall_samples
                      FROM fall_window_aggregates ORDER BY window_start DESC LIMIT 1`),
        client.query(`SELECT a.id, a.created_at, a.device_id, a.window_start, a.score, a.acknowledged,
                             w.acc_mag_max, w.acc_mag_mean, w.gyro_mag_mean, w.sample_count
                      FROM fall_alerts a LEFT JOIN fall_window_aggregates w
                        ON w.device_id=a.device_id AND w.window_start=a.window_start
                      ORDER BY a.created_at DESC LIMIT 8`),
        client.query(`SELECT a.window_start AS time, a.device_id, a.acc_mag_max,
                             COALESCE(p.prediction, CASE WHEN a.fall_samples > 0 THEN 'FALL' ELSE 'ADL' END) AS prediction,
                             COALESCE(p.score, 0) AS score, a.sample_count, a.fall_samples
                      FROM fall_window_aggregates a LEFT JOIN fall_predictions p
                        ON p.device_id=a.device_id AND p.window_start=a.window_start
                      ORDER BY a.window_start DESC LIMIT 60`),
      ]);
      const counts = await client.query(`SELECT COUNT(*) FILTER (WHERE NOT acknowledged)::int AS open_alerts,
                                                COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '15 minutes')::int AS alerts_15m
                                         FROM fall_alerts`);
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
