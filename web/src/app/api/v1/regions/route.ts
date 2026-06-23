/**
 * GET /api/v1/regions — Per-region geo-economic aggregates.
 *
 * Query params (all optional): since, until (ISO8601), decision (BURN|MINT|NEUTRAL).
 * Returns one entry per world region with the count-based ethical_index,
 * decision breakdown, mean_score, CBWD supply, and top countries.
 */

export const dynamic = "force-dynamic";

import { queryRegions } from "@/lib/api/intel";
import { checkRateLimit, getClientIp } from "@/lib/api/rate-limit";
import { ok, rateLimitExceeded, badRequest, serverError, optionsResponse } from "@/lib/api/response";

const VALID_DECISIONS = new Set(["BURN", "MINT", "NEUTRAL"]);

export async function OPTIONS() {
  return optionsResponse();
}

export async function GET(request: Request) {
  const ip = getClientIp(request);
  const rl = checkRateLimit(ip);
  if (!rl.allowed) return rateLimitExceeded(rl);

  try {
    const { searchParams } = new URL(request.url);
    const since = searchParams.get("since");
    const until = searchParams.get("until");
    const decision = searchParams.get("decision")?.toUpperCase();

    for (const [name, val] of [["since", since], ["until", until]] as const) {
      if (val && isNaN(new Date(val).getTime())) {
        return badRequest(`Invalid '${name}' parameter. Must be ISO8601 datetime.`);
      }
    }
    if (decision && !VALID_DECISIONS.has(decision)) {
      return badRequest("Invalid decision filter. Must be one of: BURN, MINT, NEUTRAL");
    }

    const data = queryRegions({
      since: since ?? undefined,
      until: until ?? undefined,
      decision,
    });
    return ok(data, rl);
  } catch (err) {
    console.error("[GET /api/v1/regions]", err);
    return serverError();
  }
}
