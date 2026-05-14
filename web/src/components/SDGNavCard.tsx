/**
 * SDGNavCard — Visible navigation by the 17 UN Sustainable Development Goals.
 *
 * Replaces the earlier narrative ThemesNavCard with the canonical international
 * framework already used by the Analyst agents (each event's positive/negative
 * aspects carry an `affected_sdgs` array). This means filtering by SDG matches
 * the Analyst output exactly — no regex approximation, 100 % precision.
 *
 * For each SDG we count:
 *  - burn: BURN events whose positive_aspects mention this SDG
 *  - mint: MINT events whose negative_aspects mention this SDG
 * over the last 7 days, on-chain only (tx_hash present).
 *
 * Clicking a card opens /events?sdg=<num>&since=7d.
 */

import Image from "next/image";
import Link from "next/link";
import { SDG_META, sdgIconId } from "@/lib/sdg-meta";
import type { CarbonEvent } from "@/lib/types";

interface SDGAspect {
  affected_sdgs?: number[];
  sdgs?: number[];
}

function parseAspects(raw: string | undefined | null): SDGAspect[] {
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

function collectSDGs(aspects: SDGAspect[]): Set<number> {
  const set = new Set<number>();
  for (const a of aspects) {
    const list = a.affected_sdgs ?? a.sdgs ?? [];
    for (const n of list) {
      if (typeof n === "number" && n >= 1 && n <= 17) set.add(n);
    }
  }
  return set;
}

function computeCounts(events: CarbonEvent[]): Map<number, { burn: number; mint: number }> {
  const counts = new Map<number, { burn: number; mint: number }>();
  for (let i = 1; i <= 17; i++) counts.set(i, { burn: 0, mint: 0 });

  const sinceMs = Date.now() - 7 * 86400_000;
  for (const e of events) {
    if (!e.tx_hash) continue;
    if (new Date(e.created_at).getTime() < sinceMs) continue;

    if (e.decision === "BURN") {
      const sdgs = collectSDGs(parseAspects(e.positive_aspects_json));
      for (const n of sdgs) counts.get(n)!.burn += 1;
    } else if (e.decision === "MINT") {
      const sdgs = collectSDGs(parseAspects(e.negative_aspects_json));
      for (const n of sdgs) counts.get(n)!.mint += 1;
    }
  }
  return counts;
}

export function SDGNavCard({ events }: { events: CarbonEvent[] }) {
  const counts = computeCounts(events);

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
            Browse events by SDG
          </h2>
          <p
            className="font-mono text-xs mt-1 uppercase tracking-wider"
            style={{ color: "#0190A0" }}
          >
            17 UN Sustainable Development Goals · last 7 days, on-chain only
          </p>
        </div>
        <Link
          href="/events?since=7d"
          className="font-mono text-xs uppercase tracking-wider hover:opacity-80"
          style={{ color: "#FF8400", textDecoration: "none" }}
        >
          See all events →
        </Link>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2">
        {SDG_META.map((sdg) => {
          const c = counts.get(sdg.num)!;
          const hasData = c.burn + c.mint > 0;
          return (
            <Link
              key={sdg.num}
              href={`/events?sdg=${sdg.num}&since=7d`}
              className="block hover:opacity-90 transition-opacity"
              style={{
                backgroundColor: "#111111",
                border: "1px solid #2E2E2E",
                textDecoration: "none",
                opacity: hasData ? 1 : 0.55,
              }}
            >
              <div
                className="flex items-center gap-2 p-2"
                style={{ backgroundColor: sdg.color, color: "#FFFFFF" }}
              >
                <Image
                  src={`/sdg/${sdgIconId(sdg.num)}.png`}
                  alt={`SDG ${sdg.num} — ${sdg.fullName}`}
                  width={40}
                  height={40}
                  className="shrink-0"
                  style={{ display: "block" }}
                />
                <div className="min-w-0 flex-1">
                  <div className="font-mono text-[10px] opacity-80 leading-none">
                    SDG {sdg.num.toString().padStart(2, "0")}
                  </div>
                  <div className="text-xs font-bold leading-tight mt-0.5 truncate">
                    {sdg.label}
                  </div>
                </div>
              </div>
              <div
                className="flex justify-between items-center px-2 py-1.5 font-mono text-xs"
                style={{ color: "#B8B9B6" }}
              >
                <span>
                  <span style={{ color: "#B6FFCE" }}>▲ {c.burn}</span>
                  <span style={{ color: "#666", margin: "0 4px" }}>·</span>
                  <span style={{ color: "#FF5C33" }}>▽ {c.mint}</span>
                </span>
              </div>
            </Link>
          );
        })}
      </div>

      <p
        className="font-mono text-[10px] mt-3 uppercase tracking-wider"
        style={{ color: "#666" }}
      >
        Calibrated on the 17 UN Sustainable Development Goals · Adopted by all UN Member States in 2015 ·{" "}
        <a
          href="https://sdgs.un.org/goals"
          target="_blank"
          rel="noopener noreferrer"
          style={{ color: "#0190A0", textDecoration: "underline" }}
        >
          sdgs.un.org
        </a>
      </p>
    </div>
  );
}
