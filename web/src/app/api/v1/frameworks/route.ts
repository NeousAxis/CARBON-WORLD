/**
 * GET /api/v1/frameworks — Aggregates across the 7 UN reference frameworks.
 *
 * Parses positive/negative aspect JSON to count framework hits and sum
 * magnitudes (positive vs negative), plus an SDG histogram (1-17).
 *
 * Query params (all optional): region, country, decision, since, until.
 */

export const dynamic = "force-dynamic";

import { queryFrameworks } from "@/lib/api/intel";
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
    const region = searchParams.get("region");
    const country = searchParams.get("country");
    const decision = searchParams.get("decision")?.toUpperCase();
    const since = searchParams.get("since");
    const until = searchParams.get("until");

    if (decision && !VALID_DECISIONS.has(decision)) {
      return badRequest("Invalid decision filter. Must be one of: BURN, MINT, NEUTRAL");
    }
    for (const [name, val] of [["since", since], ["until", until]] as const) {
      if (val && isNaN(new Date(val).getTime())) {
        return badRequest(`Invalid '${name}' parameter. Must be ISO8601 datetime.`);
      }
    }

    const data = queryFrameworks({
      region: region ?? undefined,
      country: country ?? undefined,
      decision,
      since: since ?? undefined,
      until: until ?? undefined,
    });
    return ok(data, rl);
  } catch (err) {
    console.error("[GET /api/v1/frameworks]", err);
    return serverError();
  }
}
