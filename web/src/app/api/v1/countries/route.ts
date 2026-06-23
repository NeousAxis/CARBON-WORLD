/**
 * GET /api/v1/countries — Per-country geo-economic aggregates + ethical index.
 *
 * Query params (all optional):
 *   region   — restrict to one world region
 *   since, until (ISO8601), decision (BURN|MINT|NEUTRAL)
 *   sort     — events (default) | index_desc | index_asc
 *   limit    — max rows (1-200, default 50)
 */

export const dynamic = "force-dynamic";

import { queryCountries } from "@/lib/api/intel";
import { checkRateLimit, getClientIp } from "@/lib/api/rate-limit";
import { ok, rateLimitExceeded, badRequest, serverError, optionsResponse } from "@/lib/api/response";

const VALID_DECISIONS = new Set(["BURN", "MINT", "NEUTRAL"]);
const VALID_SORTS = new Set(["events", "index_desc", "index_asc"]);

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
    const since = searchParams.get("since");
    const until = searchParams.get("until");
    const decision = searchParams.get("decision")?.toUpperCase();
    const sort = searchParams.get("sort") ?? "events";
    const rawLimit = searchParams.get("limit");

    for (const [name, val] of [["since", since], ["until", until]] as const) {
      if (val && isNaN(new Date(val).getTime())) {
        return badRequest(`Invalid '${name}' parameter. Must be ISO8601 datetime.`);
      }
    }
    if (decision && !VALID_DECISIONS.has(decision)) {
      return badRequest("Invalid decision filter. Must be one of: BURN, MINT, NEUTRAL");
    }
    if (!VALID_SORTS.has(sort)) {
      return badRequest("Invalid 'sort'. Must be one of: events, index_desc, index_asc");
    }

    let limit = rawLimit ? parseInt(rawLimit, 10) : 50;
    if (isNaN(limit) || limit < 1) limit = 50;
    if (limit > 200) limit = 200;

    const data = queryCountries(
      { region: region ?? undefined, since: since ?? undefined, until: until ?? undefined, decision },
      { sort: sort as "events" | "index_desc" | "index_asc", limit }
    );
    return ok(data, rl);
  } catch (err) {
    console.error("[GET /api/v1/countries]", err);
    return serverError();
  }
}
