/**
 * GET /api/v1/external/gdelt — Global news stream via the GDELT 2.0 Doc API.
 *
 * Query params:
 *   query    (required) — GDELT query expression, e.g. "climate policy"
 *   max      (1-75, default 25)
 *   timespan (e.g. "1d", "3d", "12h"; default "3d")
 *
 * Cached 15 min; hard 7s upstream timeout with graceful 502 fallback.
 */

export const dynamic = "force-dynamic";

import { fetchGdelt } from "@/lib/api/external";
import { checkRateLimit, getClientIp } from "@/lib/api/rate-limit";
import { ok, rateLimitExceeded, badRequest, optionsResponse } from "@/lib/api/response";

function upstreamError(source: string, error: string): Response {
  return new Response(JSON.stringify({ error: "upstream_error", source, detail: error }), {
    status: 502,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Content-Type": "application/json",
    },
  });
}

export async function OPTIONS() {
  return optionsResponse();
}

export async function GET(request: Request) {
  const ip = getClientIp(request);
  const rl = checkRateLimit(ip);
  if (!rl.allowed) return rateLimitExceeded(rl);

  const { searchParams } = new URL(request.url);
  const query = searchParams.get("query")?.trim();
  if (!query || query.length < 2) {
    return badRequest("Missing required 'query' parameter (min 2 chars).");
  }

  const rawMax = searchParams.get("max");
  const max = rawMax ? parseInt(rawMax, 10) : undefined;
  if (rawMax && (max === undefined || Number.isNaN(max))) {
    return badRequest("Invalid 'max' parameter. Must be an integer.");
  }
  const timespan = searchParams.get("timespan") ?? undefined;

  const result = await fetchGdelt(query, { max, timespan });
  if (!result.ok) return upstreamError(result.source, result.error);
  return ok(result, rl);
}
