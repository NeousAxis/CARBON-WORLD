// Shared types used by both server and client components.
// This file MUST NOT import 'fs' or 'path' — it is included in client bundles.

export interface CarbonEvent {
  id: number;
  event_title: string;
  event_url: string;
  event_source: string;
  decision: "BURN" | "MINT" | "NEUTRAL";
  amount_crbn: number;
  /**
   * Display-only calibrated amount (magnitude-driven, symmetric BURN/MINT).
   * Used by the dashboard headline so the net signal is not distorted by the
   * ~6.4x BURN over-tokenisation baked into the raw on-chain amount_crbn.
   * Falls back to amount_crbn when absent (older exports).
   */
  amount_index?: number;
  final_score: number;
  confidence: number;
  justification: string;
  tx_hash: string | null;
  created_at: string;
  country?: string | null;
  region?: string | null;
  administration?: string | null;
  burn_subtype?: string | null;
  mint_subtype?: string | null;
  /** JSON string: array of {description, affected_sdgs, magnitude, ...}. */
  positive_aspects_json?: string | null;
  negative_aspects_json?: string | null;
}

export interface CountryStat {
  country: string;
  count: number;
  total_amount: number;
}

export interface RegionStat {
  region: string;
  burn_ratio: number;
  events: number;
}

export interface AdministrationStat {
  administration: string;
  burn_ratio: number;
  events: number;
}

export interface SupplyTrendPoint {
  date: string;
  net_minted: number;
  net_burned: number;
}

export interface EventOfTheDay {
  id: number;
  event_title: string;
  decision: "BURN" | "MINT" | "NEUTRAL";
  amount_crbn: number;
  final_score: number;
  confidence?: number;
  country?: string | null;
  region?: string | null;
  created_at?: string;
}

export interface FrameworkActivityCounts {
  positive: number;
  negative: number;
  /** event IDs whose positive aspects reference this framework (on-chain only) */
  event_ids_positive?: number[];
  /** event IDs whose negative aspects reference this framework (on-chain only) */
  event_ids_negative?: number[];
}

export interface FrameworkActivityData {
  SDG: FrameworkActivityCounts;
  UDHR: FrameworkActivityCounts;
  ILO: FrameworkActivityCounts;
  CRC: FrameworkActivityCounts;
  UNDRIP: FrameworkActivityCounts;
  Animal: FrameworkActivityCounts;
  PB: FrameworkActivityCounts;
}

export interface SourceDiversity {
  niche_pct: number;
  mainstream_pct: number;
  total_sources_used: number;
  articles_processed: number;
}

export interface CacheHitRate {
  hits: number;
  total_events: number;
  pct: number;
}

export interface PartnerActivity {
  organization: string;
  submissions: number;
}

export interface PositiveStreak {
  current: number;
  longest_7d: number;
}

export interface TaxonomyEntry {
  name: string;
  count: number;
  burn_count: number;
  mint_count: number;
  /** event IDs the worker classified under this name (on-chain only) */
  event_ids?: number[];
}

export interface BurnSubtypeStat {
  count: number;
  pct: number;
}

export interface BurnComposition {
  total_burn: number;
  direct_action: BurnSubtypeStat;
  editorial_consciousness: BurnSubtypeStat;
  untyped: BurnSubtypeStat;
}

export interface MintComposition {
  total_mint: number;
  direct_action: BurnSubtypeStat;
  editorial_alarm: BurnSubtypeStat;
  untyped: BurnSubtypeStat;
}

export interface DestructiveRegionStat {
  region: string;
  mint_ratio: number;
  events: number;
}

export interface CitizenVsInstitutionalDay {
  date: string;
  citizen: number;
  institutional: number;
}

export interface CitizenVsInstitutional {
  /** Total citizen-led events on the 7d window (on-chain only). */
  citizen: number;
  /** Total institutional / governmental events on the 7d window. */
  institutional: number;
  /** citizen / (citizen + institutional), 0..1. */
  citizen_ratio: number;
  /** 7 daily buckets oldest → newest (gaps filled with 0/0). */
  daily: CitizenVsInstitutionalDay[];
  /** Canonical IDs the worker classified as citizen-led. */
  event_ids_citizen?: number[];
  /** Canonical IDs the worker classified as institutional. */
  event_ids_institutional?: number[];
}

export interface Aggregates {
  top_countries_mint: CountryStat[];
  top_countries_burn: CountryStat[];
  top_regions_sustainable: RegionStat[];
  supply_trend_7d: SupplyTrendPoint[];
  event_of_the_day: EventOfTheDay | null;
  framework_activity_7d: FrameworkActivityData;
  source_diversity_7d: SourceDiversity;
  cache_hit_rate_7d: CacheHitRate;
  active_partners_7d: PartnerActivity[];
  top_institutions_7d: TaxonomyEntry[];
  top_sectors_7d: TaxonomyEntry[];
  burn_composition_7d?: BurnComposition;
  burn_composition_all_time?: BurnComposition;
  mint_composition_7d?: MintComposition;
  mint_composition_all_time?: MintComposition;
  top_regions_destructive?: DestructiveRegionStat[];
  citizen_vs_institutional_7d?: CitizenVsInstitutional;
}

export interface ExportData {
  generated_at: string;
  total_events: number;
  total_burned: number;
  total_minted: number;
  events: CarbonEvent[];
  aggregates?: Aggregates;
}

export interface Stats {
  totalEvents: number;
  totalBurned: number;
  totalMinted: number;
  netSupplyChange: number;
  generatedAt: string;
}
