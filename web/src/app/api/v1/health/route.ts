/**
 * GET /api/v1/health — Liveness probe.
 *
 * Returns 200 { status: "ok", db_reachable: true, ... } when healthy.
 * Returns 503 { status: "degraded", db_reachable: false, ... } when DB is unreachable.
 * Not rate-limited — this endpoint is used by monitoring probes.
 */

export const dynamic = "force-dynamic";

import { isDbReachable } from "@/lib/api/db";
import { ok, serviceUnavailable, optionsResponse } from "@/lib/api/response";
import type { RateLimitResult } from "@/lib/api/rate-limit";

const API_VERSION = "1.0.0";

// Synthetic unlimited RateLimitResult for health endpoint (no rate limiting)
const NO_RATE_LIMIT: RateLimitResult = {
  allowed: true,
  remaining: 100,
  reset: new Date(Date.now() + 24 * 60 * 60 * 1000),
  retryAfterSeconds: 0,
};

export async function OPTIONS() {
  return optionsResponse();
}

export async function GET() {
  const { ok: dbOk, last_event_at } = isDbReachable();

  const body = {
    status: dbOk ? "ok" : "degraded",
    version: API_VERSION,
    db_reachable: dbOk,
    last_event_at,
  };

  if (!dbOk) {
    return serviceUnavailable(body);
  }

  return ok(body, NO_RATE_LIMIT);
}
