/**
 * PBNavCard — Navigation by the 9 Planetary Boundaries (Rockström et al. 2009,
 * updated by Richardson et al. 2023).
 *
 * Mirrors the SDG card but uses regex keyword matching on aspect descriptions
 * because the Analyst tags PB only at the framework level (binary), not by
 * specific boundary. Recall is therefore approximate (~80 %), marked clearly
 * in the footer. Status colour per boundary uses the 2023 Stockholm Resilience
 * Centre assessment (6 transgressed, 1 at limit, 2 within safe zone).
 *
 * Each card links to /events?pb=<slug>&since=7d for the drill-down.
 */

import Link from "next/link";
import { PB_META, PB_STATUS_COLOR, PB_STATUS_LABEL } from "@/lib/pb-meta";
import type { CarbonEvent } from "@/lib/types";

interface AspectShape {
  description?: string;
  frameworks?: string[];
}

function parseAspects(raw: string | undefined | null): AspectShape[] {
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

function describesPB(aspects: AspectShape[], patterns: RegExp[]): boolean {
  for (const a of aspects) {
    const text = a?.description ?? "";
    if (!text) continue;
    for (const re of patterns) {
      if (re.test(text)) return true;
    }
  }
  return false;
}

function computeCounts(events: CarbonEvent[]): Map<string, { burn: number; mint: number }> {
  const counts = new Map<string, { burn: number; mint: number }>();
  for (const pb of PB_META) counts.set(pb.slug, { burn: 0, mint: 0 });

  const sinceMs = Date.now() - 7 * 86400_000;
  for (const e of events) {
    if (!e.tx_hash) continue;
    if (new Date(e.created_at).getTime() < sinceMs) continue;

    const raw =
      e.decision === "BURN"
        ? e.positive_aspects_json
        : e.decision === "MINT"
        ? e.negative_aspects_json
        : null;
    if (!raw) continue;
    const aspects = parseAspects(raw);
    if (aspects.length === 0) continue;

    for (const pb of PB_META) {
      if (describesPB(aspects, pb.patterns)) {
        const c = counts.get(pb.slug)!;
        if (e.decision === "BURN") c.burn += 1;
        else if (e.decision === "MINT") c.mint += 1;
      }
    }
  }
  return counts;
}

export function PBNavCard({ events }: { events: CarbonEvent[] }) {
  const counts = computeCounts(events);
  const transgressedCount = PB_META.filter((p) => p.status === "transgressed").length;

  return (
    <div
      style={{
        backgroundColor: "#1A1A1A",
        border: "1px solid #2E2E2E",
        padding: 20,
      }}
    >
      <div className="flex items-baseline justify-between mb-4 gap-3 flex-wrap">
        <div>
          <h2
            className="text-xl font-bold uppercase tracking-wider"
            style={{ color: "#FFFFFF" }}
          >
            Browse events by planetary boundary
          </h2>
          <p
            className="font-mono text-xs mt-1 uppercase tracking-wider"
            style={{ color: "#0190A0" }}
          >
            9 boundaries · {transgressedCount} transgressed in 2023 · last 7 days, on-chain only
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-3 lg:grid-cols-5 gap-2">
        {PB_META.map((pb) => {
          const c = counts.get(pb.slug)!;
          const statusColor = PB_STATUS_COLOR[pb.status];
          const hasData = c.burn + c.mint > 0;
          return (
            <Link
              key={pb.slug}
              href={`/events?pb=${pb.slug}&since=7d`}
              className="block hover:opacity-90 transition-opacity"
              style={{
                backgroundColor: "#111111",
                border: "1px solid #2E2E2E",
                borderLeft: `3px solid ${statusColor}`,
                textDecoration: "none",
                opacity: hasData ? 1 : 0.55,
              }}
            >
              <div className="p-3">
                <div
                  className="font-mono text-[10px] uppercase tracking-wider"
                  style={{ color: statusColor }}
                >
                  PB {pb.num.toString().padStart(2, "0")} · {PB_STATUS_LABEL[pb.status]}
                </div>
                <div
                  className="text-sm font-bold mt-1 leading-tight"
                  style={{ color: "#FFFFFF" }}
                >
                  {pb.label}
                </div>
                <div
                  className="flex items-center gap-2 mt-2 font-mono text-xs"
                  style={{ color: "#B8B9B6" }}
                >
                  <span style={{ color: "#B6FFCE" }}>▲ {c.burn}</span>
                  <span style={{ color: "#666" }}>·</span>
                  <span style={{ color: "#FF5C33" }}>▽ {c.mint}</span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      <p
        className="font-mono text-[10px] mt-3 uppercase tracking-wider"
        style={{ color: "#666" }}
      >
        Counts are an approximate keyword match (~80 % recall) on aspect descriptions ·
        Framework: Rockström et al. 2009, Richardson et al. 2023 ·{" "}
        <a
          href="https://www.stockholmresilience.org/research/planetary-boundaries.html"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "#0190A0", textDecoration: "underline" }}
        >
          stockholmresilience.org
        </a>
      </p>
    </div>
  );
}
