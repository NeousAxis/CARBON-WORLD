"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import type { CarbonEvent } from "@/lib/types";

interface CitizenActionsClientProps {
  events: CarbonEvent[];
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// Theme classifier — maps an event to one or more high-level categories.
// Heuristic: regex on title + justification + event_source. Multi-label
// (an event can be both ANIMAL and ENVIRONMENT).
const THEME_RULES: Array<{ id: string; label: string; color: string; patterns: RegExp[] }> = [
  {
    id: "animal",
    label: "Animal",
    color: "#FFB347",
    patterns: [/\banimal[s]?\b/i, /\bwildlife\b/i, /\bspecies\b/i, /\bbiodivers/i, /\bpets?\b/i, /\bzoonotic\b/i, /\bpoach/i, /\bextinction\b/i, /\bendangered\b/i],
  },
  {
    id: "environment",
    label: "Environment",
    color: "#7DD3FC",
    patterns: [/\bclimate\b/i, /\bemission/i, /\bcarbon\b/i, /\bdeforest/i, /\bfossil\b/i, /\brenewabl/i, /\bsolar\b/i, /\bwind\b/i, /\bocean\b/i, /\bforest\b/i, /\bpollut/i, /\bgreenhouse\b/i],
  },
  {
    id: "social",
    label: "Social rights",
    color: "#C4B5FD",
    patterns: [/\brights?\b/i, /\bindigenous\b/i, /\bgender\b/i, /\bequality\b/i, /\bmigra/i, /\brefugee/i, /\bdiscriminat/i, /\bdisabilit/i, /\bchild/i, /\beducation\b/i, /\bjustice\b/i],
  },
  {
    id: "health",
    label: "Health",
    color: "#FCA5A5",
    patterns: [/\bhealth\b/i, /\bmedic/i, /\bvaccin/i, /\bdisease\b/i, /\bvirus\b/i, /\bcancer\b/i, /\bpandemic\b/i, /\bsanit/i, /\bnutrition\b/i, /\bmental health\b/i],
  },
  {
    id: "invention",
    label: "Invention",
    color: "#86EFAC",
    patterns: [/\binvent/i, /\bbreakthrough\b/i, /\bbreakthrough\b/i, /\bdiscover/i, /\bpatent/i, /\binnovation\b/i, /\bprototype\b/i, /\bscientist[s]?\b/i, /\bresearch\b/i],
  },
  {
    id: "community",
    label: "Community",
    color: "#FDE68A",
    patterns: [/\bcommunity\b/i, /\bcooperative\b/i, /\bcoalition\b/i, /\bgrassroots\b/i, /\bvolunteer/i, /\bmutual aid\b/i, /\blocal\b/i, /\bcitizen[s]?\b/i, /\bneighbour/i, /\bneighborhood\b/i],
  },
];

function detectThemes(e: CarbonEvent): string[] {
  const text = `${e.event_title ?? ""} ${e.justification ?? ""}`;
  const out: string[] = [];
  for (const rule of THEME_RULES) {
    if (rule.patterns.some((re) => re.test(text))) out.push(rule.id);
  }
  return out;
}

function ThemeBadge({ themeId }: { themeId: string }) {
  const rule = THEME_RULES.find((r) => r.id === themeId);
  if (!rule) return null;
  return (
    <span
      className="px-2 py-0.5 text-[10px] uppercase tracking-wider font-mono"
      style={{
        backgroundColor: "transparent",
        border: `1px solid ${rule.color}`,
        color: rule.color,
      }}
    >
      {rule.label}
    </span>
  );
}

/**
 * Search + region/source filter on top of the server-rendered citizen-actions
 * list. Pure client interaction — no extra fetch, the parent page already
 * pre-filtered the data.
 */
export function CitizenActionsClient({ events }: CitizenActionsClientProps) {
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState<string>("");
  const [source, setSource] = useState<string>("");
  const [theme, setTheme] = useState<string>("");

  // Pre-compute themes once per event for stable filtering & rendering
  const eventsWithThemes = useMemo(
    () => events.map((e) => ({ ...e, _themes: detectThemes(e) })),
    [events],
  );

  const regionsList = useMemo(() => {
    const set = new Set<string>();
    for (const e of events) if (e.region) set.add(e.region);
    return Array.from(set).sort();
  }, [events]);

  const sourcesList = useMemo(() => {
    const set = new Set<string>();
    for (const e of events) if (e.event_source) set.add(e.event_source);
    return Array.from(set).sort();
  }, [events]);

  // Theme counts for the pill row
  const themeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of eventsWithThemes) {
      for (const t of e._themes) counts[t] = (counts[t] ?? 0) + 1;
    }
    return counts;
  }, [eventsWithThemes]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return eventsWithThemes.filter((e) => {
      if (region && e.region !== region) return false;
      if (source && e.event_source !== source) return false;
      if (theme && !e._themes.includes(theme)) return false;
      if (q) {
        const hay = `${e.event_title ?? ""} ${e.justification ?? ""} ${
          e.event_source ?? ""
        } ${e.country ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [eventsWithThemes, query, region, source, theme]);

  return (
    <div>
      {/* Theme pills — multi-label classifier on title + justification */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => setTheme("")}
          className="px-3 py-1.5 text-xs font-mono uppercase tracking-wider"
          style={{
            backgroundColor: theme === "" ? "#2E2E2E" : "transparent",
            border: "1px solid #2E2E2E",
            color: theme === "" ? "#FFFFFF" : "#B8B9B6",
            cursor: "pointer",
          }}
        >
          ALL · {events.length}
        </button>
        {THEME_RULES.map((r) => {
          const n = themeCounts[r.id] ?? 0;
          if (n === 0) return null;
          const sel = theme === r.id;
          return (
            <button
              key={r.id}
              onClick={() => setTheme(sel ? "" : r.id)}
              className="px-3 py-1.5 text-xs font-mono uppercase tracking-wider"
              style={{
                backgroundColor: sel ? r.color + "22" : "transparent",
                border: `1px solid ${sel ? r.color : "#2E2E2E"}`,
                color: sel ? r.color : "#B8B9B6",
                cursor: "pointer",
              }}
            >
              {r.label} · {n}
            </button>
          );
        })}
      </div>

      {/* Search + filters */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-6">
        <input
          type="text"
          placeholder="Search title, source, country…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="px-3 py-2 text-sm font-mono"
          style={{
            backgroundColor: "#1A1A1A",
            border: "1px solid #2E2E2E",
            color: "#FFFFFF",
            outline: "none",
          }}
        />
        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="px-3 py-2 text-sm font-mono"
          style={{
            backgroundColor: "#1A1A1A",
            border: "1px solid #2E2E2E",
            color: "#FFFFFF",
            outline: "none",
          }}
        >
          <option value="">All regions</option>
          {regionsList.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          className="px-3 py-2 text-sm font-mono"
          style={{
            backgroundColor: "#1A1A1A",
            border: "1px solid #2E2E2E",
            color: "#FFFFFF",
            outline: "none",
          }}
        >
          <option value="">All sources</option>
          {sourcesList.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <p
        className="text-xs font-mono mb-3"
        style={{ color: "#B8B9B6" }}
      >
        {filtered.length} {filtered.length === 1 ? "action" : "actions"} shown
      </p>

      {/* List */}
      {filtered.length === 0 ? (
        <div
          className="p-8 text-center font-mono text-sm"
          style={{
            backgroundColor: "#1A1A1A",
            border: "1px solid #2E2E2E",
            color: "#B8B9B6",
          }}
        >
          No citizen actions match your filters.
        </div>
      ) : (
        <div className="flex flex-col">
          {filtered.map((e) => (
            <Link
              key={e.id}
              href={`/event/${e.id}`}
              className="block p-4 hover:opacity-90"
              style={{
                backgroundColor: "#1A1A1A",
                border: "1px solid #2E2E2E",
                borderLeft: "3px solid #B6FFCE",
                marginBottom: 8,
                transition: "background-color 120ms",
              }}
            >
              <div className="flex items-center gap-3 mb-2 text-xs font-mono">
                <span
                  className="font-bold uppercase tracking-wider"
                  style={{ color: "#B6FFCE" }}
                >
                  BURN
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
                <span style={{ color: "#666" }}>{formatDate(e.created_at)}</span>
                {e.burn_subtype === "editorial_consciousness" && (
                  <span
                    className="px-2 py-0.5 text-[10px] uppercase tracking-wider"
                    style={{
                      backgroundColor: "var(--brand-teal-dim, #02343a)",
                      color: "var(--brand-teal, #0190A0)",
                      marginLeft: 8,
                    }}
                  >
                    EDITORIAL
                  </span>
                )}
              </div>
              <p className="text-sm leading-snug" style={{ color: "#FFFFFF" }}>
                {e.event_title}
              </p>
              {e._themes.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {e._themes.map((t) => (
                    <ThemeBadge key={t} themeId={t} />
                  ))}
                </div>
              )}
              {e.justification && (
                <p
                  className="text-xs leading-relaxed mt-2 font-mono"
                  style={{ color: "#B8B9B6" }}
                >
                  {e.justification.length > 220
                    ? e.justification.slice(0, 220) + "…"
                    : e.justification}
                </p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
