/**
 * /events — Generic filtered events list.
 *
 * Drill-down target for every dashboard card: clicking a country / region /
 * institution / sector / framework row opens this page with the matching
 * filter applied. Lists every event that justifies the aggregate number.
 *
 * Supported query params:
 *   country=<exact>           — match CarbonEvent.country
 *   region=<exact>            — match CarbonEvent.region
 *   administration=<exact>    — match CarbonEvent.administration
 *   decision=BURN|MINT|NEUTRAL
 *   sector=<id>               — animal|environment|social|health|invention|community
 *   institution=<keyword>     — text match in title/justification
 *   framework=<code>          — SDG|UDHR|ILO|CRC|UNDRIP|Animal|PB (justification text match)
 *   framework_polarity=positive|negative
 *                             — when paired with framework, also forces decision=BURN/MINT
 *   since=7d|30d|all          — default 7d
 */

import fs from "node:fs";
import path from "node:path";
import Link from "next/link";
import type { CarbonEvent, ExportData } from "@/lib/types";
import { formatAmount } from "@/components/indicators/formatAmount";

export const dynamic = "force-dynamic";

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

function loadEvents(): CarbonEvent[] {
  const filePath = path.join(process.cwd(), "data", "export.json");
  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    const data = JSON.parse(raw) as ExportData;
    return data.events ?? [];
  } catch {
    return [];
  }
}

// ---------------------------------------------------------------------------
// Filter taxonomy — copied from CitizenActionsClient (sector) + new framework
// patterns (matches the heuristics the worker uses in framework_activity).
// ---------------------------------------------------------------------------

const SECTOR_RULES: Array<{ id: string; label: string; patterns: RegExp[] }> = [
  {
    id: "animal",
    label: "Animal",
    patterns: [/\banimal[s]?\b/i, /\bwildlife\b/i, /\bspecies\b/i, /\bbiodivers/i, /\bpets?\b/i, /\bzoonotic\b/i, /\bpoach/i, /\bextinction\b/i, /\bendangered\b/i],
  },
  {
    id: "environment",
    label: "Environment",
    patterns: [/\bclimate\b/i, /\bemission/i, /\bcarbon\b/i, /\bdeforest/i, /\bfossil\b/i, /\brenewabl/i, /\bsolar\b/i, /\bwind\b/i, /\bocean\b/i, /\bforest\b/i, /\bpollut/i, /\bgreenhouse\b/i],
  },
  {
    id: "social",
    label: "Social rights",
    patterns: [/\brights?\b/i, /\bindigenous\b/i, /\bgender\b/i, /\bequality\b/i, /\bmigra/i, /\brefugee/i, /\bdiscriminat/i, /\bdisabilit/i, /\bchild/i, /\beducation\b/i, /\bjustice\b/i],
  },
  {
    id: "health",
    label: "Health",
    patterns: [/\bhealth\b/i, /\bmedic/i, /\bvaccin/i, /\bdisease\b/i, /\bvirus\b/i, /\bcancer\b/i, /\bpandemic\b/i, /\bsanit/i, /\bnutrition\b/i, /\bmental health\b/i],
  },
  {
    id: "invention",
    label: "Invention",
    patterns: [/\binvent/i, /\bbreakthrough\b/i, /\bdiscover/i, /\bpatent/i, /\binnovation\b/i, /\bprototype\b/i, /\bscientist[s]?\b/i, /\bresearch\b/i],
  },
  {
    id: "community",
    label: "Community",
    patterns: [/\bcommunity\b/i, /\bcooperative\b/i, /\bcoalition\b/i, /\bgrassroots\b/i, /\bvolunteer/i, /\bmutual aid\b/i, /\blocal\b/i, /\bcitizen[s]?\b/i, /\bneighbour/i, /\bneighborhood\b/i],
  },
];

const FRAMEWORK_PATTERNS: Record<string, RegExp> = {
  SDG: /\bSDG[s]?\s*\d*\b|sustainable development goal/i,
  UDHR: /UDHR|universal declaration of human rights/i,
  ILO: /\bILO\b|international labour organization|labour standard/i,
  CRC: /\bCRC\b|convention on the rights of the child/i,
  UNDRIP: /UNDRIP|indigenous peoples?\b/i,
  Animal: /universal declaration of animal rights|animal rights/i,
  PB: /planetary bound|rockstrom|9 limits/i,
};

// ---------------------------------------------------------------------------
// Filter pipeline
// ---------------------------------------------------------------------------

interface Filters {
  country?: string;
  region?: string;
  administration?: string;
  decision?: string;
  sector?: string;
  institution?: string;
  framework?: string;
  frameworkPolarity?: string;
  since: "7d" | "30d" | "all";
}

function matchesSector(e: CarbonEvent, sectorId: string): boolean {
  const rule = SECTOR_RULES.find((r) => r.id.toLowerCase() === sectorId.toLowerCase());
  const hay = `${e.event_title ?? ""} ${e.justification ?? ""}`;
  if (rule) return rule.patterns.some((re) => re.test(hay));
  // Fallback: free-form sector name (e.g. coming from the worker taxonomy)
  // becomes a keyword match in title+justification.
  return hay.toLowerCase().includes(sectorId.toLowerCase());
}

function matchesFramework(e: CarbonEvent, code: string): boolean {
  const re = FRAMEWORK_PATTERNS[code];
  if (!re) return false;
  const hay = `${e.event_title ?? ""} ${e.justification ?? ""}`;
  return re.test(hay);
}

function matchesInstitution(e: CarbonEvent, keyword: string): boolean {
  const hay = `${e.event_title ?? ""} ${e.justification ?? ""}`.toLowerCase();
  return hay.includes(keyword.toLowerCase());
}

function applyFilters(events: CarbonEvent[], f: Filters): CarbonEvent[] {
  const sinceMs = (() => {
    if (f.since === "all") return 0;
    if (f.since === "30d") return Date.now() - 30 * 86400_000;
    return Date.now() - 7 * 86400_000; // default 7d
  })();

  return events.filter((e) => {
    if (sinceMs > 0 && new Date(e.created_at).getTime() < sinceMs) return false;

    if (f.country && (e.country ?? "") !== f.country) return false;
    if (f.region && (e.region ?? "") !== f.region) return false;
    if (f.administration && (e.administration ?? "") !== f.administration) return false;

    if (f.decision) {
      // framework_polarity overrides decision when set
      if (!f.frameworkPolarity && e.decision !== f.decision) return false;
    }

    if (f.framework) {
      if (!matchesFramework(e, f.framework)) return false;
      if (f.frameworkPolarity === "positive" && e.decision !== "BURN") return false;
      if (f.frameworkPolarity === "negative" && e.decision !== "MINT") return false;
    }

    if (f.sector && !matchesSector(e, f.sector)) return false;
    if (f.institution && !matchesInstitution(e, f.institution)) return false;

    return true;
  });
}

// ---------------------------------------------------------------------------
// Page (Server Component)
// ---------------------------------------------------------------------------

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function EventsPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const get = (k: string): string | undefined => {
    const v = sp[k];
    return typeof v === "string" ? v : Array.isArray(v) ? v[0] : undefined;
  };

  const since = (get("since") as Filters["since"]) ?? "7d";
  const filters: Filters = {
    country: get("country"),
    region: get("region"),
    administration: get("administration"),
    decision: get("decision"),
    sector: get("sector"),
    institution: get("institution"),
    framework: get("framework"),
    frameworkPolarity: get("framework_polarity"),
    since: ["7d", "30d", "all"].includes(since) ? since : "7d",
  };

  const all = loadEvents();
  const filtered = applyFilters(all, filters).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  // Build a human-readable "active filters" line
  const activeChips: Array<{ label: string; value: string }> = [];
  if (filters.country) activeChips.push({ label: "Country", value: filters.country });
  if (filters.region) activeChips.push({ label: "Region", value: filters.region });
  if (filters.administration) activeChips.push({ label: "Administration", value: filters.administration });
  if (filters.decision && !filters.frameworkPolarity) activeChips.push({ label: "Decision", value: filters.decision });
  if (filters.framework) {
    const polarity = filters.frameworkPolarity === "positive" ? " (positive · BURN)" : filters.frameworkPolarity === "negative" ? " (negative · MINT)" : "";
    activeChips.push({ label: "Framework", value: filters.framework + polarity });
  }
  if (filters.sector) {
    const lab = SECTOR_RULES.find((r) => r.id === filters.sector)?.label ?? filters.sector;
    activeChips.push({ label: "Sector", value: lab });
  }
  if (filters.institution) activeChips.push({ label: "Institution", value: filters.institution });
  activeChips.push({ label: "Since", value: filters.since });

  // Aggregate of the filtered set (mirrors the "number" the user came from)
  const totalAmount = filtered.reduce((s, e) => s + (e.amount_crbn ?? 0), 0);
  const burnCount = filtered.filter((e) => e.decision === "BURN").length;
  const mintCount = filtered.filter((e) => e.decision === "MINT").length;

  return (
    <div className="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-12" style={{ backgroundColor: "#111111" }}>
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm hover:opacity-80 mb-6 sm:mb-8"
        style={{ color: "#B8B9B6" }}
      >
        &larr; Back to dashboard
      </Link>

      <h1 className="text-2xl sm:text-3xl font-bold mb-2" style={{ color: "#FFFFFF" }}>
        Events behind the numbers
      </h1>
      <p className="leading-relaxed mb-6 max-w-3xl" style={{ color: "#B8B9B6" }}>
        Each event listed below contributes to the dashboard aggregate you clicked on.
        Click any title to open its full ethical analysis (the 7-framework breakdown,
        the 4D scoring, the on-chain transaction).
      </p>

      {/* Active filter chips */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {activeChips.map((c) => (
          <span
            key={`${c.label}:${c.value}`}
            className="font-mono text-xs px-3 py-1.5"
            style={{
              backgroundColor: "#1A1A1A",
              border: "1px solid #2E2E2E",
              color: "#B8B9B6",
            }}
          >
            <span style={{ color: "#666", marginRight: 6 }}>{c.label.toUpperCase()}</span>
            <span style={{ color: "#B6FFCE" }}>{c.value}</span>
          </span>
        ))}
        <Link
          href="/events?since=7d"
          className="font-mono text-xs px-3 py-1.5"
          style={{
            backgroundColor: "transparent",
            border: "1px solid #2E2E2E",
            color: "#FF8400",
            textDecoration: "none",
          }}
        >
          CLEAR
        </Link>
      </div>

      {/* Aggregate strip */}
      <div
        className="flex flex-wrap items-center gap-3 sm:gap-6 mb-6 p-3 sm:p-4 text-xs"
        style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
      >
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>EVENTS</span>
          <span className="font-mono font-bold" style={{ color: "#FFFFFF" }}>{filtered.length}</span>
        </div>
        <div style={{ width: 1, height: 16, backgroundColor: "#2E2E2E" }} />
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>BURN</span>
          <span className="font-mono font-bold" style={{ color: "#B6FFCE" }}>{burnCount}</span>
        </div>
        <div style={{ width: 1, height: 16, backgroundColor: "#2E2E2E" }} />
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>MINT</span>
          <span className="font-mono font-bold" style={{ color: "#FF5C33" }}>{mintCount}</span>
        </div>
        <div style={{ width: 1, height: 16, backgroundColor: "#2E2E2E" }} />
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>TOTAL CBWD</span>
          <span className="font-mono font-bold" style={{ color: "#FFFFFF" }}>{formatAmount(totalAmount)}</span>
        </div>
      </div>

      {/* Empty state */}
      {filtered.length === 0 ? (
        <div
          className="p-8 text-center font-mono text-sm"
          style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E", color: "#B8B9B6" }}
        >
          No events match these filters in the selected time window.
        </div>
      ) : (
        <div className="flex flex-col">
          {filtered.map((e) => {
            const isBurn = e.decision === "BURN";
            return (
              <Link
                key={e.id}
                href={`/event/${e.id}`}
                className="block p-4 hover:opacity-90"
                style={{
                  backgroundColor: "#1A1A1A",
                  border: "1px solid #2E2E2E",
                  borderLeft: `3px solid ${isBurn ? "#B6FFCE" : "#FF5C33"}`,
                  marginBottom: 8,
                  transition: "background-color 120ms",
                }}
              >
                <div className="flex items-center gap-3 mb-2 text-xs font-mono">
                  <span
                    className="font-bold uppercase tracking-wider"
                    style={{ color: isBurn ? "#B6FFCE" : "#FF5C33" }}
                  >
                    {e.decision}
                  </span>
                  <span style={{ color: "#666" }}>·</span>
                  <span style={{ color: isBurn ? "#B6FFCE" : "#FF5C33" }}>
                    {isBurn ? "-" : "+"}{formatAmount(e.amount_crbn)} CBWD
                  </span>
                  <span style={{ color: "#666" }}>·</span>
                  <span style={{ color: "#B8B9B6" }}>{e.event_source}</span>
                  {e.country && (
                    <>
                      <span style={{ color: "#666" }}>·</span>
                      <span style={{ color: "#B8B9B6" }}>{e.country}</span>
                    </>
                  )}
                  <span style={{ color: "#666" }}>·</span>
                  <span style={{ color: "#666" }}>
                    {new Date(e.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                  </span>
                </div>
                <p className="text-sm leading-snug" style={{ color: "#FFFFFF" }}>
                  {e.event_title}
                </p>
                {e.justification && (
                  <p className="text-xs leading-relaxed mt-2 font-mono" style={{ color: "#B8B9B6" }}>
                    {e.justification.length > 240 ? e.justification.slice(0, 240) + "…" : e.justification}
                  </p>
                )}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
