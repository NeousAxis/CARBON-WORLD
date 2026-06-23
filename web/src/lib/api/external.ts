/**
 * external.ts — Cached, timeout-guarded proxies for free world-data sources.
 *
 * Aggregates open external datasets alongside the CBWD corpus:
 *   - GDELT 2.0 Doc API  — global news stream (geopolitical), no key
 *   - World Bank API     — economic / development indicators, no key
 *
 * Every outbound call has a hard timeout and a graceful fallback (never throws
 * to the route — returns { ok:false, error } instead). Results are memoised in
 * a small in-memory TTL cache to protect the upstreams and stay within their
 * fair-use limits.
 */

const DEFAULT_TIMEOUT_MS = 7000;
// GDELT's Doc API is frequently slow (8-15s) — give it a longer leash than the
// fast World Bank API, which stays on DEFAULT_TIMEOUT_MS.
const GDELT_TIMEOUT_MS = 18000;
const DEFAULT_TTL_MS = 15 * 60 * 1000; // 15 minutes

interface CacheEntry {
  expires: number;
  data: unknown;
}
const cache = new Map<string, CacheEntry>();

function cacheGet(key: string): unknown | null {
  const e = cache.get(key);
  if (!e) return null;
  if (Date.now() > e.expires) {
    cache.delete(key);
    return null;
  }
  return e.data;
}

function cacheSet(key: string, data: unknown, ttl = DEFAULT_TTL_MS): void {
  cache.set(key, { expires: Date.now() + ttl, data });
  // Bound memory: drop oldest if the cache grows unreasonably.
  if (cache.size > 500) {
    const oldest = cache.keys().next().value;
    if (oldest !== undefined) cache.delete(oldest);
  }
}

async function fetchJson(
  url: string,
  timeoutMs = DEFAULT_TIMEOUT_MS
): Promise<{ ok: true; data: unknown } | { ok: false; error: string }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: { "User-Agent": "CarbonWorld/1.0 (+https://carbon-world.xyz)" },
    });
    if (!res.ok) return { ok: false, error: `upstream returned ${res.status}` };
    const text = await res.text();
    try {
      return { ok: true, data: JSON.parse(text) };
    } catch {
      return { ok: false, error: "upstream returned non-JSON payload" };
    }
  } catch (err) {
    const msg = err instanceof Error && err.name === "AbortError" ? "upstream timeout" : "upstream unreachable";
    return { ok: false, error: msg };
  } finally {
    clearTimeout(timer);
  }
}

export type ExternalResult =
  | { ok: true; source: string; fetched_at: string; cached: boolean; data: unknown }
  | { ok: false; source: string; error: string };

// ---------------------------------------------------------------------------
// GDELT 2.0 Doc API
// ---------------------------------------------------------------------------

interface GdeltArticle {
  url?: string;
  title?: string;
  seendate?: string;
  domain?: string;
  language?: string;
  sourcecountry?: string;
}

export async function fetchGdelt(
  query: string,
  opts: { max?: number; timespan?: string } = {}
): Promise<ExternalResult> {
  const max = Math.min(Math.max(opts.max ?? 25, 1), 75);
  const timespan = /^\d+[dhm]$/.test(opts.timespan ?? "") ? opts.timespan! : "3d";
  const url =
    "https://api.gdeltproject.org/api/v2/doc/doc?" +
    new URLSearchParams({
      query,
      mode: "artlist",
      format: "json",
      maxrecords: String(max),
      timespan,
      sort: "datedesc",
    }).toString();

  const cacheKey = `gdelt:${query}:${max}:${timespan}`;
  const hit = cacheGet(cacheKey);
  if (hit !== null) {
    return { ok: true, source: "gdelt", fetched_at: new Date().toISOString(), cached: true, data: hit };
  }

  const res = await fetchJson(url, GDELT_TIMEOUT_MS);
  if (!res.ok) return { ok: false, source: "gdelt", error: res.error };

  const raw = res.data as { articles?: GdeltArticle[] };
  const articles = (raw.articles ?? []).map((a) => ({
    title: a.title ?? "",
    url: a.url ?? "",
    domain: a.domain ?? "",
    seen_date: a.seendate ?? "",
    language: a.language ?? "",
    source_country: a.sourcecountry ?? "",
  }));
  const data = { query, timespan, count: articles.length, articles };
  cacheSet(cacheKey, data);
  return { ok: true, source: "gdelt", fetched_at: new Date().toISOString(), cached: false, data };
}

// ---------------------------------------------------------------------------
// World Bank Indicators API
// ---------------------------------------------------------------------------

// Curated allow-list of common indicators so clients get friendly names and we
// keep the surface predictable. Clients may still pass any raw indicator code.
export const WORLD_BANK_INDICATORS: Record<string, string> = {
  gdp: "NY.GDP.MKTP.CD", // GDP (current US$)
  gdp_per_capita: "NY.GDP.PCAP.CD", // GDP per capita (current US$)
  gdp_growth: "NY.GDP.MKTP.KD.ZG", // GDP growth (annual %)
  population: "SP.POP.TOTL", // Population, total
  co2_per_capita: "EN.GHG.CO2.PC.CE.AR5", // CO2 emissions per capita (t)
  renewable_energy: "EG.FEC.RNEW.ZS", // Renewable energy consumption (% of total)
  unemployment: "SL.UEM.TOTL.ZS", // Unemployment (% of labor force)
  forest_area: "AG.LND.FRST.ZS", // Forest area (% of land)
};

interface WorldBankPoint {
  date?: string;
  value?: number | null;
  indicator?: { id?: string; value?: string };
  country?: { id?: string; value?: string };
}

export async function fetchWorldBank(
  country: string,
  indicator: string,
  opts: { from?: number; to?: number } = {}
): Promise<ExternalResult> {
  const indicatorCode = WORLD_BANK_INDICATORS[indicator] ?? indicator;
  const to = opts.to ?? new Date().getFullYear();
  const from = opts.from ?? to - 15;
  const safeCountry = encodeURIComponent(country.toLowerCase());
  const url =
    `https://api.worldbank.org/v2/country/${safeCountry}/indicator/${encodeURIComponent(indicatorCode)}?` +
    new URLSearchParams({ format: "json", per_page: "100", date: `${from}:${to}` }).toString();

  const cacheKey = `wb:${safeCountry}:${indicatorCode}:${from}:${to}`;
  const hit = cacheGet(cacheKey);
  if (hit !== null) {
    return { ok: true, source: "worldbank", fetched_at: new Date().toISOString(), cached: true, data: hit };
  }

  const res = await fetchJson(url);
  if (!res.ok) return { ok: false, source: "worldbank", error: res.error };

  // World Bank returns [meta, series] — or [{message:[...]}] on error.
  if (!Array.isArray(res.data) || res.data.length < 2 || !Array.isArray(res.data[1])) {
    return { ok: false, source: "worldbank", error: "no data for this country/indicator" };
  }
  const series = (res.data[1] as WorldBankPoint[])
    .filter((p) => p.value !== null && p.value !== undefined)
    .map((p) => ({ year: Number(p.date), value: p.value as number }))
    .sort((a, b) => a.year - b.year);

  const meta = (res.data[1] as WorldBankPoint[])[0];
  const data = {
    country: meta?.country?.value ?? country,
    country_code: meta?.country?.id ?? country,
    indicator: indicator,
    indicator_code: indicatorCode,
    indicator_name: meta?.indicator?.value ?? indicatorCode,
    points: series,
    latest: series.length ? series[series.length - 1] : null,
  };
  cacheSet(cacheKey, data);
  return { ok: true, source: "worldbank", fetched_at: new Date().toISOString(), cached: false, data };
}
