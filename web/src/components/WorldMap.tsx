"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
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

// Reverse mapping: ISO-2 → canonical event country name (the one stored in
// `event.country` by the analyst LLM). When the same ISO has multiple
// aliases (e.g. "United States" vs "United States of America"), pick the
// shorter one — by convention that's the canonical short form used by the
// pipeline. This drives the /events?country=… drill-down so the filter
// hits actual event rows.
const ISO_TO_CANONICAL: Record<string, string> = (() => {
  const out: Record<string, string> = {};
  for (const [name, iso] of Object.entries(NAME_TO_ISO)) {
    if (!out[iso] || name.length < out[iso].length) out[iso] = name;
  }
  return out;
})();

interface WorldCountry {
  id: string;
  name: string;
  d: string;
}

/**
 * Compute the visual centroid of an SVG path by averaging every coordinate
 * pair found in its `d` string. Cheap and good enough for placing a marker:
 * for a country whose path traces its outline, the average of all outline
 * points lands inside the country roughly at its visual centre. Much better
 * than the previous "first M command" shortcut which placed the marker at
 * an arbitrary corner (Russia → Siberia, US → Maine).
 */
function pathCentroid(d: string): { cx: number; cy: number } | null {
  const numRe = /-?\d+(?:\.\d+)?/g;
  const nums = d.match(numRe);
  if (!nums || nums.length < 2) return null;
  let sx = 0;
  let sy = 0;
  let count = 0;
  for (let i = 0; i + 1 < nums.length; i += 2) {
    const x = parseFloat(nums[i]);
    const y = parseFloat(nums[i + 1]);
    if (Number.isFinite(x) && Number.isFinite(y)) {
      sx += x;
      sy += y;
      count++;
    }
  }
  if (count === 0) return null;
  return { cx: sx / count, cy: sy / count };
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
  const router = useRouter();
  const [countries, setCountries] = useState<WorldCountry[] | null>(null);
  const [hoverIso, setHoverIso] = useState<string | null>(null);
  const [hoverName, setHoverName] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number } | null>(null);
  // Track press start so we don't navigate when the user is panning
  const pressStart = useRef<{ x: number; y: number } | null>(null);

  // Pan + zoom state — operates on the SVG viewBox so the geometry stays crisp
  const W = 1000;
  const VIEW_H = 420;
  const VIEW_Y = 30;
  const [view, setView] = useState({ x: 0, y: VIEW_Y, w: W, h: VIEW_H });
  const isDragging = useRef(false);
  const dragStart = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

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

  // Wheel zoom centred on the cursor position. Stops the page from scrolling.
  function handleWheel(e: React.WheelEvent<SVGSVGElement>) {
    e.preventDefault();
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    // Map cursor to viewBox coordinates
    const px = (e.clientX - rect.left) / rect.width;
    const py = (e.clientY - rect.top) / rect.height;
    const cx = view.x + px * view.w;
    const cy = view.y + py * view.h;
    const factor = e.deltaY > 0 ? 1.2 : 1 / 1.2;
    let newW = Math.min(W, Math.max(150, view.w * factor));
    let newH = Math.min(VIEW_H, Math.max(150 * (VIEW_H / W), view.h * factor));
    // Keep aspect ratio aligned with the original viewBox
    const aspect = W / VIEW_H;
    if (newW / newH > aspect) newW = newH * aspect;
    else newH = newW / aspect;
    let newX = cx - px * newW;
    let newY = cy - py * newH;
    // Clamp inside the original world bounds
    newX = Math.max(0, Math.min(W - newW, newX));
    newY = Math.max(VIEW_Y, Math.min(VIEW_Y + VIEW_H - newH, newY));
    setView({ x: newX, y: newY, w: newW, h: newH });
  }

  function handleMouseDown(e: React.MouseEvent<SVGSVGElement>) {
    isDragging.current = true;
    dragStart.current = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y };
    pressStart.current = { x: e.clientX, y: e.clientY };
  }
  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    setTooltip({ x: e.clientX, y: e.clientY });
    if (!isDragging.current || !dragStart.current) return;
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const dxPx = e.clientX - dragStart.current.x;
    const dyPx = e.clientY - dragStart.current.y;
    // Convert pixel delta to viewBox delta
    const dx = (dxPx / rect.width) * view.w;
    const dy = (dyPx / rect.height) * view.h;
    let newX = dragStart.current.vx - dx;
    let newY = dragStart.current.vy - dy;
    newX = Math.max(0, Math.min(W - view.w, newX));
    newY = Math.max(VIEW_Y, Math.min(VIEW_Y + VIEW_H - view.h, newY));
    setView((v) => ({ ...v, x: newX, y: newY }));
  }
  function handleMouseUp() {
    isDragging.current = false;
    dragStart.current = null;
  }
  function resetZoom() {
    setView({ x: 0, y: VIEW_Y, w: W, h: VIEW_H });
  }

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

  const activeCount = Object.keys(countryStats).length;
  const isZoomed = view.w !== W || view.h !== VIEW_H || view.x !== 0 || view.y !== VIEW_Y;

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
        <div className="flex items-center gap-3">
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
          {isZoomed && (
            <button
              onClick={resetZoom}
              className="text-[10px] font-mono uppercase tracking-wider px-2 py-1"
              style={{
                color: "var(--muted)",
                border: "1px solid var(--border)",
                background: "transparent",
                cursor: "pointer",
              }}
            >
              RESET ZOOM
            </button>
          )}
        </div>
      </div>

      {/* SVG world map — wheel-zoom + drag-pan */}
      <svg
        ref={svgRef}
        width="100%"
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        preserveAspectRatio="xMidYMid meet"
        style={{
          display: "block",
          height,
          background: "#1A1A1A",
          cursor: isDragging.current ? "grabbing" : "grab",
          touchAction: "none",
        }}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => {
          handleMouseUp();
          setTooltip(null);
        }}
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
        <rect x="0" y={VIEW_Y} width={W} height={VIEW_H} fill="url(#wm-grid)" />

        {/* Country paths */}
        {countries?.map((c) => {
          const iso = NAME_TO_ISO[c.name];
          const focused = !!c.name && hoverName === c.name;
          const hasStats = !!iso && !!countryStats[iso];
          return (
            <path
              key={c.id}
              d={c.d}
              fill={colorFor(iso)}
              stroke={focused ? "#F5F5F5" : "#3A3A3A"}
              strokeWidth={focused ? 1.2 : 0.4}
              style={{
                transition: "fill 400ms linear",
                cursor: hasStats ? "pointer" : "default",
              }}
              onMouseEnter={() => {
                setHoverName(c.name);
                if (iso) setHoverIso(iso);
              }}
              onMouseLeave={() => {
                setHoverName(null);
                setHoverIso(null);
              }}
              onClick={(e) => {
                // Suppress navigation if the user actually panned (drag)
                // — measured by movement between mousedown and mouseup.
                if (pressStart.current) {
                  const dx = e.clientX - pressStart.current.x;
                  const dy = e.clientY - pressStart.current.y;
                  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) return;
                }
                if (!iso || !hasStats) return;
                const canonical = ISO_TO_CANONICAL[iso] ?? c.name;
                router.push(
                  `/events?country=${encodeURIComponent(canonical)}&since=${windowDays}d`,
                );
              }}
            />
          );
        })}

        {/* Pulse rings on active countries — placed at the visual centroid
            of the country path (average of all coordinates), not at the
            first M command which gives an arbitrary corner. */}
        {countries &&
          Object.entries(countryStats).map(([iso, s]) => {
            const country = countries.find((c) => NAME_TO_ISO[c.name] === iso);
            if (!country) return null;
            const ctr = pathCentroid(country.d);
            if (!ctr) return null;
            const { cx, cy } = ctr;
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

      {/* Floating tooltip — country name + stats, follows the cursor.
          The pulse ring on each active country is centred on the country's
          visual centroid (NOT a city or region — there is no sub-national
          data in the pipeline). */}
      {hoverName && tooltip && (
        <div
          style={{
            position: "fixed",
            left: tooltip.x + 14,
            top: tooltip.y + 14,
            pointerEvents: "none",
            zIndex: 50,
            background: "#0a0a0a",
            border: "1px solid #2E2E2E",
            padding: "6px 10px",
            fontFamily: "var(--font-mono, monospace)",
            fontSize: 11,
            lineHeight: 1.4,
            color: "#E5E5E5",
            whiteSpace: "nowrap",
          }}
        >
          <div
            className="uppercase tracking-wider"
            style={{ fontSize: 9, color: "#6E6F6C", marginBottom: 2 }}
          >
            COUNTRY
          </div>
          <div style={{ fontWeight: 600, color: "#F5F5F5" }}>{hoverName}</div>
          {hoverIso && countryStats[hoverIso] ? (
            <div style={{ color: "#B8B9B6", marginTop: 4 }}>
              <span style={{ color: "#FF5C33" }}>
                +{countryStats[hoverIso].mint}K MINT
              </span>
              <span style={{ color: "#666", margin: "0 6px" }}>·</span>
              <span style={{ color: "#B6FFCE" }}>
                -{countryStats[hoverIso].burn}K BURN
              </span>
              <span style={{ color: "#666", margin: "0 6px" }}>·</span>
              <span>{countryStats[hoverIso].count} events</span>
            </div>
          ) : (
            <div style={{ color: "#6E6F6C", marginTop: 4 }}>
              No activity in this window
            </div>
          )}
        </div>
      )}

      {/* Footer legend + zoom hint */}
      <div
        className="grid grid-cols-4 text-xs"
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
        <div
          className="flex items-center gap-2 px-3 py-2"
          style={{ borderRight: "1px solid var(--border)" }}
        >
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
        <div className="flex items-center gap-2 px-3 py-2 justify-end">
          <span
            className="font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)", fontSize: 10 }}
          >
            SCROLL TO ZOOM · DRAG TO PAN
          </span>
        </div>
      </div>
    </div>
  );
}
