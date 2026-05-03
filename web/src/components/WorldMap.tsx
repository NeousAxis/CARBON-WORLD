"use client";

import { useEffect, useMemo, useState } from "react";
import type { CarbonEvent } from "@/lib/types";

/**
 * WorldMap — choropleth + pulse rings showing where decisions land
 * geographically over the last 7 days.
 *
 * Render strategy (no leaflet, no d3-geo, no extra deps):
 *   - Static SVG paths for ~177 countries shipped as
 *     /public/world-countries.json (Equirectangular projection,
 *     viewBox 0 0 1000 500, generated upstream and copied verbatim from
 *     the dashboard mockup at /dashboard-v2/world-countries.json).
 *   - The component fetches the JSON on mount; until it lands, only the
 *     header + footer render so the card never renders blank-of-empty.
 *   - Country fill is interpolated between MINT (orange) and BURN (green)
 *     depending on which dominates for that country's events; intensity
 *     is normalised against the busiest country so a quiet day still
 *     produces visible variation.
 *   - A pulse ring is drawn on top of each active country (centroid
 *     extracted from the first M command in the path d-string — cheap
 *     and good-enough for a visual cue).
 *
 * Data source: same `events` array the rest of the dashboard receives,
 * filtered to the 7-day window for consistency with the other indicators.
 */

// Country canonical name (matches event.country) → ISO-2 used as map key.
// Same dictionary as the dashboard-v2 mockup. Anything not in this list
// will simply not be lit up — the path still renders neutral grey.
const NAME_TO_ISO: Record<string, string> = {
  "France": "FR", "Germany": "DE", "Spain": "ES", "Italy": "IT",
  "Portugal": "PT", "United Kingdom": "GB", "Norway": "NO", "Sweden": "SE",
  "Finland": "FI", "Belgium": "BE", "Netherlands": "NL", "Poland": "PL",
  "Greece": "GR", "Russia": "RU", "Ukraine": "UA", "Turkey": "TR",
  "United States": "US", "United States of America": "US", "Canada": "CA",
  "Mexico": "MX", "Brazil": "BR", "Argentina": "AR", "Colombia": "CO",
  "Chile": "CL", "Peru": "PE", "Venezuela": "VE", "Cuba": "CU",
  "Ecuador": "EC", "Bolivia": "BO", "Paraguay": "PY", "Uruguay": "UY",
  "Costa Rica": "CR", "Guatemala": "GT", "Honduras": "HN", "Panama": "PA",
  "India": "IN", "China": "CN", "Japan": "JP", "South Korea": "KR",
  "Indonesia": "ID", "Vietnam": "VN", "Thailand": "TH", "Philippines": "PH",
  "Malaysia": "MY", "Pakistan": "PK", "Bangladesh": "BD", "Sri Lanka": "LK",
  "Australia": "AU", "New Zealand": "NZ",
  "Egypt": "EG", "South Africa": "ZA", "Kenya": "KE", "Nigeria": "NG",
  "Ethiopia": "ET", "Morocco": "MA", "Algeria": "DZ", "Tunisia": "TN",
  "Libya": "LY", "Sudan": "SD", "Tanzania": "TZ", "Uganda": "UG",
  "Ghana": "GH", "Senegal": "SN", "Mali": "ML", "Somalia": "SO",
  "Saudi Arabia": "SA", "Iran": "IR", "Iraq": "IQ", "Israel": "IL",
  "Syria": "SY", "Lebanon": "LB", "Jordan": "JO", "Yemen": "YE",
  "United Arab Emirates": "AE", "Qatar": "QA", "Kuwait": "KW",
  "Afghanistan": "AF", "Kazakhstan": "KZ", "Uzbekistan": "UZ",
};

interface WorldCountry {
  id: string;
  name: string;
  d: string;
}

interface CountryStat {
  mint: number;
  burn: number;
  count: number;
}

interface WorldMapProps {
  events: CarbonEvent[];
  /** Visible window in days. Default: 7. */
  windowDays?: number;
  /** Card height. Default 440. */
  height?: number;
}

export function WorldMap({ events, windowDays = 7, height = 440 }: WorldMapProps) {
  const [countries, setCountries] = useState<WorldCountry[] | null>(null);
  const [hoverIso, setHoverIso] = useState<string | null>(null);

  // Lazy-load the geometry — 165 KB JSON, fetched once and cached by the browser
  useEffect(() => {
    let cancelled = false;
    fetch("/world-countries.json")
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) setCountries(data as WorldCountry[]);
      })
      .catch((err) => {
        // eslint-disable-next-line no-console
        console.warn("[WorldMap] failed to load world-countries.json:", err);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Aggregate events per ISO over the chosen window
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

  // Color scale: intensity = total / max(total)
  const max = Math.max(
    1,
    ...Object.values(countryStats).map((s) => s.mint + s.burn),
  );

  function colorFor(iso: string | undefined): string {
    if (!iso) return "#222";
    const s = countryStats[iso];
    if (!s || s.mint + s.burn === 0) return "#222";
    const intensity = Math.min(1, (s.mint + s.burn) / max);
    const dominant = s.mint > s.burn ? "mint" : "burn";
    // mint = orange, burn = green
    const base = dominant === "mint" ? [255, 132, 0] : [182, 255, 206];
    const factor = 0.35 + intensity * 0.65;
    const r = Math.round(base[0] * factor);
    const g = Math.round(base[1] * factor);
    const b = Math.round(base[2] * factor);
    return `rgb(${r},${g},${b})`;
  }

  // Crop to drop most of antarctica
  const W = 1000;
  const viewH = 420;
  const viewY = 30;

  const activeCount = Object.keys(countryStats).length;

  return (
    <div
      style={{
        backgroundColor: "var(--card-bg)",
        border: "1px solid var(--border)",
      }}
      className="relative"
    >
      {/* Title bar */}
      <div
        className="px-4 py-3 flex items-center justify-between"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div>
          <p
            className="text-xs uppercase tracking-wider font-mono"
            style={{ color: "var(--brand-teal)" }}
          >
            VERDICTS WORLDWIDE · {windowDays}D
          </p>
          <p
            className="text-[10px] font-mono mt-0.5"
            style={{ color: "var(--muted)" }}
          >
            {activeCount} {activeCount === 1 ? "country" : "countries"} active
          </p>
        </div>
        {hoverIso && countryStats[hoverIso] && (
          <div className="text-xs font-mono" style={{ color: "var(--muted)" }}>
            <span style={{ color: "var(--foreground)" }}>{hoverIso}</span>
            <span style={{ color: "#FF5C33", marginLeft: 8 }}>
              +{countryStats[hoverIso].mint}K
            </span>
            <span style={{ color: "var(--muted)", margin: "0 4px" }}>/</span>
            <span style={{ color: "#B6FFCE" }}>
              -{countryStats[hoverIso].burn}K
            </span>
          </div>
        )}
      </div>

      {/* SVG world map */}
      <svg
        width="100%"
        viewBox={`0 ${viewY} ${W} ${viewH}`}
        preserveAspectRatio="xMidYMid meet"
        style={{ display: "block", height, background: "#1A1A1A" }}
      >
        <defs>
          <pattern
            id="wm-grid"
            x="0"
            y="0"
            width="20"
            height="20"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M20 0H0V20"
              stroke="#2E2E2E"
              strokeWidth="0.5"
              fill="none"
              opacity="0.4"
            />
          </pattern>
        </defs>
        <rect x="0" y={viewY} width={W} height={viewH} fill="url(#wm-grid)" />

        {/* Country paths */}
        {countries?.map((c) => {
          const iso = NAME_TO_ISO[c.name];
          const focused = iso !== undefined && hoverIso === iso;
          return (
            <path
              key={c.id}
              d={c.d}
              fill={colorFor(iso)}
              stroke={focused ? "#F5F5F5" : "#3A3A3A"}
              strokeWidth={focused ? 1.2 : 0.4}
              style={{
                cursor: iso ? "pointer" : "default",
                transition: "fill 400ms linear",
              }}
              onMouseEnter={() => iso && setHoverIso(iso)}
              onMouseLeave={() => setHoverIso(null)}
            />
          );
        })}

        {/* Pulse rings on active countries */}
        {countries &&
          Object.entries(countryStats).map(([iso, s]) => {
            const country = countries.find((c) => NAME_TO_ISO[c.name] === iso);
            if (!country) return null;
            const m = country.d.match(/M([\d.\-]+),([\d.\-]+)/);
            if (!m) return null;
            const cx = parseFloat(m[1]);
            const cy = parseFloat(m[2]);
            const dom = s.mint > s.burn ? "#FF5C33" : "#B6FFCE";
            const size = Math.min(8, 3 + (s.mint + s.burn) / 30);
            return (
              <g key={iso} pointerEvents="none">
                <circle cx={cx} cy={cy} r={size} fill={dom} opacity="0.9" />
                <circle
                  cx={cx}
                  cy={cy}
                  r={size}
                  fill="none"
                  stroke={dom}
                  strokeWidth="1"
                >
                  <animate
                    attributeName="r"
                    values={`${size};${size * 3};${size}`}
                    dur="2.2s"
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="opacity"
                    values="0.7;0;0.7"
                    dur="2.2s"
                    repeatCount="indefinite"
                  />
                </circle>
              </g>
            );
          })}
      </svg>

      {/* Footer legend */}
      <div
        className="grid grid-cols-3 text-xs"
        style={{ borderTop: "1px solid var(--border)" }}
      >
        <div
          className="flex items-center gap-2 px-3 py-2"
          style={{ borderRight: "1px solid var(--border)" }}
        >
          <span
            style={{
              width: 10,
              height: 10,
              backgroundColor: "#FF5C33",
              display: "inline-block",
            }}
          />
          <span
            className="font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)", fontSize: 10 }}
          >
            MINT-DOMINANT
          </span>
        </div>
        <div
          className="flex items-center gap-2 px-3 py-2"
          style={{ borderRight: "1px solid var(--border)" }}
        >
          <span
            style={{
              width: 10,
              height: 10,
              backgroundColor: "#B6FFCE",
              display: "inline-block",
            }}
          />
          <span
            className="font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)", fontSize: 10 }}
          >
            BURN-DOMINANT
          </span>
        </div>
        <div className="flex items-center gap-2 px-3 py-2">
          <span
            style={{
              width: 10,
              height: 10,
              backgroundColor: "#222",
              display: "inline-block",
            }}
          />
          <span
            className="font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)", fontSize: 10 }}
          >
            INACTIVE
          </span>
        </div>
      </div>
    </div>
  );
}
