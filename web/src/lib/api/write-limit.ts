/**
 * write-limit.ts — Per-key write rate limiter for Tier 2 Partner API.
 *
 * Counts submissions in the api_usage table (or submissions table) for the
 * current UTC day and blocks if the key has hit its write_quota_daily.
 *
 * Backed by the submissions table: counts rows for api_key_id received today UTC
 * with status NOT IN ('rejected_invalid', 'rejected_duplicate').
 */

import Database from "better-sqlite3";
import path from "path";

let _db: Database.Database | null = null;

function getDb(): Database.Database {
  if (_db) return _db;
  const dbPath =
    process.env.CARBON_DB_PATH ||
    path.join(process.cwd(), "..", "data", "carbon.db");
  _db = new Database(dbPath, { readonly: true, fileMustExist: true });
  _db.pragma("journal_mode = WAL");
  return _db;
}

export interface WriteLimitResult {
  allowed: boolean;
  used: number;
  limit: number;
  reset_at: string; // ISO8601 — midnight UTC tonight
}

/**
 * Check whether the given api_key_id has remaining write quota for today UTC.
 * Returns { allowed, used, limit, reset_at }.
 */
export function checkWriteLimit(
  apiKeyId: number,
  writeQuotaDaily: number
): WriteLimitResult {
  // Unlimited write quota (enterprise unlimited = 0 sentinel? not used here but guard it)
  if (writeQuotaDaily <= 0) {
    return {
      allowed: true,
      used: 0,
      limit: 0,
      reset_at: todayMidnightUTC(),
    };
  }

  const todayStart = new Date().toISOString().slice(0, 10); // "YYYY-MM-DD"

  let used = 0;
  try {
    const db = getDb();
    const row = db
      .prepare(
        `SELECT COUNT(*) AS c FROM submissions
         WHERE api_key_id = ?
           AND received_at >= ?
           AND status NOT IN ('rejected_invalid', 'rejected_duplicate')`
      )
      .get(apiKeyId, todayStart) as { c: number };
    used = row?.c ?? 0;
  } catch (err) {
    console.error("[write-limit] DB error, allowing request:", err);
    // Fail open — better to allow than to block all writes on DB error
    return {
      allowed: true,
      used: 0,
      limit: writeQuotaDaily,
      reset_at: todayMidnightUTC(),
    };
  }

  return {
    allowed: used < writeQuotaDaily,
    used,
    limit: writeQuotaDaily,
    reset_at: todayMidnightUTC(),
  };
}

/** ISO8601 string for tonight midnight UTC (start of tomorrow). */
function todayMidnightUTC(): string {
  const d = new Date();
  d.setUTCHours(24, 0, 0, 0);
  return d.toISOString();
}

/** Build a 429 response body for write quota exceeded. */
export function writeQuotaExceeded(result: WriteLimitResult): Response {
  return new Response(
    JSON.stringify({
      error: "write_quota_exceeded",
      used: result.used,
      limit: result.limit,
      reset_at: result.reset_at,
    }),
    {
      status: 429,
      headers: {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Retry-After": String(
          Math.ceil((new Date(result.reset_at).getTime() - Date.now()) / 1000)
        ),
      },
    }
  );
}
