"use client";

import { useState } from "react";
import type { CarbonEvent } from "@/lib/types";

// Calibrated display amount (magnitude-driven, symmetric BURN/MINT). Falls back
// to the raw on-chain amount for older exports lacking amount_index.
const idxAmount = (e: CarbonEvent) => e.amount_index ?? e.amount_crbn;

interface DayPoint {
  dayMs: number;
  net: number; // burn - mint (>0 = net-burn = world improving)
  burn: number;
  mint: number;
  count: number;
}

function formatCompact(raw: number): string {
  const abs = Math.abs(raw);
  const sign = raw >= 0 ? "+" : "-";
  const m = abs / 1_000_000;
  if (m >= 1) return `${sign}${m.toFixed(1).replace(/\.0$/, "")}M`;
  const k = abs / 1_000;
  if (k >= 1) return `${sign}${k.toFixed(0)}K`;
  return `${sign}${abs.toFixed(0)}`;
}

function formatShortDate(ms: number): string {
  return new Date(ms).toLocaleDateString("en-US", { month: "short", day: "numeric" });
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

  // Group into per-day net-flow buckets (burn - mint), the honest signal that
  // actually oscillates instead of a monotone cumulative ramp.
  const byDay = new Map<string, DayPoint>();
  for (const e of decided) {
    const d = new Date(e.created_at);
    const key = d.toISOString().slice(0, 10);
    let p = byDay.get(key);
    if (!p) {
      const dayMs = new Date(key + "T00:00:00Z").getTime();
      p = { dayMs, net: 0, burn: 0, mint: 0, count: 0 };
      byDay.set(key, p);
    }
    const amt = idxAmount(e);
    if (e.decision === "BURN") p.burn += amt;
    else p.mint += amt;
    p.count += 1;
  }
  const dataPoints = [...byDay.values()].sort((a, b) => a.dayMs - b.dayMs);
  for (const p of dataPoints) p.net = p.burn - p.mint;

  // Chart dimensions
  const width = 900;
  const height = 300;
  const padding = { top: 30, right: 30, bottom: 40, left: 70 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // Symmetric Y scale around zero.
  const maxAbs = Math.max(1, ...dataPoints.map((d) => Math.abs(d.net)));
  const yPad = maxAbs * 0.12;
  const scaleX = (i: number) =>
    padding.left +
    (dataPoints.length === 1 ? chartW / 2 : (i / (dataPoints.length - 1)) * chartW);
  const scaleY = (val: number) =>
    padding.top + chartH / 2 - (val / (maxAbs + yPad)) * (chartH / 2);
  const zeroY = scaleY(0);

  // Line + area paths
  const pathD = dataPoints
    .map((d, i) => `${i === 0 ? "M" : "L"} ${scaleX(i).toFixed(1)} ${scaleY(d.net).toFixed(1)}`)
    .join(" ");
  const areaD =
    pathD +
    ` L ${scaleX(dataPoints.length - 1).toFixed(1)} ${zeroY.toFixed(1)}` +
    ` L ${scaleX(0).toFixed(1)} ${zeroY.toFixed(1)} Z`;

  // Y-axis ticks (symmetric)
  const yTicks = [maxAbs, maxAbs / 2, 0, -maxAbs / 2, -maxAbs];

  // X-axis labels (~6 evenly spaced dates)
  const xLabelCount = Math.min(6, dataPoints.length);
  const xLabels: { index: number; label: string }[] = [];
  for (let i = 0; i < xLabelCount; i++) {
    const idx =
      xLabelCount === 1 ? 0 : Math.round((i / (xLabelCount - 1)) * (dataPoints.length - 1));
    xLabels.push({ index: idx, label: formatShortDate(dataPoints[idx].dayMs) });
  }

  const lineColor = "#FF8400";
  const fillColor = "rgba(255,132,0,0.12)";

  // Headline: 7-day net (sum of last 7 buckets).
  const last7 = dataPoints.slice(-7).reduce((s, d) => s + d.net, 0);
  const headlineColor = last7 >= 0 ? "#B6FFCE" : "#FF5C33";

  return (
    <div
      className="p-4"
      style={{
        backgroundColor: "#1A1A1A",
        border: "1px solid #2E2E2E",
        boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
      }}
    >
      <div className="flex items-center justify-between mb-2 px-2">
        <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "#B8B9B6" }}>
          Net Impact Flow · Daily
        </span>
        <span
          className="text-sm font-mono font-semibold tabular-nums"
          style={{ color: headlineColor }}
        >
          {formatCompact(last7)} CBWD · 7d
        </span>
      </div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        style={{ height: "300px" }}
        onMouseLeave={() => setHoveredIndex(null)}
      >
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

        {/* Area fill */}
        <path d={areaD} fill={fillColor} />

        {/* Line */}
        <path d={pathD} fill="none" stroke={lineColor} strokeWidth="2" />

        {/* Data points */}
        {dataPoints.map((d, i) => {
          const cx = scaleX(i);
          const cy = scaleY(d.net);
          const dotColor = d.net >= 0 ? "#B6FFCE" : "#FF5C33";
          return (
            <g key={i}>
              <circle
                cx={cx}
                cy={cy}
                r={12}
                fill="transparent"
                onMouseEnter={() => setHoveredIndex(i)}
              />
              <circle
                cx={cx}
                cy={cy}
                r={hoveredIndex === i ? 5 : 2.5}
                fill={dotColor}
                stroke="#1A1A1A"
                strokeWidth="1.5"
                style={{ transition: "r 0.15s ease" }}
              />
            </g>
          );
        })}

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
            {formatCompact(tick)}
          </text>
        ))}

        {/* X-axis labels */}
        {xLabels.map(({ index, label }) => (
          <text
            key={`xlabel-${index}`}
            x={scaleX(index)}
            y={height - 10}
            textAnchor="middle"
            fill="#B8B9B6"
            fontSize="10"
          >
            {label}
          </text>
        ))}

        {/* Tooltip */}
        {hoveredIndex !== null && (() => {
          const d = dataPoints[hoveredIndex];
          const cx = scaleX(hoveredIndex);
          const tooltipW = 232;
          const tooltipH = 62;
          const tooltipX = cx + tooltipW + 10 > width ? cx - tooltipW - 10 : cx + 10;
          const tooltipY = Math.max(padding.top, Math.min(zeroY - tooltipH / 2, height - padding.bottom - tooltipH));
          const netColor = d.net >= 0 ? "#B6FFCE" : "#FF5C33";
          return (
            <g>
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
              <text x={tooltipX + 8} y={tooltipY + 16} fontSize="10" fill="#B8B9B6">
                {formatShortDate(d.dayMs)} · {d.count} ev
              </text>
              <text
                x={tooltipX + tooltipW - 8}
                y={tooltipY + 16}
                fontSize="11"
                fontWeight="700"
                fill={netColor}
                textAnchor="end"
                fontFamily="'JetBrains Mono', ui-monospace, monospace"
              >
                NET {formatCompact(d.net)}
              </text>
              <text x={tooltipX + 8} y={tooltipY + 34} fontSize="10" fill="#B6FFCE" fontFamily="'JetBrains Mono', ui-monospace, monospace">
                ▲ Burn {formatCompact(d.burn).replace("+", "")}
              </text>
              <text x={tooltipX + 8} y={tooltipY + 50} fontSize="10" fill="#FF5C33" fontFamily="'JetBrains Mono', ui-monospace, monospace">
                ▼ Mint {formatCompact(d.mint).replace("+", "")}
              </text>
            </g>
          );
        })()}
      </svg>
    </div>
  );
}
