import Link from "next/link";
import { InfoTooltip } from "../InfoTooltip";

export interface TopRegionsDestructiveCardProps {
  regions: Array<{ region: string; mint_ratio: number; events: number }>;
}

/**
 * TopRegionsDestructiveCard — Server Component
 *
 * Mirror of TopRegionsSustainableCard. Shows top 5 regions ranked by MINT
 * ratio (destructive score) over 7 days. The "darkest" regions where
 * harmful events dominate, surfaced explicitly so the dashboard maps both
 * ends of the spectrum.
 */
export function TopRegionsDestructiveCard({
  regions,
}: TopRegionsDestructiveCardProps) {
  const items = regions.slice(0, 5);

  return (
    <div
      style={{
        backgroundColor: "var(--card-bg)",
        border: "1px solid var(--border)",
      }}
      className="p-4"
    >
      {/* Title */}
      <p
        className="text-xs uppercase tracking-wider font-mono mb-1"
        style={{ color: "var(--muted)" }}
      >
        TOP REGIONS · DESTRUCTIVE · 7D
        <InfoTooltip text="Régions avec le plus haut RATIO d'actions négatives (MINT ÷ total) sur 7 jours. Minimum 3 events on-chain pour figurer. Identifie les zones où les régressions dominent." />
      </p>
      <p
        className="text-[10px] uppercase tracking-wider font-mono mb-4"
        style={{ color: "var(--brand-teal)" }}
      >
        MINT RATIO WEIGHTED
      </p>

      {items.length === 0 ? (
        <div className="flex items-center justify-center py-6">
          <span
            className="text-xs font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)" }}
          >
            NO REGIONAL DATA YET
          </span>
        </div>
      ) : (
        <div className="flex flex-col">
          {items.map((item, i) => {
            const pct = Math.round(item.mint_ratio * 100);
            const barWidth = Math.min(100, Math.max(0, pct));

            return (
              <Link
                key={item.region}
                href={`/events?region=${encodeURIComponent(item.region)}&decision=MINT&since=7d`}
                className="block py-2 hover:opacity-80"
                style={{
                  borderBottom:
                    i < items.length - 1 ? "1px solid var(--border)" : "none",
                  cursor: "pointer",
                }}
                title={`See the MINT events behind ${item.region}'s ${pct}% destructive ratio`}
              >
                <div className="flex items-center gap-3">
                  <span
                    className="text-xs font-mono tabular-nums shrink-0 w-6"
                    style={{ color: "var(--muted)" }}
                  >
                    {String(i + 1).padStart(2, "0")}.
                  </span>
                  <span
                    className="text-xs font-mono uppercase tracking-wider flex-1 truncate"
                    style={{ color: "var(--foreground)" }}
                  >
                    {item.region}
                  </span>
                  <div
                    style={{
                      width: "60px",
                      height: "4px",
                      backgroundColor: "var(--border)",
                      flexShrink: 0,
                    }}
                  >
                    <div
                      style={{
                        width: `${barWidth}%`,
                        height: "100%",
                        backgroundColor: "#FF5C33",
                      }}
                    />
                  </div>
                  <span
                    className="text-xs font-mono tabular-nums shrink-0 w-8 text-right"
                    style={{ color: "#FF5C33" }}
                  >
                    {pct}%
                  </span>
                </div>
                <p
                  className="text-[10px] font-mono mt-1 ml-9"
                  style={{ color: "var(--muted)" }}
                >
                  · {item.events} {item.events === 1 ? "event" : "events"}
                </p>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
