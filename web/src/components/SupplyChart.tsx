"use client";

import { useState } from "react";
import type { CarbonEvent } from "@/lib/types";

// Calibrated display amount (magnitude-driven, symmetric BURN/MINT). Falls back
// to the raw on-chain amount for older exports lacking amount_index.
const idxAmount = (e: CarbonEvent) => e.amount_index ?? e.amount_crbn;

const DAY_MS = 86_400_000;
const AVG_WINDOW_DAYS = 7;
const AVG_MIN_COVERAGE = 5;

interface DayPoint {
  dayMs: number;
  burn: number; // gross CBWD burned that day
  mint: number; // gross CBWD minted that day
  net: number; // burn - mint
  count: number;
  avg: number; // trailing 7-calendar-day average of net
  avgReady: boolean; // window has enough covered days to be meaningful
}

function formatCompact(raw: number): string {
  const abs = Math.abs(raw);
  const sign = raw >= 0 ? "+" : "-";
  const b = abs / 1_000_000_000;
  if (b >= 1) return `${sign}${b.toFixed(2).replace(/\.?0+$/, "")}B`;
  const m = abs / 1_000_000;
  if (m >= 1) return `${sign}${m.toFixed(1).replace(/\.0$/, "")}M`;
  const k = abs / 1_000;
  if (k >= 1) return `${sign}${k.toFixed(0)}K`;
  return `${sign}${abs.toFixed(0)}`;
}

function formatShortDate(ms: number): string {
  return new Date(ms).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

// Round up to a human number. Finer than the usual 1/2/5 ladder, otherwise the
// axis bound jumps far past the data and flattens every bar.
const NICE_STEPS = [1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10];
function niceCeil(v: number): number {
  if (v <= 0) return 0;
  const pow = Math.pow(10, Math.floor(Math.log10(v)));
  const f = v / pow;
  return (NICE_STEPS.find((s) => f <= s) ?? 10) * pow;
}

function percentile(values: number[], p: number): number {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.round(p * (sorted.length - 1)))];
}

export function SupplyChart({ events }: { events: CarbonEvent[] }) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const decided = events.filter(
    (e) => (e.decision === "BURN" || e.decision === "MINT") && e.created_at
  );

  if (decided.length === 0) {
    return (
      <div
        className="flex items-center justify-center h-[320px] text-sm"
        style={{
          backgroundColor: "#1A1A1A",
          border: "1px solid #2E2E2E",
          color: "#B8B9B6",
          boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
        }}
      >
        No events yet
      </div>
    );
  }

  // One column per calendar day. BURN and MINT are plotted as their own gross
  // volumes, up and down from the baseline. Plotting only the net hid the BURN
  // side completely: it is 32% of the events and present on most days.
  const byDay = new Map<string, DayPoint>();
  for (const e of decided) {
    const key = new Date(e.created_at).toISOString().slice(0, 10);
    let p = byDay.get(key);
    if (!p) {
      p = {
        dayMs: new Date(key + "T00:00:00Z").getTime(),
        burn: 0,
        mint: 0,
        net: 0,
        count: 0,
        avg: 0,
        avgReady: false,
      };
      byDay.set(key, p);
    }
    const amt = idxAmount(e);
    if (e.decision === "BURN") p.burn += amt;
    else p.mint += amt;
    p.count += 1;
  }
  const days = [...byDay.values()].sort((a, b) => a.dayMs - b.dayMs);
  for (const p of days) p.net = p.burn - p.mint;

  // Trailing 7-CALENDAR-day average of the net, suppressed when the window is
  // mostly a pipeline silence (it would otherwise ramp back towards zero).
  for (const p of days) {
    const from = p.dayMs - (AVG_WINDOW_DAYS - 1) * DAY_MS;
    let sum = 0;
    let covered = 0;
    for (const q of days) {
      if (q.dayMs > p.dayMs) break;
      if (q.dayMs >= from) {
        sum += q.net;
        covered += 1;
      }
    }
    p.avg = sum / AVG_WINDOW_DAYS;
    p.avgReady = covered >= AVG_MIN_COVERAGE;
  }

  const firstMs = days[0].dayMs;
  const lastMs = days[days.length - 1].dayMs;
  const spanMs = Math.max(DAY_MS, lastMs - firstMs);
  const calendarDays = Math.round(spanMs / DAY_MS) + 1;

  // Stretches of consecutive missing calendar days: real pipeline outages, so
  // they get labelled instead of looking like a rendering bug.
  const outages: { fromMs: number; toMs: number; days: number }[] = [];
  for (let i = 1; i < days.length; i++) {
    const missing = Math.round((days[i].dayMs - days[i - 1].dayMs) / DAY_MS) - 1;
    if (missing > 0) {
      outages.push({
        fromMs: days[i - 1].dayMs + DAY_MS / 2,
        toMs: days[i].dayMs - DAY_MS / 2,
        days: missing,
      });
    }
  }

  const totals = days.reduce(
    (acc, d) => ({ burn: acc.burn + d.burn, mint: acc.mint + d.mint }),
    { burn: 0, mint: 0 }
  );
  const last7 = days
    .filter((d) => d.dayMs >= lastMs - (AVG_WINDOW_DAYS - 1) * DAY_MS)
    .reduce((s, d) => s + d.net, 0);
  const headlineColor = last7 >= 0 ? "#B6FFCE" : "#FF5C33";

  // Chart dimensions
  const width = 900;
  const height = 320;
  const padding = { top: 26, right: 24, bottom: 38, left: 68 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // Linear, and CRITICALLY the same number of CBWD per pixel above and below
  // the baseline, otherwise comparing the two flows visually would be a lie.
  // Each side is only cropped at its own 97th percentile so that a couple of
  // freak days cannot flatten the other 90+. Cropped days are drawn full length
  // and flagged with an axis-break mark.
  const sideBound = (values: number[], floor: number) => {
    const positives = values.filter((v) => v > 0);
    if (!positives.length) return floor;
    return Math.max(floor, niceCeil(percentile(positives, 0.97) * 1.1));
  };
  const burnBound = sideBound(days.map((d) => d.burn), 1);
  const mintBound = sideBound(days.map((d) => d.mint), burnBound);
  const totalRange = burnBound + mintBound;
  const zeroY = padding.top + (burnBound / totalRange) * chartH;
  const chartBottom = padding.top + chartH;
  const pxPerToken = chartH / totalRange;
  const scaleY = (v: number) =>
    zeroY - Math.max(-mintBound, Math.min(burnBound, v)) * pxPerToken;

  const overBurn = days.filter((d) => d.burn > burnBound).length;
  const overMint = days.filter((d) => d.mint > mintBound).length;

  // One slot per calendar day, so a silent day simply has no column.
  const slot = chartW / Math.max(1, calendarDays - 1);
  const barW = Math.max(2, Math.min(10, slot - 1.6));

  // Y ticks, linear, same step on both sides so the shared scale is visible.
  const step = niceCeil(mintBound / 4);
  const yTicks = [0];
  for (let v = step; v <= mintBound + 1; v += step) yTicks.push(-v);
  for (let v = step; v <= burnBound + 1; v += step) yTicks.push(v);
  if (yTicks.length < 3) yTicks.push(burnBound);

  // Net average line, split on gaps and on stretches with too thin a window.
  const avgSegments: string[] = [];
  let run: DayPoint[] = [];
  const flush = () => {
    if (run.length > 1) {
      avgSegments.push(
        run
          .map(
            (d, i) =>
              `${i === 0 ? "M" : "L"} ${scaleX(d.dayMs).toFixed(1)} ${scaleY(d.avg).toFixed(1)}`
          )
          .join(" ")
      );
    }
    run = [];
  };
  function scaleX(dayMs: number) {
    return padding.left + ((dayMs - firstMs) / spanMs) * chartW;
  }
  days.forEach((d, i) => {
    const contiguous = i > 0 && d.dayMs - days[i - 1].dayMs === DAY_MS;
    if (!d.avgReady || !contiguous) flush();
    if (d.avgReady) run.push(d);
  });
  flush();

  // X labels: evenly spaced in TIME, not in bucket index.
  const xLabelCount = Math.min(6, days.length);
  const xLabels = Array.from({ length: xLabelCount }, (_, i) => {
    const ms = xLabelCount === 1 ? firstMs : firstMs + (i / (xLabelCount - 1)) * spanMs;
    return { ms, label: formatShortDate(ms) };
  });

  const handleMove = (evt: React.MouseEvent<SVGRectElement>) => {
    const box = evt.currentTarget.getBoundingClientRect();
    const x = ((evt.clientX - box.left) / box.width) * chartW + padding.left;
    let best = 0;
    let bestDist = Infinity;
    days.forEach((d, i) => {
      const dist = Math.abs(scaleX(d.dayMs) - x);
      if (dist < bestDist) {
        bestDist = dist;
        best = i;
      }
    });
    setHoveredIndex(best);
  };

  const mono = "'JetBrains Mono', ui-monospace, monospace";
  const breakMark = (x: number, y: number) => (
    <g stroke="#1A1A1A" strokeWidth="2">
      <line x1={x - 1} y1={y} x2={x + barW + 1} y2={y - 4} />
      <line x1={x - 1} y1={y + 4} x2={x + barW + 1} y2={y} />
    </g>
  );

  return (
    <div
      className="p-4"
      style={{
        backgroundColor: "#1A1A1A",
        border: "1px solid #2E2E2E",
        boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
      }}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 px-2">
        <span
          className="text-xs font-medium uppercase tracking-wider"
          style={{ color: "#B8B9B6" }}
        >
          Daily Burn vs Mint
        </span>
        <span
          className="text-sm font-mono font-semibold tabular-nums whitespace-nowrap"
          style={{ color: headlineColor }}
        >
          7D NET {formatCompact(last7)} CBWD
        </span>
      </div>

      <div
        className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 mb-3 px-2 text-[10px]"
        style={{ color: "#B8B9B6" }}
      >
        <span className="min-w-0" style={{ color: "#0190A0" }}>
          {formatShortDate(firstMs)} → {formatShortDate(lastMs)} · one column = one day
        </span>
        <span className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
          <span style={{ color: "#B6FFCE" }}>
            ▲ burned {formatCompact(totals.burn).replace("+", "")}
          </span>
          <span style={{ color: "#FF5C33" }}>
            ▼ minted {formatCompact(totals.mint).replace("+", "")}
          </span>
          <span style={{ color: "#FF8400" }}>▬ 7d net</span>
          {outages.length > 0 && <span>▨ pipeline down</span>}
          {overBurn + overMint > 0 && <span>⇉ {overBurn + overMint} past the axis</span>}
        </span>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height: "320px" }}
        onMouseLeave={() => setHoveredIndex(null)}
      >
        <defs>
          <pattern
            id="supplychart-outage"
            width="6"
            height="6"
            patternUnits="userSpaceOnUse"
            patternTransform="rotate(45)"
          >
            <rect width="6" height="6" fill="#151515" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="#2E2E2E" strokeWidth="1.5" />
          </pattern>
        </defs>

        {/* Real outages: days where the pipeline produced nothing at all */}
        {outages.map((o) => {
          const x = scaleX(o.fromMs);
          const w = Math.max(2, scaleX(o.toMs) - x);
          return (
            <g key={`outage-${o.fromMs}`}>
              <rect
                x={x}
                y={padding.top}
                width={w}
                height={chartH}
                fill="url(#supplychart-outage)"
              />
              {w > 22 && (
                <text
                  x={x + w / 2}
                  y={padding.top + 12}
                  textAnchor="middle"
                  fontSize="8"
                  fill="#B8B9B6"
                  fontFamily={mono}
                >
                  {o.days}d
                </text>
              )}
            </g>
          );
        })}

        {/* Grid */}
        {yTicks.map((tick) => (
          <line
            key={`grid-${tick}`}
            x1={padding.left}
            y1={scaleY(tick)}
            x2={width - padding.right}
            y2={scaleY(tick)}
            stroke="#2E2E2E"
            strokeWidth="1"
          />
        ))}

        {/* Hover highlight, behind the columns */}
        {hoveredIndex !== null && (
          <rect
            x={scaleX(days[hoveredIndex].dayMs) - slot / 2}
            y={padding.top}
            width={slot}
            height={chartH}
            fill="rgba(255,255,255,0.07)"
          />
        )}

        {/* Daily columns: BURN up, MINT down, same scale */}
        {days.map((d, i) => {
          const x = scaleX(d.dayMs) - barW / 2;
          const dim = hoveredIndex !== null && hoveredIndex !== i;
          const burnTop = scaleY(Math.min(d.burn, burnBound));
          const mintBottom = scaleY(-Math.min(d.mint, mintBound));
          return (
            <g key={`col-${d.dayMs}`} opacity={dim ? 0.5 : 1}>
              {d.burn > 0 && (
                <rect
                  x={x}
                  y={burnTop}
                  width={barW}
                  height={Math.max(1.5, zeroY - burnTop)}
                  fill="#B6FFCE"
                />
              )}
              {d.mint > 0 && (
                <rect
                  x={x}
                  y={zeroY}
                  width={barW}
                  height={Math.max(1.5, mintBottom - zeroY)}
                  fill="#FF5C33"
                />
              )}
              {d.burn > burnBound && breakMark(x, padding.top + 6)}
              {d.mint > mintBound && breakMark(x, chartBottom - 6)}
            </g>
          );
        })}

        {/* Baseline */}
        <line
          x1={padding.left}
          y1={zeroY}
          x2={width - padding.right}
          y2={zeroY}
          stroke="#B8B9B6"
          strokeWidth="1"
          opacity="0.8"
        />

        {/* 7-day net average, with a halo so it reads over the columns */}
        {avgSegments.map((d, i) => (
          <g key={`avg-${i}`}>
            <path d={d} fill="none" stroke="#1A1A1A" strokeWidth="4.5" opacity="0.8" />
            <path
              d={d}
              fill="none"
              stroke="#FF8400"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </g>
        ))}

        {/* Y-axis labels */}
        {yTicks.map((tick) => (
          <text
            key={`ytick-${tick}`}
            x={padding.left - 10}
            y={scaleY(tick)}
            textAnchor="end"
            dominantBaseline="middle"
            fill="#B8B9B6"
            fontSize="10"
            fontFamily={mono}
          >
            {tick === 0 ? "0" : formatCompact(Math.abs(tick)).replace("+", "")}
          </text>
        ))}

        {/* Which side is which, so the chart reads without the legend */}
        <text
          x={16}
          y={(padding.top + zeroY) / 2}
          fill="#B6FFCE"
          fontSize="9"
          fontFamily={mono}
          textAnchor="middle"
          transform={`rotate(-90, 16, ${(padding.top + zeroY) / 2})`}
        >
          BURN ▲
        </text>
        <text
          x={16}
          y={(zeroY + chartBottom) / 2}
          fill="#FF5C33"
          fontSize="9"
          fontFamily={mono}
          textAnchor="middle"
          transform={`rotate(-90, 16, ${(zeroY + chartBottom) / 2})`}
        >
          MINT ▼
        </text>

        {/* X-axis labels */}
        {xLabels.map(({ ms, label }) => (
          <text
            key={`xlabel-${ms}`}
            x={scaleX(ms)}
            y={height - 12}
            textAnchor="middle"
            fill="#B8B9B6"
            fontSize="10"
          >
            {label}
          </text>
        ))}

        {/* Hover surface */}
        <rect
          x={padding.left}
          y={padding.top}
          width={chartW}
          height={chartH}
          fill="transparent"
          onMouseMove={handleMove}
        />

        {/* Tooltip */}
        {hoveredIndex !== null &&
          (() => {
            const d = days[hoveredIndex];
            const cx = scaleX(d.dayMs);
            const tooltipW = 212;
            const tooltipH = 90;
            const tooltipX =
              cx + tooltipW + 14 > width - padding.right ? cx - tooltipW - 14 : cx + 14;
            const tooltipY = Math.max(
              padding.top,
              Math.min(zeroY - tooltipH / 2, chartBottom - tooltipH)
            );
            const netColor = d.net >= 0 ? "#B6FFCE" : "#FF5C33";
            return (
              <g style={{ pointerEvents: "none" }}>
                <rect
                  x={tooltipX}
                  y={tooltipY}
                  width={tooltipW}
                  height={tooltipH}
                  fill="#111111"
                  stroke="#2E2E2E"
                  strokeWidth="1"
                />
                <text x={tooltipX + 10} y={tooltipY + 17} fontSize="10" fill="#B8B9B6">
                  {formatShortDate(d.dayMs)} · {d.count} event{d.count > 1 ? "s" : ""}
                </text>
                <text
                  x={tooltipX + 10}
                  y={tooltipY + 35}
                  fontSize="10"
                  fill="#B6FFCE"
                  fontFamily={mono}
                >
                  ▲ BURN {formatCompact(d.burn).replace("+", "")}
                </text>
                <text
                  x={tooltipX + 10}
                  y={tooltipY + 50}
                  fontSize="10"
                  fill="#FF5C33"
                  fontFamily={mono}
                >
                  ▼ MINT {formatCompact(d.mint).replace("+", "")}
                </text>
                <line
                  x1={tooltipX + 10}
                  y1={tooltipY + 58}
                  x2={tooltipX + tooltipW - 10}
                  y2={tooltipY + 58}
                  stroke="#2E2E2E"
                  strokeWidth="1"
                />
                <text
                  x={tooltipX + 10}
                  y={tooltipY + 74}
                  fontSize="11"
                  fontWeight="700"
                  fill={netColor}
                  fontFamily={mono}
                >
                  NET {formatCompact(d.net)}
                </text>
                <text
                  x={tooltipX + tooltipW - 10}
                  y={tooltipY + 74}
                  fontSize="9"
                  fill="#FF8400"
                  textAnchor="end"
                  fontFamily={mono}
                >
                  7d {d.avgReady ? formatCompact(d.avg) : "n/a"}
                </text>
              </g>
            );
          })()}
      </svg>
    </div>
  );
}
