/**
 * auth.ts — Bearer token verification for Tier 2 Partner API.
 *
 * Reads Authorization: Bearer <token>, hashes it with SHA-256,
 * queries api_keys table, updates last_used_at, and returns the key record.
 *
 * Usage in a route handler:
 *   const key = await verifyBearer(request);
 *   if (!key) return unauthorized();
 */

import { createHash } from "crypto";
import Database from "better-sqlite3";
import path from "path";

// ---------------------------------------------------------------------------
// DB connection (write-capable — needed for last_used_at update)
// ---------------------------------------------------------------------------

let _db: Database.Database | null = null;

function getAuthDb(): Database.Database {
  if (_db) return _db;
  const dbPath =
    process.env.CARBON_DB_PATH ||
    path.join(process.cwd(), "..", "data", "carbon.db");
  _db = new Database(dbPath, { readonly: false, fileMustExist: true });
  _db.pragma("journal_mode = WAL");
  return _db;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ApiKeyRecord {
  id: number;
  organization: string;
  contact_email: string;
  tier: "partner" | "enterprise";
  read_quota_daily: number;
  write_quota_daily: number;
  webhook_url: string | null;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Core verification
// ---------------------------------------------------------------------------

/**
 * Verify a Bearer token from the Authorization header.
 * Returns the key record if valid and not revoked, null otherwise.
 * Also updates last_used_at on a successful lookup.
 */
export async function verifyBearer(
  request: Request
): Promise<ApiKeyRecord | null> {
  const authHeader = request.headers.get("Authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) return null;

  const rawToken = authHeader.slice(7).trim();
  if (!rawToken) return null;

  const keyHash = createHash("sha256").update(rawToken).digest("hex");

  try {
    const db = getAuthDb();
    const row = db
      .prepare(
        `SELECT id, organization, contact_email, tier,
                read_quota_daily, write_quota_daily,
                webhook_url, created_at
         FROM api_keys
         WHERE key_hash = ? AND revoked_at IS NULL`
      )
      .get(keyHash) as ApiKeyRecord | undefined;

    if (!row) return null;

    // Update last_used_at (best-effort, no throw)
    try {
      db.prepare(
        "UPDATE api_keys SET last_used_at = ? WHERE id = ?"
      ).run(new Date().toISOString(), row.id);
    } catch {
      // Non-fatal
    }

    return row;
  } catch (err) {
    console.error("[auth.verifyBearer]", err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Response helpers for auth failures
// ---------------------------------------------------------------------------

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

export function unauthorized(message = "Invalid or missing API key"): Response {
  return new Response(
    JSON.stringify({ error: "unauthorized", message }),
    {
      status: 401,
      headers: {
        ...CORS_HEADERS,
        "Content-Type": "application/json",
        "WWW-Authenticate": 'Bearer realm="CARBON WORLD API"',
      },
    }
  );
}

export function forbidden(message = "Forbidden"): Response {
  return new Response(JSON.stringify({ error: "forbidden", message }), {
    status: 403,
    headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
  });
}
