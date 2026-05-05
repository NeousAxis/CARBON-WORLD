import Link from "next/link";
import { formatAmount } from "./formatAmount";

export interface SupplyTrendCardProps {
  /** 7 daily entries ordered oldest → newest */
  trend: Array<{ date: string; net_minted: number; net_burned: number }>;
}

/**
 * SupplyTrendCard — Server Component
 *
 * Renders a 7-day supply net-change sparkline using inline SVG.
 * Positive net_change (burn dominant) is shown with success color;
 * negative (mint dominant) with error color.
 *
 * Example props for smoke-test:
 * <SupplyTrendCard trend={[
 *   { date: "2026-04-15", net_minted: 500000, net_burned: 200000 },
 *   { date: "2026-04-16", net_minted: 300000, net_burned: 600000 },
 *   { date: "2026-04-17", net_minted: 100000, net_burned: 400000 },
 *   { date: "2026-04-18", net_minted: 250000, net_burned: 450000 },
 *   { date: "2026-04-19", net_minted: 200000, net_burned: 800000 },
 *   { date: "2026-04-20", net_minted: 150000, net_burned: 500000 },
 *   { date: "2026-04-21", net_minted: 100000, net_burned: 700000 },
 * ]} />
 */
export function SupplyTrendCard({ trend }: SupplyTrendCardProps) {
  // --- Derived data ---
  const values = trend.map((d) => d.net_minted - d.net_burned);
  const totalNet = values.reduce((acc, v) => acc + v, 0);
  // net_change positive = mint dominant (bad) → positive number here
  // net_change negative = burn dominant (good) → negative here
  // For supply: BURN reduces supply (net negative = good)
  // totalNet < 0 means burn dominant → good → green
  const isBurnDominant = totalNet <= 0;

  const hasData = trend.length > 0 && values.some((v) => v !== 0);

  // --- SVG sparkline geometry ---
  const SVG_W = 240;
  const SVG_H = 80;
  const PAD_X = 8;
  const PAD_Y = 10;
  const innerW = SVG_W - PAD_X * 2;
  const innerH = SVG_H - PAD_Y * 2;

  let polylinePoints = "";
  let fillPath = "";
  let dots: Array<{ cx: number; cy: number }> = [];

  if (hasData && trend.length >= 2) {
    const minVal = Math.min(...values);
    const maxVal = Math.max(...values);
    const range = maxVal - minVal || 1;

    const xStep = innerW / (trend.length - 1);

    const coords = values.map((v, i) => {
      const cx = PAD_X + i * xStep;
      // Flip Y: higher value = higher on chart (more mint = top)
      const cy = PAD_Y + innerH - ((v - minVal) / range) * innerH;
      return { cx, cy };
    });

    polylinePoints = coords.map((c) => `${c.cx},${c.cy}`).join(" ");
    dots = coords;

    // Fill path: from first point → all points → last point bottom → first point bottom
    const firstX = coords[0].cx;
    const lastX = coords[coords.length - 1].cx;
    const bottomY = PAD_Y + innerH;
    fillPath =
      `M ${firstX},${bottomY} ` +
      `L ${coords.map((c) => `${c.cx},${c.cy}`).join(" L ")} ` +
      `L ${lastX},${bottomY} Z`;
  }

  const strokeColor = isBurnDominant ? "var(--success-fg)" : "var(--error-fg)";
  const totalLabel = isBurnDominant
    ? `-${formatAmount(Math.abs(totalNet))}`
    : `+${formatAmount(Math.abs(totalNet))}`;

  return (
    <Link
      href="/events?since=7d"
      className="block hover:opacity-90"
      style={{
        backgroundColor: "var(--card-bg)",
        border: "1px solid var(--border)",
        cursor: "pointer",
        textDecoration: "none",
      }}
      title="See every event that drove the 7-day supply change"
    >
     <div className="p-4">
      {/* Title */}
      <p
        className="text-xs uppercase tracking-wider font-mono mb-3"
        style={{ color: "var(--muted)" }}
      >
        SUPPLY NET · 7D TREND
      </p>

      {!hasData ? (
        <div className="flex items-center justify-center py-8">
          <span
            className="text-xs font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)" }}
          >
            NO TREND DATA
          </span>
        </div>
      ) : (
        <>
          {/* Sparkline */}
          <svg
            width="100%"
            viewBox={`0 0 ${SVG_W} ${SVG_H}`}
            preserveAspectRatio="none"
            aria-hidden="true"
            style={{ display: "block", overflow: "visible" }}
          >
            {/* Gradient fill under curve */}
            <defs>
              <linearGradient id="supplyGrad" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor={
                    isBurnDominant ? "#B6FFCE" : "#FF5C33"
                  }
                  stopOpacity="0.25"
                />
                <stop
                  offset="100%"
                  stopColor={
                    isBurnDominant ? "#B6FFCE" : "#FF5C33"
                  }
                  stopOpacity="0"
                />
              </linearGradient>
            </defs>

            {/* Fill area */}
            {fillPath && (
              <path d={fillPath} fill="url(#supplyGrad)" />
            )}

            {/* Sparkline polyline */}
            {polylinePoints && (
              <polyline
                points={polylinePoints}
                fill="none"
                stroke={strokeColor}
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            )}

            {/* Data point dots */}
            {dots.map((dot, i) => (
              <circle
                key={i}
                cx={dot.cx}
                cy={dot.cy}
                r="3"
                fill="var(--foreground)"
              />
            ))}
          </svg>

          {/* Total */}
          <div className="flex flex-col items-center gap-1 mt-3">
            <span
              className="text-2xl font-mono tabular-nums font-bold leading-none"
              style={{ color: isBurnDominant ? "var(--success-fg)" : "var(--error-fg)" }}
            >
              {totalLabel} CBWD
            </span>
            <span
              className="text-[10px] font-mono uppercase tracking-wider"
              style={{ color: "var(--muted)" }}
            >
              NET SUPPLY CHANGE · LAST 7 DAYS
            </span>
          </div>
        </>
      )}
     </div>
    </Link>
  );
}
