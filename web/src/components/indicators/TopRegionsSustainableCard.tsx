export interface TopRegionsSustainableCardProps {
  regions: Array<{ region: string; burn_ratio: number; events: number }>;
}

/**
 * TopRegionsSustainableCard — Server Component
 *
 * Shows top 5 regions ranked by BURN ratio (sustainability score) over 7 days.
 * Each item includes a mini horizontal bar visualising the ratio.
 *
 * Example props for smoke-test:
 * <TopRegionsSustainableCard regions={[
 *   { region: "Europe", burn_ratio: 0.62, events: 11 },
 *   { region: "Latin America", burn_ratio: 0.55, events: 7 },
 * ]} />
 */
export function TopRegionsSustainableCard({
  regions,
}: TopRegionsSustainableCardProps) {
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
        TOP REGIONS · SUSTAINABLE · 7D
      </p>
      <p
        className="text-[10px] uppercase tracking-wider font-mono mb-4"
        style={{ color: "var(--border)" }}
      >
        BURN RATIO WEIGHTED
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
            const pct = Math.round(item.burn_ratio * 100);
            const barWidth = Math.min(100, Math.max(0, pct));

            return (
              <div
                key={item.region}
                className="py-2"
                style={{
                  borderBottom:
                    i < items.length - 1 ? "1px solid var(--border)" : "none",
                }}
              >
                {/* Top row: rank + name + bar + pct */}
                <div className="flex items-center gap-3">
                  {/* Rank */}
                  <span
                    className="text-xs font-mono tabular-nums shrink-0 w-6"
                    style={{ color: "var(--muted)" }}
                  >
                    {String(i + 1).padStart(2, "0")}.
                  </span>

                  {/* Region name */}
                  <span
                    className="text-xs font-mono uppercase tracking-wider flex-1 truncate"
                    style={{ color: "var(--foreground)" }}
                  >
                    {item.region}
                  </span>

                  {/* Mini bar */}
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
                        backgroundColor: "var(--success-fg)",
                      }}
                    />
                  </div>

                  {/* Percentage */}
                  <span
                    className="text-xs font-mono tabular-nums shrink-0 w-8 text-right"
                    style={{ color: "var(--success-fg)" }}
                  >
                    {pct}%
                  </span>
                </div>

                {/* Sub-line: event count */}
                <p
                  className="text-[10px] font-mono mt-1 ml-9"
                  style={{ color: "var(--muted)" }}
                >
                  · {item.events} {item.events === 1 ? "event" : "events"}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
