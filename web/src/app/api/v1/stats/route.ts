/**
 * GET /api/v1/stats — Global stats: event counts, supply, last event timestamp.
 */

export const dynamic = "force-dynamic";

import { queryStats } from "@/lib/api/db";
import { checkRateLimit, getClientIp } from "@/lib/api/rate-limit";
import { ok, rateLimitExceeded, serverError, optionsResponse } from "@/lib/api/response";

export async function OPTIONS() {
  return optionsResponse();
}

export async function GET(request: Request) {
  const ip = getClientIp(request);
  const rl = checkRateLimit(ip);
  if (!rl.allowed) return rateLimitExceeded(rl);

  try {
    const stats = queryStats();
    return ok(stats, rl);
  } catch (err) {
    console.error("[GET /api/v1/stats]", err);
    return serverError();
  }
}
