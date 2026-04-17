"use client";

import { useState } from "react";
import type { CarbonEvent } from "@/lib/types";

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

  // Build cumulative series
  let cumulative = 0;
  const rawPoints: { event: CarbonEvent; cumulative: number }[] = sorted.map(
    (event) => {
      if (event.decision === "MINT") {
        cumulative += event.amount_crbn;
      } else if (event.decision === "BURN") {
        cumulative -= event.amount_crbn;
      }
      return { event, cumulative };
    }
  );

  // Prepend a synthetic genesis point when there are fewer than 2 real points
  // so the chart always renders a visible line.
  const dataPoints =
    rawPoints.length < 2
      ? [
          {
            event: {
              ...rawPoints[0].event,
              // Shift timestamp 1 hour before first real event
              created_at: new Date(
                new Date(rawPoints[0].event.created_at).getTime() - 3_600_000
              ).toISOString(),
            },
            cumulative: 0,
          },
          ...rawPoints,
        ]
      : rawPoints;

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

  // Line and fill always orange in Lunaris Dark
  const lineColor = "#FF8400";
  const fillColor = "rgba(255,132,0,0.12)";

  // Cumulative label color
  const lastCumulative = dataPoints[dataPoints.length - 1].cumulative;
  const cumulativeColor = lastCumulative > 0 ? "#FF5C33" : "#B6FFCE";

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
          Cumulative Supply Change
        </span>
        <span
          className="text-sm font-mono font-semibold tabular-nums"
          style={{ color: cumulativeColor }}
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
          const cy = scaleY(d.cumulative);
          const dotColor = d.event.decision === "BURN" ? "#B6FFCE" : d.event.decision === "MINT" ? "#FF5C33" : "#B8B9B6";
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
          const cy = scaleY(d.cumulative);
          const tooltipW = 260;
          const tooltipH = 52;
          // Flip tooltip if too close to right edge
          const tooltipX = cx + tooltipW + 10 > width ? cx - tooltipW - 10 : cx + 10;
          const tooltipY = Math.max(padding.top, Math.min(cy - tooltipH / 2, height - padding.bottom - tooltipH));
          const decColor = d.event.decision === "BURN" ? "#B6FFCE" : "#FF5C33";

          return (
            <g>
              {/* Vertical guideline */}
              <line
                x1={cx}
                y1={padding.top}
                x2={cx}
                y2={height - padding.bottom}
                stroke="#B8B9B6"
                strokeWidth="0.5"
                strokeDasharray="3 2"
              />
              {/* Tooltip background */}
              <rect
                x={tooltipX}
                y={tooltipY}
                width={tooltipW}
                height={tooltipH}
                rx="0"
                fill="#1A1A1A"
                stroke="#2E2E2E"
                strokeWidth="1"
                filter="drop-shadow(0 1px 3px rgba(0,0,0,0.3))"
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
                fontFamily="'JetBrains Mono', ui-monospace, monospace"
              >
                {formatCompact(d.event.decision === "MINT" ? d.event.amount_crbn : -d.event.amount_crbn)} CBWD
              </text>
              {/* Title (truncated) */}
              <text
                x={tooltipX + 8}
                y={tooltipY + 32}
                fontSize="11"
                fill="#FFFFFF"
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
                fill="#B8B9B6"
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
