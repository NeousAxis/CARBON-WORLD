/**
 * GET /api/v1/events — Paginated list of scored events.
 *
 * Query params:
 *   limit   int    default 20, max 100
 *   offset  int    default 0
 *   decision  "BURN" | "MINT" | "NEUTRAL"  (optional filter)
 *   since   ISO8601 datetime  (optional, filter created_at >= since)
 *   source  string            (optional, LIKE %source%)
 */

export const dynamic = "force-dynamic";

import { queryEvents } from "@/lib/api/db";
import { checkRateLimit, getClientIp } from "@/lib/api/rate-limit";
import { ok, rateLimitExceeded, badRequest, serverError, optionsResponse } from "@/lib/api/response";

const VALID_DECISIONS = new Set(["BURN", "MINT", "NEUTRAL"]);

export async function OPTIONS() {
  return optionsResponse();
}

export async function GET(request: Request) {
  // Rate limiting
  const ip = getClientIp(request);
  const rl = checkRateLimit(ip);
  if (!rl.allowed) return rateLimitExceeded(rl);

  try {
    const { searchParams } = new URL(request.url);

    // Parse + validate query params
    const rawLimit = searchParams.get("limit");
    const rawOffset = searchParams.get("offset");
    const decisionFilter = searchParams.get("decision")?.toUpperCase();
    const sinceFilter = searchParams.get("since");
    const sourceFilter = searchParams.get("source");

    let limit = rawLimit ? parseInt(rawLimit, 10) : 20;
    let offset = rawOffset ? parseInt(rawOffset, 10) : 0;

    if (isNaN(limit) || limit < 1) limit = 20;
    if (limit > 100) limit = 100;
    if (isNaN(offset) || offset < 0) offset = 0;

    if (decisionFilter && !VALID_DECISIONS.has(decisionFilter)) {
      return badRequest(
        `Invalid decision filter. Must be one of: BURN, MINT, NEUTRAL`
      );
    }

    // Validate ISO8601 date if provided
    if (sinceFilter) {
      const parsed = new Date(sinceFilter);
      if (isNaN(parsed.getTime())) {
        return badRequest(`Invalid 'since' parameter. Must be ISO8601 datetime.`);
      }
    }

    const { events, total } = queryEvents({
      limit,
      offset,
      decision: decisionFilter,
      since: sinceFilter ?? undefined,
      source: sourceFilter ?? undefined,
    });

    return ok(
      {
        events,
        pagination: {
          limit,
          offset,
          total,
          has_more: offset + events.length < total,
        },
      },
      rl
    );
  } catch (err) {
    console.error("[GET /api/v1/events]", err);
    return serverError();
  }
}
