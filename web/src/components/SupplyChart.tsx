"use client";

import { useState } from "react";
import type { CarbonEvent } from "@/lib/data";

interface ChartPoint {
  x: number;
  y: number;
  event: CarbonEvent;
  cumulative: number;
}

function formatCompact(raw: number): string {
  const abs = Math.abs(raw);
  const sign = raw >= 0 ? "+" : "-";
  const m = abs / 1_000_000;
  if (m >= 1) return `${sign}${m.toFixed(1).replace(/\.0$/, "")}M`;
  const k = abs / 1_000;
  return `${sign}${k.toFixed(0)}K`;
}

function formatShortDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function SupplyChart({ events }: { events: CarbonEvent[] }) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // Sort events chronologically and compute cumulative supply
  const sorted = [...events].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  if (sorted.length === 0) {
    return (
      <div className="flex items-center justify-center h-[300px] bg-white rounded-lg border border-gray-200 text-sm text-gray-400">
        No events yet
      </div>
    );
  }

  let cumulative = 0;
  const dataPoints: { event: CarbonEvent; cumulative: number }[] = sorted.map(
    (event) => {
      if (event.decision === "MINT") {
        cumulative += event.amount_crbn;
      } else if (event.decision === "BURN") {
        cumulative -= event.amount_crbn;
      }
      return { event, cumulative };
    }
  );

  // Chart dimensions
  const width = 900;
  const height = 300;
  const padding = { top: 30, right: 30, bottom: 40, left: 70 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // Scales
  const minY = Math.min(0, ...dataPoints.map((d) => d.cumulative));
  const maxY = Math.max(0, ...dataPoints.map((d) => d.cumulative));
  const yRange = maxY - minY || 1;
  const yPad = yRange * 0.1;

  const scaleX = (i: number) =>
    padding.left +
    (dataPoints.length === 1 ? chartW / 2 : (i / (dataPoints.length - 1)) * chartW);

  const scaleY = (val: number) =>
    padding.top + chartH - ((val - (minY - yPad)) / (yRange + 2 * yPad)) * chartH;

  // Build SVG path
  const pathD = dataPoints
    .map((d, i) => `${i === 0 ? "M" : "L"} ${scaleX(i).toFixed(1)} ${scaleY(d.cumulative).toFixed(1)}`)
    .join(" ");

  // Area fill path (fill down to zero line)
  const zeroY = scaleY(0);
  const areaD =
    pathD +
    ` L ${scaleX(dataPoints.length - 1).toFixed(1)} ${zeroY.toFixed(1)}` +
    ` L ${scaleX(0).toFixed(1)} ${zeroY.toFixed(1)} Z`;

  // Y-axis ticks (5 ticks)
  const yTicks: number[] = [];
  const tickCount = 5;
  for (let i = 0; i <= tickCount; i++) {
    yTicks.push(minY - yPad + ((yRange + 2 * yPad) / tickCount) * i);
  }

  // X-axis labels (show ~6 evenly spaced dates)
  const xLabelCount = Math.min(6, dataPoints.length);
  const xLabels: { index: number; label: string }[] = [];
  for (let i = 0; i < xLabelCount; i++) {
    const idx =
      xLabelCount === 1
        ? 0
        : Math.round((i / (xLabelCount - 1)) * (dataPoints.length - 1));
    xLabels.push({
      index: idx,
      label: formatShortDate(dataPoints[idx].event.created_at),
    });
  }

  // Determine if cumulative is net positive (red = minted more) or negative (green = burned more)
  const lastCumulative = dataPoints[dataPoints.length - 1].cumulative;
  const lineColor = lastCumulative > 0 ? "#EF4444" : "#10B981";
  const fillColor = lastCumulative > 0 ? "rgba(239,68,68,0.08)" : "rgba(16,185,129,0.08)";

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-2 px-2">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
          Cumulative Supply Change
        </span>
        <span
          className={`text-sm font-mono font-semibold tabular-nums ${lastCumulative > 0 ? "text-red-500" : "text-emerald-500"}`}
        >
          {formatCompact(lastCumulative)} CBWD
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
            stroke="#f1f5f9"
            strokeWidth="1"
          />
        ))}

        {/* Zero line */}
        <line
          x1={padding.left}
          y1={zeroY}
          x2={width - padding.right}
          y2={zeroY}
          stroke="#cbd5e1"
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
          const cy = scaleY(d.cumulative);
          const dotColor = d.event.decision === "BURN" ? "#10B981" : d.event.decision === "MINT" ? "#EF4444" : "#9CA3AF";
          return (
            <g key={i}>
              {/* Invisible larger hit area */}
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
                r={hoveredIndex === i ? 5 : 3}
                fill={dotColor}
                stroke="white"
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
            className="fill-gray-400"
            fontSize="10"
            fontFamily="ui-monospace, monospace"
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
            className="fill-gray-400"
            fontSize="10"
          >
            {label}
          </text>
        ))}

        {/* Tooltip */}
        {hoveredIndex !== null && (() => {
          const d = dataPoints[hoveredIndex];
          const cx = scaleX(hoveredIndex);
          const cy = scaleY(d.cumulative);
          const tooltipW = 260;
          const tooltipH = 52;
          // Flip tooltip if too close to right edge
          const tooltipX = cx + tooltipW + 10 > width ? cx - tooltipW - 10 : cx + 10;
          const tooltipY = Math.max(padding.top, Math.min(cy - tooltipH / 2, height - padding.bottom - tooltipH));
          const decColor = d.event.decision === "BURN" ? "#10B981" : "#EF4444";

          return (
            <g>
              {/* Vertical guideline */}
              <line
                x1={cx}
                y1={padding.top}
                x2={cx}
                y2={height - padding.bottom}
                stroke="#94a3b8"
                strokeWidth="0.5"
                strokeDasharray="3 2"
              />
              {/* Tooltip background */}
              <rect
                x={tooltipX}
                y={tooltipY}
                width={tooltipW}
                height={tooltipH}
                rx="6"
                fill="white"
                stroke="#e2e8f0"
                strokeWidth="1"
                filter="drop-shadow(0 1px 3px rgba(0,0,0,0.1))"
              />
              {/* Decision badge */}
              <text
                x={tooltipX + 8}
                y={tooltipY + 16}
                fontSize="10"
                fontWeight="700"
                fill={decColor}
              >
                {d.event.decision}
              </text>
              {/* Amount */}
              <text
                x={tooltipX + tooltipW - 8}
                y={tooltipY + 16}
                fontSize="10"
                fontWeight="600"
                fill={decColor}
                textAnchor="end"
                fontFamily="ui-monospace, monospace"
              >
                {formatCompact(d.event.decision === "MINT" ? d.event.amount_crbn : -d.event.amount_crbn)} CBWD
              </text>
              {/* Title (truncated) */}
              <text
                x={tooltipX + 8}
                y={tooltipY + 32}
                fontSize="11"
                fill="#1e293b"
                clipPath={`inset(0 0 0 0)`}
              >
                {d.event.event_title.length > 38
                  ? d.event.event_title.slice(0, 38) + "..."
                  : d.event.event_title}
              </text>
              {/* Date + cumulative */}
              <text
                x={tooltipX + 8}
                y={tooltipY + 46}
                fontSize="9"
                fill="#94a3b8"
              >
                {formatShortDate(d.event.created_at)} | Cumulative: {formatCompact(d.cumulative)}
              </text>
            </g>
          );
        })()}
      </svg>
    </div>
  );
}
