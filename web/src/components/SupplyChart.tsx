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
  net: number; // burn - mint (>0 = net-burn = world improving)
  burn: number;
  mint: number;
  count: number;
  avg: number; // trailing 7-calendar-day average of net
  avgReady: boolean; // window has enough covered days to be meaningful
}

function formatCompact(raw: number): string {
  const abs = Math.abs(raw);
  const sign = raw >= 0 ? "+" : "-";
  const b = abs / 1_000_000_000;
  if (b >= 1) return `${sign}${b.toFixed(1).replace(/\.0$/, "")}B`;
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

// Round to the nearest 1 / 2 / 5 x 10^n so axis ticks read as human numbers.
function niceRound(v: number): number {
  if (v === 0) return 0;
  const exp = Math.floor(Math.log10(v));
  const pow = Math.pow(10, exp);
  const frac = v / pow;
  const snapped = frac < 1.5 ? 1 : frac < 3.5 ? 2 : frac < 7.5 ? 5 : 10;
  return snapped * pow;
}

export function SupplyChart({ events }: { events: CarbonEvent[] }) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const decided = events.filter(
    (e) => (e.decision === "BURN" || e.decision === "MINT") && e.created_at
  );

  if (decided.length === 0) {
    return (
      <div
        className="flex items-center justify-center h-[300px] text-sm"
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

  // Group into per-day net-flow buckets (burn - mint). Each dot is one real
  // calendar day: it materialises what actually happened on that date.
  const byDay = new Map<string, DayPoint>();
  for (const e of decided) {
    const key = new Date(e.created_at).toISOString().slice(0, 10);
    let p = byDay.get(key);
    if (!p) {
      p = {
        dayMs: new Date(key + "T00:00:00Z").getTime(),
        net: 0,
        burn: 0,
        mint: 0,
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
  const dataPoints = [...byDay.values()].sort((a, b) => a.dayMs - b.dayMs);
  for (const p of dataPoints) p.net = p.burn - p.mint;

  // Trailing 7-CALENDAR-day average (days without events count as 0, because no
  // event genuinely means no measured impact that day).
  for (const p of dataPoints) {
    const from = p.dayMs - (AVG_WINDOW_DAYS - 1) * DAY_MS;
    let sum = 0;
    let covered = 0;
    for (const q of dataPoints) {
      if (q.dayMs > p.dayMs) break;
      if (q.dayMs >= from) {
        sum += q.net;
        covered += 1;
      }
    }
    p.avg = sum / AVG_WINDOW_DAYS;
    // Below this, the window is mostly a pipeline silence and the average would
    // draw a fake ramp back towards zero after every gap.
    p.avgReady = covered >= AVG_MIN_COVERAGE;
  }

  const firstMs = dataPoints[0].dayMs;
  const lastMs = dataPoints[dataPoints.length - 1].dayMs;
  const spanMs = Math.max(DAY_MS, lastMs - firstMs);

  // Headline: net over the last 7 calendar days (same window as the avg line).
  const headlineFrom = lastMs - (AVG_WINDOW_DAYS - 1) * DAY_MS;
  const last7 = dataPoints
    .filter((d) => d.dayMs >= headlineFrom)
    .reduce((s, d) => s + d.net, 0);
  const headlineColor = last7 >= 0 ? "#B6FFCE" : "#FF5C33";

  // Chart dimensions
  const width = 900;
  const height = 300;
  const padding = { top: 24, right: 30, bottom: 40, left: 74 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // X = real time, so a 5-day silence reads as a 5-day gap and every date label
  // sits at its true position.
  const scaleX = (dayMs: number) =>
    padding.left + ((dayMs - firstMs) / spanMs) * chartW;

  // Y = signed square root. A single outlier day (-332M) would otherwise
  // flatten the other 95 days into an unreadable band. One pixel is worth the
  // same number of compressed units above and below zero, but the two sides get
  // the vertical room their data actually needs instead of a symmetric half
  // each (the positive side is nearly empty, 93 days out of 96 are net-MINT).
  const signedSqrt = (v: number) => Math.sign(v) * Math.sqrt(Math.abs(v));
  const plotted = dataPoints.flatMap((d) => (d.avgReady ? [d.net, d.avg] : [d.net]));
  const posMax = Math.max(0, ...plotted);
  const negMax = Math.max(0, ...plotted.map((v) => -v));
  // Degenerate case (a single day, or everything netting to exactly zero):
  // fall back to a symmetric scale so the line lands mid-card, not on an edge.
  const flat = posMax === 0 && negMax === 0;
  const negUnits = flat ? 1 : Math.sqrt(negMax) * 1.06;
  // Keep a floor of headroom above zero so the zero line never sticks to the
  // top edge and a net-BURN day still has somewhere to go.
  const posUnits = flat ? 1 : Math.max(Math.sqrt(posMax) * 1.15, negUnits * 0.16);
  const totalUnits = posUnits + negUnits;
  const unitsToPx = chartH / totalUnits;
  const zeroY = padding.top + posUnits * unitsToPx;
  const scaleY = (val: number) => zeroY - signedSqrt(val) * unitsToPx;

  // Ticks per side, spaced evenly in the compressed space, snapped to round
  // numbers, then thinned out so labels never collide.
  const sideTicks = (max: number, sign: 1 | -1) => {
    const out: number[] = [];
    for (const f of [1, 0.55, 0.25]) {
      const v = niceRound(max * f * f);
      if (v <= 0 || out.includes(v)) continue;
      if (Math.abs(scaleY(sign * v) - zeroY) < 14) continue;
      if (out.some((p) => Math.abs(scaleY(sign * p) - scaleY(sign * v)) < 18)) continue;
      out.push(v);
    }
    return out.map((v) => sign * v);
  };
  const yTicks = [...sideTicks(posMax, 1), 0, ...sideTicks(negMax, -1)];

  // Split into runs of consecutive calendar days. Nothing is ever drawn across
  // a silence, so a 7-day gap reads as a hole and not as a slope.
  const runs: DayPoint[][] = [];
  for (const d of dataPoints) {
    const run = runs[runs.length - 1];
    if (run && d.dayMs - run[run.length - 1].dayMs === DAY_MS) run.push(d);
    else runs.push([d]);
  }
  const runPath = (run: DayPoint[], value: (d: DayPoint) => number) =>
    run
      .map(
        (d, i) =>
          `${i === 0 ? "M" : "L"} ${scaleX(d.dayMs).toFixed(1)} ${scaleY(value(d)).toFixed(1)}`
      )
      .join(" ");
  const rawSegments = runs.map((run) => runPath(run, (d) => d.net));
  const avgSegments = runs.flatMap((run) => {
    const chunks: DayPoint[][] = [];
    for (const d of run) {
      if (!d.avgReady) {
        if (chunks[chunks.length - 1]?.length) chunks.push([]);
        continue;
      }
      if (!chunks.length) chunks.push([]);
      chunks[chunks.length - 1].push(d);
    }
    return chunks.filter((c) => c.length > 1).map((c) => runPath(c, (d) => d.avg));
  });
  const areaSegments = runs.map(
    (run) =>
      runPath(run, (d) => d.net) +
      ` L ${scaleX(run[run.length - 1].dayMs).toFixed(1)} ${zeroY.toFixed(1)}` +
      ` L ${scaleX(run[0].dayMs).toFixed(1)} ${zeroY.toFixed(1)} Z`
  );

  // X-axis labels: evenly spaced in TIME, not in bucket index.
  const xLabelCount = Math.min(6, dataPoints.length);
  const xLabels = Array.from({ length: xLabelCount }, (_, i) => {
    const ms =
      xLabelCount === 1 ? firstMs : firstMs + (i / (xLabelCount - 1)) * spanMs;
    return { ms, label: formatShortDate(ms) };
  });

  // Nearest-point hover: one overlay instead of 96 overlapping hit circles.
  const handleMove = (evt: React.MouseEvent<SVGRectElement>) => {
    const box = evt.currentTarget.getBoundingClientRect();
    const x = ((evt.clientX - box.left) / box.width) * chartW + padding.left;
    let best = 0;
    let bestDist = Infinity;
    dataPoints.forEach((d, i) => {
      const dist = Math.abs(scaleX(d.dayMs) - x);
      if (dist < bestDist) {
        bestDist = dist;
        best = i;
      }
    });
    setHoveredIndex(best);
  };

  const rangeLabel = `${formatShortDate(firstMs)} → ${formatShortDate(lastMs)}`;

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
          Net Impact Flow · Daily
        </span>
        <span
          className="text-sm font-mono font-semibold tabular-nums whitespace-nowrap"
          style={{ color: headlineColor }}
        >
          7D NET {formatCompact(last7)} CBWD
        </span>
      </div>

      {/* Legend: says out loud what up and down mean. */}
      <div
        className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 mb-2 px-2 text-[10px]"
        style={{ color: "#B8B9B6" }}
      >
        <span className="min-w-0" style={{ color: "#0190A0" }}>
          {rangeLabel} · {dataPoints.length} days with events
        </span>
        <span className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
          <span style={{ color: "#B6FFCE" }}>▲ above 0 = net BURN</span>
          <span style={{ color: "#FF5C33" }}>▼ below 0 = net MINT</span>
          <span style={{ color: "#FF8400" }}>▬ 7d average</span>
          <span>√ compressed y axis</span>
        </span>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height: "300px" }}
        onMouseLeave={() => setHoveredIndex(null)}
      >
        <defs>
          <clipPath id="supplychart-above">
            <rect x="0" y="0" width={width} height={zeroY} />
          </clipPath>
          <clipPath id="supplychart-below">
            <rect x="0" y={zeroY} width={width} height={height - zeroY} />
          </clipPath>
        </defs>

        {/* Grid lines */}
        {yTicks.map((tick, i) => (
          <line
            key={`grid-${i}`}
            x1={padding.left}
            y1={scaleY(tick)}
            x2={width - padding.right}
            y2={scaleY(tick)}
            stroke="#2E2E2E"
            strokeWidth="1"
          />
        ))}

        {/* Zero line */}
        <line
          x1={padding.left}
          y1={zeroY}
          x2={width - padding.right}
          y2={zeroY}
          stroke="#B8B9B6"
          strokeWidth="1"
          strokeDasharray="4 2"
        />

        {/* Area fill, green above zero and red below */}
        {areaSegments.map((d, i) => (
          <g key={`area-${i}`}>
            <path d={d} fill="rgba(182,255,206,0.16)" clipPath="url(#supplychart-above)" />
            <path d={d} fill="rgba(255,92,51,0.12)" clipPath="url(#supplychart-below)" />
          </g>
        ))}

        {/* Raw daily line, dimmed: the dots are the message, this only links them */}
        {rawSegments.map((d, i) => (
          <path
            key={`raw-${i}`}
            d={d}
            fill="none"
            stroke="rgba(184,185,182,0.45)"
            strokeWidth="1"
          />
        ))}

        {/* 7-day trailing average: the trend */}
        {avgSegments.map((d, i) => (
          <path key={`avg-${i}`} d={d} fill="none" stroke="#FF8400" strokeWidth="2" />
        ))}

        {/* Daily points */}
        {dataPoints.map((d, i) => (
          <circle
            key={`dot-${i}`}
            cx={scaleX(d.dayMs)}
            cy={scaleY(d.net)}
            r={hoveredIndex === i ? 5.5 : 3}
            fill={d.net >= 0 ? "#B6FFCE" : "#FF5C33"}
            stroke="#1A1A1A"
            strokeWidth="1.5"
            style={{ transition: "r 0.15s ease" }}
          />
        ))}

        {/* Y-axis labels */}
        {yTicks.map((tick, i) => (
          <text
            key={`ytick-${i}`}
            x={padding.left - 8}
            y={scaleY(tick)}
            textAnchor="end"
            dominantBaseline="middle"
            fill="#B8B9B6"
            fontSize="10"
            fontFamily="'JetBrains Mono', ui-monospace, monospace"
          >
            {tick === 0 ? "0" : formatCompact(tick)}
          </text>
        ))}

        {/* X-axis labels */}
        {xLabels.map(({ ms, label }) => (
          <text
            key={`xlabel-${ms}`}
            x={scaleX(ms)}
            y={height - 10}
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
            const d = dataPoints[hoveredIndex];
            const cx = scaleX(d.dayMs);
            const tooltipW = 214;
            const tooltipH = 96;
            const tooltipX =
              cx + tooltipW + 12 > width - padding.right
                ? cx - tooltipW - 12
                : cx + 12;
            const tooltipY = Math.max(
              padding.top,
              Math.min(scaleY(d.net) - tooltipH / 2, height - padding.bottom - tooltipH)
            );
            const netColor = d.net >= 0 ? "#B6FFCE" : "#FF5C33";
            const mono = "'JetBrains Mono', ui-monospace, monospace";
            return (
              <g style={{ pointerEvents: "none" }}>
                <line
                  x1={cx}
                  y1={padding.top}
                  x2={cx}
                  y2={height - padding.bottom}
                  stroke="#B8B9B6"
                  strokeWidth="0.5"
                  strokeDasharray="3 2"
                />
                <rect
                  x={tooltipX}
                  y={tooltipY}
                  width={tooltipW}
                  height={tooltipH}
                  fill="#1A1A1A"
                  stroke="#2E2E2E"
                  strokeWidth="1"
                  filter="drop-shadow(0 1px 3px rgba(0,0,0,0.3))"
                />
                <text x={tooltipX + 8} y={tooltipY + 17} fontSize="10" fill="#B8B9B6">
                  {formatShortDate(d.dayMs)} · {d.count} event{d.count > 1 ? "s" : ""}
                </text>
                <text
                  x={tooltipX + 8}
                  y={tooltipY + 35}
                  fontSize="10"
                  fill="#B6FFCE"
                  fontFamily={mono}
                >
                  ▲ BURN {formatCompact(d.burn)}
                </text>
                <text
                  x={tooltipX + 8}
                  y={tooltipY + 51}
                  fontSize="10"
                  fill="#FF5C33"
                  fontFamily={mono}
                >
                  ▼ MINT {formatCompact(-d.mint)}
                </text>
                <text
                  x={tooltipX + 8}
                  y={tooltipY + 69}
                  fontSize="11"
                  fontWeight="700"
                  fill={netColor}
                  fontFamily={mono}
                >
                  NET {formatCompact(d.net)}
                </text>
                <text
                  x={tooltipX + 8}
                  y={tooltipY + 86}
                  fontSize="9"
                  fill="#FF8400"
                  fontFamily={mono}
                >
                  7d avg {d.avgReady ? formatCompact(d.avg) : "n/a"}
                </text>
              </g>
            );
          })()}
      </svg>
    </div>
  );
}
