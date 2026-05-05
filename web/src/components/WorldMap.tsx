"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import type { CarbonEvent } from "@/lib/types";

/**
 * WorldMap — hexagonal dot-map base + pulse markers per active country.
 *
 * Visual base : /public/world-hex-map.svg (Figma community asset, 2,216
 * decorative hexagons, viewBox 0 0 1440 974).
 * Functional layer : pulse rings at the projected lat/lon of each
 * country that has on-chain events in the chosen window. Clicking a ring
 * navigates to /events?country=<X>&since=<windowDays>d. Hover shows a
 * tooltip with the country name and BURN/MINT counts.
 *
 * Projection : approximate equirectangular within an empirically-
 * calibrated world bounding box inside the SVG viewBox.
 */

// Country canonical name (matches event.country) → ISO-2.
// Same dictionary as before — keep in sync with the worker tagger.
const NAME_TO_ISO: Record<string, string> = {
  "France": "FR", "Germany": "DE", "Spain": "ES", "Italy": "IT",
  "Portugal": "PT", "United Kingdom": "GB", "Norway": "NO", "Sweden": "SE",
  "Finland": "FI", "Belgium": "BE", "Netherlands": "NL", "Poland": "PL",
  "Greece": "GR", "Russia": "RU", "Ukraine": "UA", "Turkey": "TR",
  "Switzerland": "CH", "Austria": "AT", "Denmark": "DK", "Ireland": "IE",
  "Czech Republic": "CZ", "Hungary": "HU", "Romania": "RO",
  "United States": "US", "United States of America": "US", "Canada": "CA",
  "Mexico": "MX", "Brazil": "BR", "Argentina": "AR", "Colombia": "CO",
  "Chile": "CL", "Peru": "PE", "Venezuela": "VE", "Cuba": "CU",
  "Ecuador": "EC", "Bolivia": "BO", "Paraguay": "PY", "Uruguay": "UY",
  "Costa Rica": "CR", "Guatemala": "GT", "Honduras": "HN", "Panama": "PA",
  "India": "IN", "China": "CN", "Japan": "JP", "South Korea": "KR",
  "North Korea": "KP",
  "Indonesia": "ID", "Vietnam": "VN", "Thailand": "TH", "Philippines": "PH",
  "Malaysia": "MY", "Pakistan": "PK", "Bangladesh": "BD", "Sri Lanka": "LK",
  "Singapore": "SG",
  "Australia": "AU", "New Zealand": "NZ",
  "Egypt": "EG", "South Africa": "ZA", "Kenya": "KE", "Nigeria": "NG",
  "Ethiopia": "ET", "Morocco": "MA", "Algeria": "DZ", "Tunisia": "TN",
  "Libya": "LY", "Sudan": "SD", "Tanzania": "TZ", "Uganda": "UG",
  "Ghana": "GH", "Senegal": "SN", "Mali": "ML", "Somalia": "SO",
  "Zimbabwe": "ZW",
  "Saudi Arabia": "SA", "Iran": "IR", "Iraq": "IQ", "Israel": "IL",
  "Palestine": "PS",
  "Syria": "SY", "Lebanon": "LB", "Jordan": "JO", "Yemen": "YE",
  "United Arab Emirates": "AE", "Qatar": "QA", "Kuwait": "KW",
  "Afghanistan": "AF", "Kazakhstan": "KZ", "Uzbekistan": "UZ",
};

// Reverse map: ISO → canonical event-country name (shorter alias wins).
const ISO_TO_CANONICAL: Record<string, string> = (() => {
  const out: Record<string, string> = {};
  for (const [name, iso] of Object.entries(NAME_TO_ISO)) {
    if (!out[iso] || name.length < out[iso].length) out[iso] = name;
  }
  return out;
})();

// Approximate country centroid in lat/lon (capital city or geographic center).
const ISO_LATLON: Record<string, [number, number]> = {
  // Europe
  FR: [46.6, 2.2], DE: [51.2, 10.4], ES: [40.5, -3.7], IT: [42.8, 12.6],
  PT: [39.4, -8.0], GB: [53.0, -2.0], NO: [62.0, 9.0], SE: [60.5, 16.0],
  FI: [64.5, 26.0], BE: [50.7, 4.5], NL: [52.2, 5.3], PL: [52.0, 19.5],
  GR: [39.0, 22.0], RU: [60.0, 90.0], UA: [49.0, 32.0], TR: [39.0, 35.0],
  CH: [46.8, 8.2], AT: [47.5, 14.5], DK: [56.0, 9.5], IE: [53.4, -8.0],
  CZ: [49.8, 15.5], HU: [47.2, 19.5], RO: [45.9, 24.9],
  // North America
  US: [39.0, -98.0], CA: [60.0, -106.0], MX: [23.6, -102.5],
  // Latin America
  BR: [-10.5, -55.5], AR: [-38.0, -65.0], CO: [4.6, -74.0], CL: [-35.5, -71.5],
  PE: [-9.0, -76.0], VE: [8.0, -66.0], CU: [21.5, -78.0], EC: [-1.5, -78.0],
  BO: [-16.5, -65.0], PY: [-23.4, -58.5], UY: [-32.5, -55.5],
  CR: [9.7, -84.0], GT: [15.8, -90.5], HN: [15.0, -86.5], PA: [9.0, -80.0],
  // Asia
  IN: [22.0, 78.0], CN: [35.0, 105.0], JP: [36.5, 138.0], KR: [36.5, 127.5],
  KP: [40.0, 127.0], ID: [-2.0, 118.0], VN: [16.0, 107.0], TH: [15.0, 100.5],
  PH: [13.0, 122.0], MY: [4.0, 102.0], PK: [30.0, 70.0], BD: [23.7, 90.4],
  LK: [7.0, 81.0], SG: [1.3, 103.8],
  // Oceania
  AU: [-25.0, 134.0], NZ: [-41.0, 172.0],
  // MENA / Middle East
  SA: [24.0, 45.0], IR: [32.0, 53.0], IQ: [33.0, 44.0], IL: [31.0, 35.0],
  PS: [31.9, 35.2], SY: [35.0, 38.0], LB: [33.9, 35.9], JO: [31.0, 36.5],
  YE: [15.5, 48.0], AE: [24.0, 54.0], QA: [25.3, 51.2], KW: [29.3, 47.5],
  EG: [27.0, 30.0], MA: [31.8, -7.0], DZ: [28.0, 1.7], TN: [33.9, 9.5],
  LY: [27.0, 17.0],
  // Africa
  ZA: [-29.0, 24.0], KE: [-1.0, 38.0], NG: [9.5, 8.0], ET: [9.0, 38.0],
  TZ: [-6.4, 35.0], UG: [1.4, 32.5], GH: [7.6, -1.0], SN: [14.5, -14.5],
  ML: [17.0, -4.0], SO: [5.5, 46.0], SD: [12.0, 30.0], ZW: [-19.0, 29.0],
  // Central Asia
  AF: [33.5, 65.0], KZ: [48.0, 68.0], UZ: [41.0, 64.0],
};

// Hex SVG calibration — eyeballed from the rendered preview at 1440×974.
const VB_W = 1440;
const VB_H = 974;
const WORLD_LEFT = 60;
const WORLD_RIGHT = 1380;
const WORLD_TOP = 80;
const WORLD_BOTTOM = 850;

function project(lat: number, lon: number): { x: number; y: number } {
  const x = ((lon + 180) / 360) * (WORLD_RIGHT - WORLD_LEFT) + WORLD_LEFT;
  const y = ((90 - lat) / 180) * (WORLD_BOTTOM - WORLD_TOP) + WORLD_TOP;
  return { x, y };
}

interface WorldMapProps {
  events: CarbonEvent[];
  windowDays?: number;
  /** Maximum card height in pixels — clamps via CSS for mobile. */
  height?: number;
}

interface CountryStat {
  mint: number;
  burn: number;
  count: number;
}

export function WorldMap({ events, windowDays = 7, height = 460 }: WorldMapProps) {
  const router = useRouter();
  const [hoverIso, setHoverIso] = useState<string | null>(null);

  // Aggregate events by ISO over the chosen time window
  const countryStats = useMemo<Record<string, CountryStat>>(() => {
    const cutoff = Date.now() - windowDays * 24 * 60 * 60 * 1000;
    const stats: Record<string, CountryStat> = {};
    for (const e of events) {
      if (!e.country) continue;
      const iso = NAME_TO_ISO[e.country];
      if (!iso) continue;
      const ts = new Date(e.created_at).getTime();
      if (ts < cutoff) continue;
      if (!stats[iso]) stats[iso] = { mint: 0, burn: 0, count: 0 };
      const amount = Math.max(0, Math.round((e.amount_crbn || 0) / 1000));
      if (e.decision === "MINT") stats[iso].mint += amount;
      if (e.decision === "BURN") stats[iso].burn += amount;
      stats[iso].count += 1;
    }
    return stats;
  }, [events, windowDays]);

  // Marker size scales with event count (capped to keep the map readable)
  const maxCount = Math.max(1, ...Object.values(countryStats).map((s) => s.count));
  function radiusFor(s: CountryStat): number {
    // 6 to 18 px, square-root scaling for visual balance
    const t = Math.min(1, Math.sqrt(s.count) / Math.sqrt(Math.max(1, maxCount)));
    return 6 + 12 * t;
  }

  const activeCount = Object.keys(countryStats).length;

  return (
    <div
      style={{
        backgroundColor: "var(--card-bg)",
        border: "1px solid var(--border)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center gap-3 flex-wrap"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <span
          className="font-mono text-xs uppercase tracking-wider"
          style={{ color: "var(--muted)" }}
        >
          WORLD MAP · {windowDays}D
        </span>
        <span
          className="font-mono text-[10px] uppercase tracking-wider"
          style={{ color: "var(--muted)" }}
        >
          {activeCount} {activeCount === 1 ? "country" : "countries"} active
        </span>
        <div className="flex items-center gap-3 ml-auto text-[10px] font-mono">
          <span style={{ color: "#FF5C33" }}>● MINT</span>
          <span style={{ color: "#B6FFCE" }}>● BURN</span>
        </div>
      </div>

      {/* Map */}
      <svg
        viewBox={`0 0 ${VB_W} ${VB_H}`}
        preserveAspectRatio="xMidYMid meet"
        width="100%"
        style={{
          display: "block",
          height: `clamp(220px, 50vw, ${height}px)`,
          // Match Lunaris card bg so the recolored hex grid blends seamlessly.
          background: "var(--card-bg, #1A1A1A)",
        }}
      >
        {/* Layer 1 — decorative hex grid (Figma asset) */}
        <image href="/world-hex-map.svg" x="0" y="0" width={VB_W} height={VB_H} />

        {/* Layer 2 — pulse markers per active country */}
        {Object.entries(countryStats).map(([iso, s]) => {
          const latlon = ISO_LATLON[iso];
          if (!latlon) return null;
          const { x, y } = project(latlon[0], latlon[1]);
          const dom = s.mint > s.burn ? "#FF5C33" : "#B6FFCE";
          const r = radiusFor(s);
          const focused = hoverIso === iso;
          const canonical = ISO_TO_CANONICAL[iso] ?? iso;

          return (
            <g
              key={iso}
              style={{ cursor: "pointer" }}
              onMouseEnter={() => setHoverIso(iso)}
              onMouseLeave={() => setHoverIso(null)}
              onClick={() =>
                router.push(
                  `/events?country=${encodeURIComponent(canonical)}&since=${windowDays}d`,
                )
              }
            >
              {/* Soft halo */}
              <circle
                cx={x}
                cy={y}
                r={r * 1.9}
                fill={dom}
                opacity={focused ? 0.25 : 0.15}
              />
              {/* Outer ring */}
              <circle
                cx={x}
                cy={y}
                r={r}
                fill="none"
                stroke={dom}
                strokeWidth={focused ? 2.5 : 1.5}
                opacity="0.85"
              />
              {/* Inner dot */}
              <circle cx={x} cy={y} r={r * 0.45} fill={dom} />
              {/* Larger transparent hit zone for easier click on mobile */}
              <circle
                cx={x}
                cy={y}
                r={Math.max(r * 1.6, 14)}
                fill="transparent"
              />
            </g>
          );
        })}
      </svg>

      {/* Floating tooltip — country name + stats */}
      {hoverIso && countryStats[hoverIso] && (
        <div
          style={{
            position: "absolute",
            top: 16,
            right: 16,
            zIndex: 10,
            padding: "8px 12px",
            backgroundColor: "rgba(15, 20, 19, 0.95)",
            border: "1px solid var(--border)",
            color: "var(--foreground)",
            fontSize: 11,
            fontFamily: "ui-monospace, monospace",
            pointerEvents: "none",
            whiteSpace: "nowrap",
          }}
        >
          <div
            style={{
              fontWeight: 700,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              marginBottom: 4,
            }}
          >
            {ISO_TO_CANONICAL[hoverIso] ?? hoverIso}
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <span style={{ color: "#FF5C33" }}>
              +{countryStats[hoverIso].mint}K MINT
            </span>
            <span style={{ color: "#B6FFCE" }}>
              -{countryStats[hoverIso].burn}K BURN
            </span>
          </div>
          <div style={{ color: "var(--muted)", marginTop: 4 }}>
            {countryStats[hoverIso].count}{" "}
            {countryStats[hoverIso].count === 1 ? "event" : "events"} · click to drill down
          </div>
        </div>
      )}

    </div>
  );
}
