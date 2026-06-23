/**
 * GET /api/v1/external/worldbank — Economic / development indicators (World Bank API).
 *
 * Query params:
 *   country   (required) — ISO2/ISO3 or code, e.g. "US", "BRA", "fr"
 *   indicator (default "gdp") — a friendly key (gdp, gdp_per_capita, gdp_growth,
 *             population, co2_per_capita, renewable_energy, unemployment,
 *             forest_area) OR a raw World Bank code like "NY.GDP.MKTP.CD"
 *   from, to  (years, optional; default last 15 years)
 *
 * Cached 15 min; hard 7s upstream timeout with graceful 502 fallback.
 */

export const dynamic = "force-dynamic";

import { fetchWorldBank, WORLD_BANK_INDICATORS } from "@/lib/api/external";
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
  const country = searchParams.get("country")?.trim();
  if (!country || !/^[A-Za-z]{2,3}$/.test(country)) {
    return badRequest("Missing or invalid 'country' (ISO2/ISO3 alpha code, e.g. US, BRA).");
  }
  const indicator = (searchParams.get("indicator") ?? "gdp").trim();

  const rawFrom = searchParams.get("from");
  const rawTo = searchParams.get("to");
  const from = rawFrom ? parseInt(rawFrom, 10) : undefined;
  const to = rawTo ? parseInt(rawTo, 10) : undefined;
  for (const [name, val] of [["from", from], ["to", to]] as const) {
    if (val !== undefined && (Number.isNaN(val) || val < 1960 || val > 2100)) {
      return badRequest(`Invalid '${name}' year.`);
    }
  }

  const result = await fetchWorldBank(country, indicator, { from, to });
  if (!result.ok) return upstreamError(result.source, result.error);
  return ok({ ...result, available_indicators: Object.keys(WORLD_BANK_INDICATORS) }, rl);
}
