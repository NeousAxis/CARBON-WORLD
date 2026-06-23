/**
 * intel.ts — Geo-economic intelligence aggregations over scored events.
 *
 * Read-only SQLite queries that turn the raw carbon_events corpus into the
 * geopolitical / economic views consumed by the /api/v1/{regions,countries,
 * timeseries,frameworks,index} endpoints.
 *
 * Index design note: the primary `ethical_index` is COUNT-based
 *   index = (burn_count - mint_count) / total_events   ∈ [-1, +1]
 * deliberately NOT amount-based. amount_crbn is LLM-chosen with no scope
 * guardrail and is inflation-prone (see memory: scale-inflation-artifact),
 * so net_cbwd is exposed for transparency but never drives the index.
 * `mean_score` (avg final_score) is a secondary, signed signal.
 */

import { getDb } from "./db";

// ---------------------------------------------------------------------------
// Shared shapes
// ---------------------------------------------------------------------------

/** The 7 UN reference frameworks, in canonical order. */
export const FRAMEWORK_KEYS = [
  "SDG",
  "UDHR",
  "ILO",
  "Animal",
  "CRC",
  "UNDRIP",
  "PB",
] as const;

export type FrameworkKey = (typeof FRAMEWORK_KEYS)[number];

interface RawAggRow {
  bucket: string | null;
  events: number;
  burn: number;
  mint: number;
  neutral: number;
  mean_score: number | null;
  burned: number;
  minted: number;
  last_event_at: string | null;
}

const AGG_COLUMNS = `
  COUNT(*) AS events,
  SUM(CASE WHEN decision = 'BURN' THEN 1 ELSE 0 END) AS burn,
  SUM(CASE WHEN decision = 'MINT' THEN 1 ELSE 0 END) AS mint,
  SUM(CASE WHEN decision = 'NEUTRAL' THEN 1 ELSE 0 END) AS neutral,
  AVG(final_score) AS mean_score,
  SUM(CASE WHEN decision = 'BURN' THEN amount_crbn ELSE 0 END) AS burned,
  SUM(CASE WHEN decision = 'MINT' THEN amount_crbn ELSE 0 END) AS minted,
  MAX(created_at) AS last_event_at
`;

function round(n: number, digits = 3): number {
  const f = 10 ** digits;
  return Math.round(n * f) / f;
}

/** Shared derived metrics from a raw aggregate row. */
function deriveMetrics(r: RawAggRow) {
  const events = r.events || 0;
  return {
    events,
    by_decision: { BURN: r.burn || 0, MINT: r.mint || 0, NEUTRAL: r.neutral || 0 },
    // Primary, robust, count-based index in [-1, +1]
    ethical_index: events ? round((r.burn - r.mint) / events) : 0,
    burn_ratio: events ? round(r.burn / events) : 0,
    mint_ratio: events ? round(r.mint / events) : 0,
    mean_score: r.mean_score !== null ? round(r.mean_score, 2) : null,
    supply_cbwd: {
      minted: r.minted || 0,
      burned: r.burned || 0,
      // Inflation-prone — exposed for transparency, not used for the index
      net: (r.burned || 0) - (r.minted || 0),
    },
    last_event_at: r.last_event_at,
  };
}

export type GeoMetrics = ReturnType<typeof deriveMetrics>;

// ---------------------------------------------------------------------------
// WHERE builder shared by aggregate endpoints
// ---------------------------------------------------------------------------

interface GeoFilter {
  since?: string;
  until?: string;
  region?: string;
  country?: string;
  decision?: string;
}

function buildWhere(f: GeoFilter, extra: string[] = []): { sql: string; bindings: unknown[] } {
  const conditions = [...extra];
  const bindings: unknown[] = [];
  if (f.since) {
    conditions.push("created_at >= ?");
    bindings.push(f.since);
  }
  if (f.until) {
    conditions.push("created_at <= ?");
    bindings.push(f.until);
  }
  if (f.region) {
    conditions.push("region = ?");
    bindings.push(f.region);
  }
  if (f.country) {
    conditions.push("country = ?");
    bindings.push(f.country);
  }
  if (f.decision) {
    conditions.push("decision = ?");
    bindings.push(f.decision.toUpperCase());
  }
  return {
    sql: conditions.length ? `WHERE ${conditions.join(" AND ")}` : "",
    bindings,
  };
}

// ---------------------------------------------------------------------------
// Regions
// ---------------------------------------------------------------------------

export function queryRegions(filter: GeoFilter = {}): {
  regions: (GeoMetrics & { region: string; top_countries: { country: string; events: number }[] })[];
  total_classified: number;
} {
  const db = getDb();
  const { sql, bindings } = buildWhere(filter, ["region IS NOT NULL"]);

  const rows = db
    .prepare(
      `SELECT region AS bucket, ${AGG_COLUMNS}
       FROM carbon_events ${sql}
       GROUP BY region
       ORDER BY events DESC`
    )
    .all(...bindings) as RawAggRow[];

  // Top countries per region (one extra grouped query, joined in JS)
  const countryRows = db
    .prepare(
      `SELECT region, country, COUNT(*) AS events
       FROM carbon_events ${sql} ${sql ? "AND" : "WHERE"} country IS NOT NULL
       GROUP BY region, country`
    )
    .all(...bindings) as { region: string; country: string; events: number }[];

  const topByRegion = new Map<string, { country: string; events: number }[]>();
  for (const c of countryRows) {
    const list = topByRegion.get(c.region) ?? [];
    list.push({ country: c.country, events: c.events });
    topByRegion.set(c.region, list);
  }

  const regions = rows.map((r) => ({
    region: r.bucket as string,
    ...deriveMetrics(r),
    top_countries: (topByRegion.get(r.bucket as string) ?? [])
      .sort((a, b) => b.events - a.events)
      .slice(0, 5),
  }));

  const total_classified = regions.reduce((s, r) => s + r.events, 0);
  return { regions, total_classified };
}

// ---------------------------------------------------------------------------
// Countries
// ---------------------------------------------------------------------------

export function queryCountries(
  filter: GeoFilter = {},
  opts: { sort?: "events" | "index_desc" | "index_asc"; limit?: number } = {}
): {
  countries: (GeoMetrics & { country: string; region: string | null })[];
  total_classified: number;
} {
  const db = getDb();
  const { sql, bindings } = buildWhere(filter, ["country IS NOT NULL"]);

  const rows = db
    .prepare(
      `SELECT country AS bucket, MAX(region) AS region, ${AGG_COLUMNS}
       FROM carbon_events ${sql}
       GROUP BY country`
    )
    .all(...bindings) as (RawAggRow & { region: string | null })[];

  let countries = rows.map((r) => ({
    country: r.bucket as string,
    region: r.region,
    ...deriveMetrics(r),
  }));

  const sort = opts.sort ?? "events";
  countries.sort((a, b) => {
    if (sort === "index_desc") return b.ethical_index - a.ethical_index || b.events - a.events;
    if (sort === "index_asc") return a.ethical_index - b.ethical_index || b.events - a.events;
    return b.events - a.events;
  });

  const total_classified = countries.reduce((s, c) => s + c.events, 0);
  if (opts.limit) countries = countries.slice(0, opts.limit);
  return { countries, total_classified };
}

// ---------------------------------------------------------------------------
// Time series
// ---------------------------------------------------------------------------

const INTERVAL_EXPR: Record<"day" | "week" | "month", string> = {
  day: "substr(created_at, 1, 10)",
  week: "strftime('%Y-W%W', created_at)",
  month: "substr(created_at, 1, 7)",
};

export function queryTimeseries(
  filter: GeoFilter = {},
  interval: "day" | "week" | "month" = "day"
): { interval: string; buckets: (GeoMetrics & { period: string })[] } {
  const db = getDb();
  const { sql, bindings } = buildWhere(filter);
  const expr = INTERVAL_EXPR[interval];

  const rows = db
    .prepare(
      `SELECT ${expr} AS bucket, ${AGG_COLUMNS}
       FROM carbon_events ${sql}
       GROUP BY ${expr}
       ORDER BY bucket ASC`
    )
    .all(...bindings) as RawAggRow[];

  return {
    interval,
    buckets: rows.map((r) => ({ period: r.bucket as string, ...deriveMetrics(r) })),
  };
}

// ---------------------------------------------------------------------------
// Frameworks (parsed from aspect JSON)
// ---------------------------------------------------------------------------

interface Aspect {
  affected_sdgs?: number[];
  magnitude?: number;
  frameworks?: string[];
  violated_rights?: string[];
}

export function queryFrameworks(filter: GeoFilter = {}): {
  frameworks: {
    framework: FrameworkKey;
    positive_count: number;
    negative_count: number;
    positive_magnitude: number;
    negative_magnitude: number;
    net_magnitude: number;
  }[];
  sdg_histogram: { sdg: number; positive: number; negative: number }[];
  events_analyzed: number;
} {
  const db = getDb();
  const { sql, bindings } = buildWhere(filter);

  const rows = db
    .prepare(
      `SELECT positive_aspects_json, negative_aspects_json
       FROM carbon_events ${sql}`
    )
    .all(...bindings) as {
    positive_aspects_json: string | null;
    negative_aspects_json: string | null;
  }[];

  const fw = new Map<
    string,
    { posC: number; negC: number; posM: number; negM: number }
  >();
  for (const k of FRAMEWORK_KEYS) fw.set(k, { posC: 0, negC: 0, posM: 0, negM: 0 });
  const sdg = new Map<number, { positive: number; negative: number }>();

  function ingest(json: string | null, polarity: "pos" | "neg") {
    if (!json) return;
    let aspects: Aspect[];
    try {
      aspects = JSON.parse(json);
    } catch {
      return;
    }
    if (!Array.isArray(aspects)) return;
    for (const a of aspects) {
      const mag = typeof a.magnitude === "number" ? a.magnitude : 0;
      for (const raw of a.frameworks ?? []) {
        const key = raw === "SDH" ? "SDG" : raw; // tolerate one historical typo
        const slot = fw.get(key);
        if (!slot) continue;
        if (polarity === "pos") {
          slot.posC += 1;
          slot.posM += mag;
        } else {
          slot.negC += 1;
          slot.negM += mag;
        }
      }
      for (const s of a.affected_sdgs ?? []) {
        if (s < 1 || s > 17) continue;
        const slot = sdg.get(s) ?? { positive: 0, negative: 0 };
        if (polarity === "pos") slot.positive += 1;
        else slot.negative += 1;
        sdg.set(s, slot);
      }
    }
  }

  for (const r of rows) {
    ingest(r.positive_aspects_json, "pos");
    ingest(r.negative_aspects_json, "neg");
  }

  const frameworks = FRAMEWORK_KEYS.map((k) => {
    const s = fw.get(k)!;
    return {
      framework: k,
      positive_count: s.posC,
      negative_count: s.negC,
      positive_magnitude: s.posM,
      negative_magnitude: s.negM,
      net_magnitude: s.posM - s.negM,
    };
  });

  const sdg_histogram = Array.from({ length: 17 }, (_, i) => {
    const s = sdg.get(i + 1) ?? { positive: 0, negative: 0 };
    return { sdg: i + 1, positive: s.positive, negative: s.negative };
  });

  return { frameworks, sdg_histogram, events_analyzed: rows.length };
}

// ---------------------------------------------------------------------------
// Global aggregate + world index
// ---------------------------------------------------------------------------

function globalAgg(filter: GeoFilter = {}): GeoMetrics {
  const db = getDb();
  const { sql, bindings } = buildWhere(filter);
  const row = db
    .prepare(`SELECT NULL AS bucket, ${AGG_COLUMNS} FROM carbon_events ${sql}`)
    .get(...bindings) as RawAggRow;
  return deriveMetrics(row);
}

/** A region's index over a window, used to compute 7d movers. */
function regionIndexMap(since: string, until?: string): Map<string, GeoMetrics> {
  const { regions } = queryRegions({ since, until });
  const m = new Map<string, GeoMetrics>();
  for (const r of regions) m.set(r.region, r);
  return m;
}

export function queryWorldIndex(nowIso: string): {
  generated_at: string;
  global: GeoMetrics;
  by_region: (GeoMetrics & { region: string })[];
  top_movers: {
    region: string;
    index_now: number;
    index_prev: number;
    delta: number;
    events_recent: number;
  }[];
  window_days: number;
} {
  const now = new Date(nowIso).getTime();
  const day = 86_400_000;
  const sevenAgo = new Date(now - 7 * day).toISOString();
  const fourteenAgo = new Date(now - 14 * day).toISOString();

  const global = globalAgg();
  const { regions } = queryRegions();
  // strip top_countries for the index view (kept lean)
  const by_region = regions
    .map(({ top_countries: _omit, ...rest }) => rest)
    .sort((a, b) => b.ethical_index - a.ethical_index);

  const recent = regionIndexMap(sevenAgo);
  const prior = regionIndexMap(fourteenAgo, sevenAgo);

  const top_movers = Array.from(recent.entries())
    .map(([region, cur]) => {
      const prev = prior.get(region);
      const index_prev = prev ? prev.ethical_index : 0;
      return {
        region,
        index_now: cur.ethical_index,
        index_prev,
        delta: round(cur.ethical_index - index_prev),
        events_recent: cur.events,
      };
    })
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

  return {
    generated_at: nowIso,
    global,
    by_region,
    top_movers,
    window_days: 7,
  };
}

/** Distinct region / country lists for discovery (used by validation + clients). */
export function queryGeoVocabulary(): { regions: string[]; countries: string[] } {
  const db = getDb();
  const regions = (
    db
      .prepare("SELECT DISTINCT region FROM carbon_events WHERE region IS NOT NULL ORDER BY region")
      .all() as { region: string }[]
  ).map((r) => r.region);
  const countries = (
    db
      .prepare("SELECT DISTINCT country FROM carbon_events WHERE country IS NOT NULL ORDER BY country")
      .all() as { country: string }[]
  ).map((r) => r.country);
  return { regions, countries };
}
