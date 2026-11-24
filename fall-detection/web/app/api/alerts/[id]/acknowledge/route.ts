import { NextResponse } from "next/server";
import { Pool } from "pg";

const globalForPg = globalThis as typeof globalThis & { fallPool?: Pool };
const pool = globalForPg.fallPool ?? new Pool({
  connectionString: process.env.FALL_POSTGRES_URL || "postgresql://falld:fall_dev_password@localhost:5433/falldetect",
  max: 5,
  connectionTimeoutMillis: 3000,
});
if (process.env.NODE_ENV !== "production") globalForPg.fallPool = pool;

export async function POST(_request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  if (!/^\d+$/.test(id)) return NextResponse.json({ ok: false, error: "Invalid alert ID" }, { status: 400 });
  try {
    const result = await pool.query("UPDATE fall_alerts SET acknowledged=TRUE WHERE id=$1 RETURNING id", [id]);
    if (!result.rowCount) return NextResponse.json({ ok: false, error: "Alert not found" }, { status: 404 });
    return NextResponse.json({ ok: true, id: result.rows[0].id });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Database error";
    return NextResponse.json({ ok: false, error: message }, { status: 503 });
  }
}
