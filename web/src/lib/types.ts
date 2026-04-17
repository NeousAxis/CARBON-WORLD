// Shared types used by both server and client components.
// This file MUST NOT import 'fs' or 'path' — it is included in client bundles.

export interface CarbonEvent {
  id: number;
  event_title: string;
  event_url: string;
  event_source: string;
  decision: "BURN" | "MINT" | "NEUTRAL";
  amount_crbn: number;
  final_score: number;
  confidence: number;
  justification: string;
  tx_hash: string | null;
  created_at: string;
}

export interface ExportData {
  generated_at: string;
  total_events: number;
  total_burned: number;
  total_minted: number;
  events: CarbonEvent[];
}

export interface Stats {
  totalEvents: number;
  totalBurned: number;
  totalMinted: number;
  netSupplyChange: number;
  generatedAt: string;
}
