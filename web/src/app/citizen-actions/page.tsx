import fs from "fs";
import path from "path";
import Link from "next/link";
import type { CarbonEvent, ExportData } from "@/lib/types";
import { CitizenActionsClient } from "@/components/CitizenActionsClient";

// Force dynamic rendering — read export.json fresh on every request,
// same pattern as the home page.
export const dynamic = "force-dynamic";

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

/**
 * /citizen-actions — Directory of citizen-led, NGO-led, scientific-led actions
 * surfaced by the pipeline.
 *
 * Filtering rules (server-side, applied to every event):
 *   - decision = BURN AND (
 *       burn_subtype = "editorial_consciousness"            (credible educational outlets covering it)
 *       OR event_source ∈ EDITORIAL_CONSCIOUSNESS_SOURCES   (Mongabay, Yale E360, etc.)
 *       OR final_score == 0                                  (manually reversed via /review)
 *     )
 *   - OR decision = BURN AND keywords in title hint at citizen / community / NGO action
 *
 * The result is a curated list of "things humans are doing right" —
 * structurally distinct from the global event log on the home dashboard
 * (which is everything, MINT included). Cyril's vision: "annuaire des
 * actions citoyennes".
 */
const EDITORIAL_SOURCES = new Set([
  "Mongabay",
  "Mongabay LATAM",
  "Mongabay Brasil",
  "Mongabay India",
  "Yale Environment 360",
  "Inside Climate News",
  "Reasons to be Cheerful",
  "Reporterre",
  "Carbon Brief",
  "China Dialogue",
  "Diálogo Chino EN",
  "Grist",
  "Grist Solutions",
  "The New Humanitarian",
  "Solutions Journalism Network",
  "Positive News",
  "Good News Network",
  "Yes Magazine",
  "Good Good Good",
  "Atlas of the Future",
  "Springwise (innovations)",
  "Anthropocene Magazine",
  "Cultural Survival",
  "Greenpeace International",
  "Sea Shepherd",
  "Rainforest Trust",
  "Oceana Blog",
  "Rewilding Europe",
  "Waging Nonviolence",
  "Shareable",
]);

const CITIZEN_KEYWORDS = [
  /\bvolunteer/i,
  /\bcommunity-led\b/i,
  /\bgrassroots\b/i,
  /\bcitizen[s]?\b/i,
  /\bindigenous\b/i,
  /\bcooperative[s]?\b/i,
  /\bcoalition\b/i,
  /\bNGO\b/i,
  /\bactivist[s]?\b/i,
  /\bstudents\b/i,
  /\bhigh-school\b/i,
  /\binventor[s]?\b/i,
  /\binvention\b/i,
  /\bbreakthrough\b/i,
  /\binitiative[s]?\b/i,
  /\bprotest\b/i,
  /\brestoration\b/i,
  /\brescue\b/i,
];

function isCitizenAction(e: CarbonEvent): boolean {
  if (e.decision !== "BURN") return false;
  if (e.burn_subtype === "editorial_consciousness") return true;
  if (EDITORIAL_SOURCES.has(e.event_source ?? "")) return true;
  if ((e.final_score ?? 0) === 0) return true; // manually reversed
  const text = `${e.event_title ?? ""} ${e.justification ?? ""}`;
  return CITIZEN_KEYWORDS.some((re) => re.test(text));
}

export default function CitizenActionsPage() {
  const allEvents = loadEvents();
  const citizen = allEvents
    .filter(isCitizenAction)
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
    );

  // Stats by region
  const regionCounts: Record<string, number> = {};
  for (const e of citizen) {
    const r = e.region ?? "Global / cross-border";
    regionCounts[r] = (regionCounts[r] ?? 0) + 1;
  }
  const regions = Object.entries(regionCounts).sort((a, b) => b[1] - a[1]);

  // Stats by source
  const sourceCounts: Record<string, number> = {};
  for (const e of citizen) {
    const s = e.event_source ?? "(unknown)";
    sourceCounts[s] = (sourceCounts[s] ?? 0) + 1;
  }
  const topSources = Object.entries(sourceCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  return (
    <div
      className="mx-auto max-w-6xl px-4 sm:px-6 py-8 sm:py-12"
      style={{ backgroundColor: "#111111" }}
    >
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm hover:opacity-80 mb-6 sm:mb-8"
        style={{ color: "#B8B9B6" }}
      >
        &larr; Back to dashboard
      </Link>

      <h1
        className="text-2xl sm:text-3xl font-bold mb-2"
        style={{ color: "#FFFFFF" }}
      >
        Citizen actions directory
      </h1>
      <p
        className="leading-relaxed mb-8 max-w-3xl"
        style={{ color: "#B8B9B6" }}
      >
        A curated, real-time directory of citizen-led, community-led, NGO and
        scientific actions surfaced by the pipeline — the &laquo;{" "}
        <strong style={{ color: "#B6FFCE" }}>BURN</strong> &raquo; verdicts
        whose structural origin is consciousness, not government decree.
        Filters: editorial-consciousness BURNs, manually reversed BURNs, and
        events whose title or justification mentions citizen / community / NGO
        / indigenous / inventor / breakthrough patterns.
      </p>

      {/* Top stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <div
          className="p-4"
          style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
        >
          <p
            className="text-xs uppercase tracking-wider font-mono mb-2"
            style={{ color: "var(--brand-teal, #0190A0)" }}
          >
            TOTAL CITIZEN ACTIONS
          </p>
          <p className="text-3xl font-mono font-bold" style={{ color: "#B6FFCE" }}>
            {citizen.length}
          </p>
        </div>
        <div
          className="p-4"
          style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
        >
          <p
            className="text-xs uppercase tracking-wider font-mono mb-2"
            style={{ color: "var(--brand-teal, #0190A0)" }}
          >
            DISTINCT SOURCES
          </p>
          <p className="text-3xl font-mono font-bold" style={{ color: "#FFFFFF" }}>
            {Object.keys(sourceCounts).length}
          </p>
        </div>
        <div
          className="p-4"
          style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
        >
          <p
            className="text-xs uppercase tracking-wider font-mono mb-2"
            style={{ color: "var(--brand-teal, #0190A0)" }}
          >
            REGIONS COVERED
          </p>
          <p className="text-3xl font-mono font-bold" style={{ color: "#FFFFFF" }}>
            {regions.length}
          </p>
        </div>
      </div>

      {/* Region breakdown */}
      {regions.length > 0 && (
        <div className="mb-8">
          <p
            className="text-xs uppercase tracking-wider font-mono mb-3"
            style={{ color: "var(--brand-teal, #0190A0)" }}
          >
            BY REGION
          </p>
          <div className="flex flex-wrap gap-2">
            {regions.map(([r, n]) => (
              <span
                key={r}
                className="font-mono text-xs px-3 py-1.5"
                style={{
                  backgroundColor: "#1A1A1A",
                  border: "1px solid #2E2E2E",
                  color: "#B8B9B6",
                }}
              >
                {r}{" "}
                <span style={{ color: "#B6FFCE", marginLeft: 6 }}>{n}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Top sources */}
      {topSources.length > 0 && (
        <div className="mb-8">
          <p
            className="text-xs uppercase tracking-wider font-mono mb-3"
            style={{ color: "var(--brand-teal, #0190A0)" }}
          >
            TOP SOURCES
          </p>
          <div className="flex flex-wrap gap-2">
            {topSources.map(([s, n]) => (
              <span
                key={s}
                className="font-mono text-xs px-3 py-1.5"
                style={{
                  backgroundColor: "#1A1A1A",
                  border: "1px solid #2E2E2E",
                  color: "#B8B9B6",
                }}
              >
                {s}{" "}
                <span style={{ color: "#B6FFCE", marginLeft: 6 }}>{n}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* The list — client component for filter/search */}
      <CitizenActionsClient events={citizen} />
    </div>
  );
}
