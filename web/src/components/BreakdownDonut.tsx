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
      color: "#10B981",
      textColor: "text-emerald-500",
    });
  if (burnedPending > 0)
    segments.push({
      label: "Burned (pending)",
      value: burnedPending,
      color: "#6EE7B7",
      textColor: "text-emerald-300",
    });
  if (mintedOnChain > 0)
    segments.push({
      label: "Minted (on-chain)",
      value: mintedOnChain,
      color: "#EF4444",
      textColor: "text-red-500",
    });
  if (mintedPending > 0)
    segments.push({
      label: "Minted (pending)",
      value: mintedPending,
      color: "#FCA5A5",
      textColor: "text-red-300",
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
    <div className="rounded-2xl bg-white border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-medium uppercase tracking-wider text-gray-500">
          Supply breakdown
        </h3>
      </div>

      <div className="flex items-center gap-8">
        {/* Donut */}
        <div className="shrink-0">
          <svg width={240} height={240} viewBox="0 0 240 240">
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
              className="text-xs fill-gray-400"
              style={{ fontSize: 11 }}
            >
              TOTAL
            </text>
            <text
              x={cx}
              y={cy + 14}
              textAnchor="middle"
              className="fill-gray-900"
              style={{ fontSize: 18, fontWeight: 700, fontFamily: "monospace" }}
            >
              {formatM(total)}
            </text>
          </svg>
        </div>

        {/* Legend */}
        <div className="flex flex-col gap-3 text-sm">
          {arcs.map((seg, i) => {
            const pct = ((seg.value / total) * 100).toFixed(1);
            return (
              <div key={i} className="flex items-center gap-3">
                <span
                  className="w-3 h-3 rounded-sm shrink-0"
                  style={{ backgroundColor: seg.color }}
                />
                <span className="text-gray-600 min-w-[140px]">{seg.label}</span>
                <span className={`font-mono tabular-nums font-semibold ${seg.textColor}`}>
                  {formatM(seg.value)}
                </span>
                <span className="text-gray-400 font-mono tabular-nums text-xs">
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
