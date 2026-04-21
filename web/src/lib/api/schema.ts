/**
 * schema.ts — TypeScript types for public API v1 responses.
 */

export interface PublicEvent {
  id: number;
  title: string;
  url: string;
  source: string;
  decision: "BURN" | "MINT" | "NEUTRAL";
  amount_cbwd: number;
  final_score: number;
  confidence: number;
  created_at: string;
  solana_tx: string | null;
  link_explorer: string | null;
  reused_from_event_id: number | null;
}

export interface PublicEventDetail extends PublicEvent {
  justification: string;
}

export interface Pagination {
  limit: number;
  offset: number;
  total: number;
  has_more: boolean;
}

export interface EventsResponse {
  events: PublicEvent[];
  pagination: Pagination;
}

export interface StatsResponse {
  total_events: number;
  by_decision: {
    BURN: number;
    MINT: number;
    NEUTRAL: number;
  };
  total_supply: {
    minted: number;
    burned: number;
    net: number;
  };
  last_event_at: string | null;
  cache_stats: {
    events_with_embedding: number;
    reused_events: number;
  };
}

export interface SourceEntry {
  name: string;
  url: string;
}

export interface SourcesResponse {
  sources: SourceEntry[];
  count: number;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  version: string;
  db_reachable: boolean;
  last_event_at: string | null;
}
