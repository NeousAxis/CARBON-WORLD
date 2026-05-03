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

/**
 * Search + region/source filter on top of the server-rendered citizen-actions
 * list. Pure client interaction — no extra fetch, the parent page already
 * pre-filtered the data.
 */
export function CitizenActionsClient({ events }: CitizenActionsClientProps) {
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState<string>("");
  const [source, setSource] = useState<string>("");

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

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return events.filter((e) => {
      if (region && e.region !== region) return false;
      if (source && e.event_source !== source) return false;
      if (q) {
        const hay = `${e.event_title ?? ""} ${e.justification ?? ""} ${
          e.event_source ?? ""
        } ${e.country ?? ""}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [events, query, region, source]);

  return (
    <div>
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
