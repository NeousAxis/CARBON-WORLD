"use client";

import type { CarbonEvent } from "@/lib/data";

function formatM(raw: number): string {
  const m = raw / 1_000_000;
  if (m >= 1) return `${m.toFixed(1).replace(/\.0$/, "")}M`;
  return `${(raw / 1_000).toFixed(0)}K`;
}

interface Segment {
  label: string;
  value: number;
  color: string;
  textColor: string;
}

function DonutArc({
  cx,
  cy,
  r,
  startAngle,
  endAngle,
  color,
}: {
  cx: number;
  cy: number;
  r: number;
  startAngle: number;
  endAngle: number;
  color: string;
}) {
  const innerR = r * 0.6;
  const startRad = ((startAngle - 90) * Math.PI) / 180;
  const endRad = ((endAngle - 90) * Math.PI) / 180;
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;

  const x1o = cx + r * Math.cos(startRad);
  const y1o = cy + r * Math.sin(startRad);
  const x2o = cx + r * Math.cos(endRad);
  const y2o = cy + r * Math.sin(endRad);
  const x1i = cx + innerR * Math.cos(endRad);
  const y1i = cy + innerR * Math.sin(endRad);
  const x2i = cx + innerR * Math.cos(startRad);
  const y2i = cy + innerR * Math.sin(startRad);

  const d = [
    `M ${x1o} ${y1o}`,
    `A ${r} ${r} 0 ${largeArc} 1 ${x2o} ${y2o}`,
    `L ${x1i} ${y1i}`,
    `A ${innerR} ${innerR} 0 ${largeArc} 0 ${x2i} ${y2i}`,
    "Z",
  ].join(" ");

  return <path d={d} fill={color} />;
}

export function BreakdownDonut({ events }: { events: CarbonEvent[] }) {
  const burnedOnChain = events
    .filter((e) => e.decision === "BURN" && e.tx_hash)
    .reduce((s, e) => s + e.amount_crbn, 0);
  const burnedPending = events
    .filter((e) => e.decision === "BURN" && !e.tx_hash)
    .reduce((s, e) => s + e.amount_crbn, 0);
  const mintedOnChain = events
    .filter((e) => e.decision === "MINT" && e.tx_hash)
    .reduce((s, e) => s + e.amount_crbn, 0);
  const mintedPending = events
    .filter((e) => e.decision === "MINT" && !e.tx_hash)
    .reduce((s, e) => s + e.amount_crbn, 0);

  const segments: Segment[] = [];

  if (burnedOnChain > 0)
    segments.push({
      label: "Burned (on-chain)",
      value: burnedOnChain,
      color: "#34D399",
      textColor: "#34D399",
    });
  if (burnedPending > 0)
    segments.push({
      label: "Burned (pending)",
      value: burnedPending,
      color: "#6EE7B7",
      textColor: "#B6FFCE",
    });
  if (mintedOnChain > 0)
    segments.push({
      label: "Minted (on-chain)",
      value: mintedOnChain,
      color: "#FF5C33",
      textColor: "#FF5C33",
    });
  if (mintedPending > 0)
    segments.push({
      label: "Minted (pending)",
      value: mintedPending,
      color: "#FF8400",
      textColor: "#FF8400",
    });

  const total = segments.reduce((s, seg) => s + seg.value, 0);
  if (total === 0) return null;

  // Build arcs
  const cx = 120;
  const cy = 120;
  const r = 100;
  let currentAngle = 0;
  const arcs = segments.map((seg) => {
    const angle = (seg.value / total) * 360;
    const start = currentAngle;
    const end = currentAngle + angle;
    currentAngle = end;
    return { ...seg, start, end };
  });

  return (
    <div
      className="p-5"
      style={{
        backgroundColor: "#1A1A1A",
        border: "1px solid #2E2E2E",
        boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
      }}
    >
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-medium uppercase tracking-wider" style={{ color: "#B8B9B6" }}>
          Supply breakdown
        </h3>
      </div>

      <div className="flex flex-col items-center gap-4">
        {/* Donut */}
        <div className="shrink-0">
          <svg width={180} height={180} viewBox="0 0 240 240">
            {arcs.map((arc, i) => (
              <DonutArc
                key={i}
                cx={cx}
                cy={cy}
                r={r}
                startAngle={arc.start}
                endAngle={arc.end}
                color={arc.color}
              />
            ))}
            {/* Center text */}
            <text
              x={cx}
              y={cy - 8}
              textAnchor="middle"
              fill="#B8B9B6"
              style={{ fontSize: 11 }}
            >
              TOTAL
            </text>
            <text
              x={cx}
              y={cy + 14}
              textAnchor="middle"
              fill="#FFFFFF"
              style={{ fontSize: 18, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}
            >
              {formatM(total)}
            </text>
          </svg>
        </div>

        {/* Legend */}
        <div className="flex flex-col gap-2 text-sm w-full">
          {arcs.map((seg, i) => {
            const pct = ((seg.value / total) * 100).toFixed(1);
            return (
              <div key={i} className="flex items-center gap-2">
                <span
                  className="w-3 h-3 shrink-0"
                  style={{ backgroundColor: seg.color }}
                />
                <span className="flex-1 truncate" style={{ color: "#B8B9B6" }}>{seg.label}</span>
                <span className="font-mono tabular-nums font-semibold shrink-0" style={{ color: seg.textColor }}>
                  {formatM(seg.value)}
                </span>
                <span className="font-mono tabular-nums text-xs shrink-0" style={{ color: "#666" }}>
                  {pct}%
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
