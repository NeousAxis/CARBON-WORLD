import fs from "fs";
import path from "path";

// Re-export shared types from the client-safe types module
export type { CarbonEvent, ExportData, Stats } from "@/lib/types";
import type { CarbonEvent, ExportData, Stats } from "@/lib/types";

// --- Data loading (server components only — uses fs/path) ---

function loadExport(): ExportData {
  const filePath = path.join(process.cwd(), "data", "export.json");
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as ExportData;
}

export function getEvents(): CarbonEvent[] {
  return loadExport().events;
}

export function getEventById(id: number): CarbonEvent | undefined {
  return loadExport().events.find((e) => e.id === id);
}

export function getStats(): Stats {
  const data = loadExport();
  return {
    totalEvents: data.total_events,
    totalBurned: data.total_burned,
    totalMinted: data.total_minted,
    netSupplyChange: data.total_minted - data.total_burned,
    generatedAt: data.generated_at,
  };
}

// --- Formatting helpers (pure functions — safe in any context) ---

export function formatAmount(raw: number): string {
  const millions = raw / 1_000_000;
  if (millions >= 1) {
    return `${millions.toFixed(1).replace(/\.0$/, "")}M CBWD`;
  }
  const thousands = raw / 1_000;
  return `${thousands.toFixed(0)}K CBWD`;
}

export function formatDate(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// Reversed events carry a "[REVERSED <date>: <reason> | Original <DECISION> tx: <sig> | Offset <DECISION> tx: <sig> | Net supply impact: 0] <original justification>"
// prefix in their justification. Extract the structured parts for clean rendering.
export interface ReverseInfo {
  date: string;
  reason: string;
  originalTx: string;
  reverseTx: string;
  originalDecision: string;
  reverseDecision: string;
}

export function parseJustification(text: string): {
  reverseInfo: ReverseInfo | null;
  cleanText: string;
} {
  const match = /^\[REVERSED\s+([^:]+):\s+([\s\S]+?)\s+\|\s+Original\s+(MINT|BURN)\s+tx:\s+(\S+)\s+\|\s+Offset\s+(MINT|BURN)\s+tx:\s+(\S+)\s+\|\s+Net supply impact:\s+0\]\s*([\s\S]*)$/.exec(text);
  if (!match) {
    return { reverseInfo: null, cleanText: text };
  }
  return {
    reverseInfo: {
      date: match[1].trim(),
      reason: match[2].trim(),
      originalDecision: match[3],
      originalTx: match[4],
      reverseDecision: match[5],
      reverseTx: match[6],
    },
    cleanText: match[7].trim(),
  };
}
