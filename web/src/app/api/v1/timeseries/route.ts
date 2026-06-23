/**
 * GET /api/v1/timeseries — Event / supply / index over time.
 *
 * Query params (all optional):
 *   interval — day (default) | week | month
 *   region, country, decision — geo / decision filters
 *   since, until (ISO8601)
 */

export const dynamic = "force-dynamic";

import { queryTimeseries } from "@/lib/api/intel";
import { checkRateLimit, getClientIp } from "@/lib/api/rate-limit";
import { ok, rateLimitExceeded, badRequest, serverError, optionsResponse } from "@/lib/api/response";

const VALID_DECISIONS = new Set(["BURN", "MINT", "NEUTRAL"]);
const VALID_INTERVALS = new Set(["day", "week", "month"]);

export async function OPTIONS() {
  return optionsResponse();
}

export async function GET(request: Request) {
  const ip = getClientIp(request);
  const rl = checkRateLimit(ip);
  if (!rl.allowed) return rateLimitExceeded(rl);

  try {
    const { searchParams } = new URL(request.url);
    const interval = searchParams.get("interval") ?? "day";
    const region = searchParams.get("region");
    const country = searchParams.get("country");
    const decision = searchParams.get("decision")?.toUpperCase();
    const since = searchParams.get("since");
    const until = searchParams.get("until");

    if (!VALID_INTERVALS.has(interval)) {
      return badRequest("Invalid 'interval'. Must be one of: day, week, month");
    }
    if (decision && !VALID_DECISIONS.has(decision)) {
      return badRequest("Invalid decision filter. Must be one of: BURN, MINT, NEUTRAL");
    }
    for (const [name, val] of [["since", since], ["until", until]] as const) {
      if (val && isNaN(new Date(val).getTime())) {
        return badRequest(`Invalid '${name}' parameter. Must be ISO8601 datetime.`);
      }
    }

    const data = queryTimeseries(
      {
        region: region ?? undefined,
        country: country ?? undefined,
        decision,
        since: since ?? undefined,
        until: until ?? undefined,
      },
      interval as "day" | "week" | "month"
    );
    return ok(data, rl);
  } catch (err) {
    console.error("[GET /api/v1/timeseries]", err);
    return serverError();
  }
}
