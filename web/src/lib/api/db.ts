/**
 * db.ts — Read-only SQLite connection for Next.js API routes.
 *
 * Uses better-sqlite3 (synchronous, zero-config).
 * DB path is resolved via CARBON_DB_PATH env var, falling back to
 * the local data/carbon.db relative to the project root.
 */

import Database from "better-sqlite3";
import path from "path";

// ---------------------------------------------------------------------------
// Connection (module-level singleton, opened lazily)
// ---------------------------------------------------------------------------

let _db: Database.Database | null = null;
/** true when the DB schema has the semantic-dedup columns (migration 2026-04-20) */
let _hasExtendedColumns: boolean | null = null;

export function getDb(): Database.Database {
  if (_db) return _db;

  const dbPath =
    process.env.CARBON_DB_PATH ||
    path.join(process.cwd(), "..", "data", "carbon.db");

  _db = new Database(dbPath, { readonly: true, fileMustExist: true });
  // Improve read performance
  _db.pragma("journal_mode = WAL");
  return _db;
}

/**
 * Detect whether the DB schema has the extended columns added in the
 * 2026-04-20 semantic-dedup migration (embedding + reused_from_event_id).
 * Result is cached at module level to avoid repeated PRAGMA calls.
 */
function hasExtendedColumns(): boolean {
  if (_hasExtendedColumns !== null) return _hasExtendedColumns;
  const db = getDb();
  const cols = db
    .prepare("PRAGMA table_info(carbon_events)")
    .all() as Array<{ name: string }>;
  _hasExtendedColumns = cols.some((c) => c.name === "reused_from_event_id");
  return _hasExtendedColumns;
}

// ---------------------------------------------------------------------------
// Row types (minimal — only what the API exposes)
// ---------------------------------------------------------------------------

export interface EventRow {
  id: number;
  event_title: string;
  event_url: string;
  event_source: string;
  decision: string;
  amount_crbn: number;
  final_score: number;
  confidence: number;
  justification: string;
  tx_hash: string | null;
  created_at: string;
  // Optional columns added by migration (may be absent in older DBs)
  embedding?: Buffer | null;
  reused_from_event_id?: number | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const EXPLORER_BASE = "https://explorer.solana.com/tx";

function explorerLink(txHash: string | null): string | null {
  return txHash ? `${EXPLORER_BASE}/${txHash}` : null;
}

/** Convert a raw DB row into the public-facing event shape (list view — no justification). */
export function toPublicEvent(row: EventRow) {
  return {
    id: row.id,
    title: row.event_title,
    url: row.event_url,
    source: row.event_source,
    decision: row.decision,
    amount_cbwd: row.amount_crbn,
    final_score: row.final_score,
    confidence: row.confidence,
    created_at: row.created_at,
    solana_tx: row.tx_hash ?? null,
    link_explorer: explorerLink(row.tx_hash),
    reused_from_event_id: (row as EventRow).reused_from_event_id ?? null,
  };
}

/** Same as toPublicEvent but includes justification (detail view). */
export function toPublicEventDetail(row: EventRow) {
  return {
    ...toPublicEvent(row),
    justification: row.justification,
  };
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

interface ListParams {
  limit: number;
  offset: number;
  decision?: string;
  since?: string;
  until?: string;
  source?: string;
  country?: string;
  region?: string;
  minScore?: number;
  maxScore?: number;
  minConfidence?: number;
  sort?: "recent" | "oldest" | "score_desc" | "score_asc";
}

const SORT_CLAUSES: Record<NonNullable<ListParams["sort"]>, string> = {
  recent: "id DESC",
  oldest: "id ASC",
  score_desc: "final_score DESC, id DESC",
  score_asc: "final_score ASC, id DESC",
};

export function queryEvents(params: ListParams): {
  events: ReturnType<typeof toPublicEvent>[];
  total: number;
} {
  const db = getDb();

  const conditions: string[] = [];
  const bindings: unknown[] = [];

  if (params.decision) {
    conditions.push("decision = ?");
    bindings.push(params.decision.toUpperCase());
  }
  if (params.since) {
    conditions.push("created_at >= ?");
    bindings.push(params.since);
  }
  if (params.until) {
    conditions.push("created_at <= ?");
    bindings.push(params.until);
  }
  if (params.source) {
    conditions.push("event_source LIKE ?");
    bindings.push(`%${params.source}%`);
  }
  if (params.country) {
    conditions.push("country = ?");
    bindings.push(params.country);
  }
  if (params.region) {
    conditions.push("region = ?");
    bindings.push(params.region);
  }
  if (params.minScore !== undefined) {
    conditions.push("final_score >= ?");
    bindings.push(params.minScore);
  }
  if (params.maxScore !== undefined) {
    conditions.push("final_score <= ?");
    bindings.push(params.maxScore);
  }
  if (params.minConfidence !== undefined) {
    conditions.push("confidence >= ?");
    bindings.push(params.minConfidence);
  }

  const where = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";
  const orderBy = SORT_CLAUSES[params.sort ?? "recent"];

  const countRow = db
    .prepare(`SELECT COUNT(*) as c FROM carbon_events ${where}`)
    .get(...bindings) as { c: number };

  const extendedSelect = hasExtendedColumns() ? ", reused_from_event_id" : "";
  const rows = db
    .prepare(
      `SELECT id, event_title, event_url, event_source, decision,
              amount_crbn, final_score, confidence, tx_hash, created_at
              ${extendedSelect}
       FROM carbon_events ${where}
       ORDER BY ${orderBy}
       LIMIT ? OFFSET ?`
    )
    .all(...bindings, params.limit, params.offset) as EventRow[];

  return {
    events: rows.map(toPublicEvent),
    total: countRow.c,
  };
}

export function queryEventById(id: number): ReturnType<typeof toPublicEventDetail> | null {
  const db = getDb();
  const extendedSelect = hasExtendedColumns() ? ", reused_from_event_id" : "";
  const row = db
    .prepare(
      `SELECT id, event_title, event_url, event_source, decision,
              amount_crbn, final_score, confidence, justification,
              tx_hash, created_at
              ${extendedSelect}
       FROM carbon_events WHERE id = ?`
    )
    .get(id) as EventRow | undefined;

  return row ? toPublicEventDetail(row) : null;
}

export function queryStats() {
  const db = getDb();

  const counts = db
    .prepare(
      `SELECT
         COUNT(*) AS total_events,
         SUM(CASE WHEN decision = 'BURN' THEN 1 ELSE 0 END) AS burn_count,
         SUM(CASE WHEN decision = 'MINT' THEN 1 ELSE 0 END) AS mint_count,
         SUM(CASE WHEN decision = 'NEUTRAL' THEN 1 ELSE 0 END) AS neutral_count,
         SUM(CASE WHEN decision = 'MINT' THEN amount_crbn ELSE 0 END) AS total_minted,
         SUM(CASE WHEN decision = 'BURN' THEN amount_crbn ELSE 0 END) AS total_burned,
         MAX(created_at) AS last_event_at
       FROM carbon_events`
    )
    .get() as {
    total_events: number;
    burn_count: number;
    mint_count: number;
    neutral_count: number;
    total_minted: number;
    total_burned: number;
    last_event_at: string | null;
  };

  // Optional columns — may not exist in older DB versions
  let events_with_embedding = 0;
  let reused_events = 0;
  try {
    const embeddingRow = db
      .prepare(
        `SELECT
           COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) AS with_emb,
           COUNT(CASE WHEN reused_from_event_id IS NOT NULL THEN 1 END) AS reused
         FROM carbon_events`
      )
      .get() as { with_emb: number; reused: number };
    events_with_embedding = embeddingRow.with_emb;
    reused_events = embeddingRow.reused;
  } catch {
    // Columns not yet migrated on this DB — safe to skip
  }

  return {
    total_events: counts.total_events,
    by_decision: {
      BURN: counts.burn_count,
      MINT: counts.mint_count,
      NEUTRAL: counts.neutral_count,
    },
    total_supply: {
      minted: counts.total_minted,
      burned: counts.total_burned,
      net: counts.total_minted - counts.total_burned,
    },
    last_event_at: counts.last_event_at,
    cache_stats: {
      events_with_embedding,
      reused_events,
    },
  };
}

// ---------------------------------------------------------------------------
// Firehose — raw collected article stream (Phase 11)
// ---------------------------------------------------------------------------

let _hasRawArticles: boolean | null = null;

/** Whether the raw_articles table exists (created by the worker migration). */
function hasRawArticlesTable(): boolean {
  if (_hasRawArticles !== null) return _hasRawArticles;
  const db = getDb();
  const row = db
    .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='raw_articles'")
    .get() as { name: string } | undefined;
  _hasRawArticles = !!row;
  return _hasRawArticles;
}

interface FirehoseParams {
  limit: number;
  offset: number;
  source?: string;
  q?: string;
  since?: string;
  until?: string;
  becameEvent?: boolean;
}

export function queryFirehose(params: FirehoseParams): {
  articles: {
    url: string;
    title: string;
    source: string;
    published: string | null;
    fetched_at: string;
    became_event: boolean;
  }[];
  pagination: { limit: number; offset: number; total: number; has_more: boolean };
  available: boolean;
} {
  if (!hasRawArticlesTable()) {
    return {
      articles: [],
      pagination: { limit: params.limit, offset: params.offset, total: 0, has_more: false },
      available: false,
    };
  }

  const db = getDb();
  const conditions: string[] = [];
  const bindings: unknown[] = [];

  if (params.source) {
    conditions.push("r.source LIKE ?");
    bindings.push(`%${params.source}%`);
  }
  if (params.q) {
    conditions.push("r.title LIKE ?");
    bindings.push(`%${params.q}%`);
  }
  if (params.since) {
    conditions.push("r.fetched_at >= ?");
    bindings.push(params.since);
  }
  if (params.until) {
    conditions.push("r.fetched_at <= ?");
    bindings.push(params.until);
  }
  if (params.becameEvent !== undefined) {
    conditions.push(
      params.becameEvent
        ? "EXISTS (SELECT 1 FROM carbon_events e WHERE e.event_url = r.url)"
        : "NOT EXISTS (SELECT 1 FROM carbon_events e WHERE e.event_url = r.url)"
    );
  }

  const where = conditions.length ? `WHERE ${conditions.join(" AND ")}` : "";

  const countRow = db
    .prepare(`SELECT COUNT(*) AS c FROM raw_articles r ${where}`)
    .get(...bindings) as { c: number };

  const rows = db
    .prepare(
      `SELECT r.url, r.title, r.source, r.published, r.fetched_at,
              EXISTS (SELECT 1 FROM carbon_events e WHERE e.event_url = r.url) AS became_event
       FROM raw_articles r ${where}
       ORDER BY r.fetched_at DESC, r.id DESC
       LIMIT ? OFFSET ?`
    )
    .all(...bindings, params.limit, params.offset) as {
    url: string;
    title: string;
    source: string;
    published: string | null;
    fetched_at: string;
    became_event: number;
  }[];

  return {
    articles: rows.map((r) => ({
      url: r.url,
      title: r.title,
      source: r.source,
      published: r.published,
      fetched_at: r.fetched_at,
      became_event: !!r.became_event,
    })),
    pagination: {
      limit: params.limit,
      offset: params.offset,
      total: countRow.c,
      has_more: params.offset + rows.length < countRow.c,
    },
    available: true,
  };
}

export function isDbReachable(): { ok: boolean; last_event_at: string | null } {
  try {
    const db = getDb();
    const row = db
      .prepare("SELECT MAX(created_at) AS last FROM carbon_events")
      .get() as { last: string | null };
    return { ok: true, last_event_at: row.last };
  } catch {
    return { ok: false, last_event_at: null };
  }
}
