/**
 * GET /api/v1/firehose — Raw collected article stream (Phase 11).
 *
 * Every article the collector fetches is persisted (independently of whether it
 * survives classification), giving access to the full geopolitical / economic
 * stream — not just the ~scored events. Each item carries `became_event` so
 * clients can see what the pipeline acted on.
 *
 * Query params (all optional):
 *   limit (1-100, default 50), offset
 *   source — partial match on source name
 *   q      — partial match on title
 *   since, until (ISO8601, on fetched_at)
 *   became_event — "true" | "false" filter
 *
 * Note: this table is forward-only — it fills as the pipeline runs. Returns
 * `available:false` with an empty list until the worker has persisted a batch.
 */

export const dynamic = "force-dynamic";

import { queryFirehose } from "@/lib/api/db";
import { checkRateLimit, getClientIp } from "@/lib/api/rate-limit";
import { ok, rateLimitExceeded, badRequest, serverError, optionsResponse } from "@/lib/api/response";

export async function OPTIONS() {
  return optionsResponse();
}

export async function GET(request: Request) {
  const ip = getClientIp(request);
  const rl = checkRateLimit(ip);
  if (!rl.allowed) return rateLimitExceeded(rl);

  try {
    const { searchParams } = new URL(request.url);

    const rawLimit = searchParams.get("limit");
    const rawOffset = searchParams.get("offset");
    const source = searchParams.get("source");
    const q = searchParams.get("q");
    const since = searchParams.get("since");
    const until = searchParams.get("until");
    const rawBecame = searchParams.get("became_event");

    let limit = rawLimit ? parseInt(rawLimit, 10) : 50;
    let offset = rawOffset ? parseInt(rawOffset, 10) : 0;
    if (isNaN(limit) || limit < 1) limit = 50;
    if (limit > 100) limit = 100;
    if (isNaN(offset) || offset < 0) offset = 0;

    for (const [name, val] of [["since", since], ["until", until]] as const) {
      if (val && isNaN(new Date(val).getTime())) {
        return badRequest(`Invalid '${name}' parameter. Must be ISO8601 datetime.`);
      }
    }

    let becameEvent: boolean | undefined;
    if (rawBecame !== null) {
      if (rawBecame === "true") becameEvent = true;
      else if (rawBecame === "false") becameEvent = false;
      else return badRequest("Invalid 'became_event'. Must be 'true' or 'false'.");
    }

    const data = queryFirehose({
      limit,
      offset,
      source: source ?? undefined,
      q: q ?? undefined,
      since: since ?? undefined,
      until: until ?? undefined,
      becameEvent,
    });
    return ok(data, rl);
  } catch (err) {
    console.error("[GET /api/v1/firehose]", err);
    return serverError();
  }
}
