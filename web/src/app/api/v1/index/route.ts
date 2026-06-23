/**
 * GET /api/v1/index — Synthesized "state of the world" geo-economic index.
 *
 * One call returns: the global count-based ethical index, the per-region
 * index ranking, and the 7-day top movers (region index now vs the prior
 * 7-day window). Designed as a dashboard-as-API for partners / institutions.
 *
 * Not parameterized — always the full corpus, computed live.
 */

export const dynamic = "force-dynamic";

import { queryWorldIndex } from "@/lib/api/intel";
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
    const data = queryWorldIndex(new Date().toISOString());
    return ok(data, rl);
  } catch (err) {
    console.error("[GET /api/v1/index]", err);
    return serverError();
  }
}
