import Link from "next/link";
import type { TaxonomyEntry } from "@/lib/types";
import { InfoTooltip } from "../InfoTooltip";

export interface TopSectorsCardProps {
  sectors: TaxonomyEntry[];
}

/**
 * TopSectorsCard — Server Component
 *
 * Shows top 8 economic sectors by event count over 7 days.
 * Each row shows rank, canonical sector name, and BURN/MINT split.
 */
export function TopSectorsCard({ sectors }: TopSectorsCardProps) {
  const items = sectors.slice(0, 8);

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
        TOP SECTORS · 7D
        <InfoTooltip text="Top 8 economic sectors (Energy, Mining, Agriculture, Tech, Finance, Pharma, Defense, Fishing, Forestry, Transport, Construction, Water) impacted by on-chain events. Multilingual regex detection. +N = BURN events, −N = MINT events." />
      </p>
      <p
        className="text-[10px] uppercase tracking-wider font-mono mb-4"
        style={{ color: "var(--brand-teal)" }}
      >
        INDUSTRIES IMPACTED
      </p>

      {items.length === 0 ? (
        <div className="flex items-center justify-center py-6">
          <span
            className="text-xs font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)" }}
          >
            NO SECTORS DETECTED · 7D
          </span>
        </div>
      ) : (
        <div>
          {items.map((item, i) => {
            const total = item.burn_count + item.mint_count;
            const posPct = total > 0 ? (item.burn_count / total) * 100 : 0;
            const negPct = total > 0 ? 100 - posPct : 0;
            const baseHref = `/events?sector=${encodeURIComponent(item.name)}&since=7d`;

            return (
              <div
                key={item.name}
                style={{
                  display: "grid",
                  gridTemplateColumns: "28px minmax(110px, 130px) 1fr 100px",
                  alignItems: "center",
                  gap: "12px",
                  paddingTop: "8px",
                  paddingBottom: "8px",
                  borderBottom:
                    i < items.length - 1 ? "1px solid var(--border)" : "none",
                }}
              >
                {/* Col 1 — rank */}
                <span
                  className="text-xs font-mono tabular-nums"
                  style={{ color: "var(--muted)" }}
                >
                  {String(i + 1).padStart(2, "0")}.
                </span>

                {/* Col 2 — sector name (links to all events for that sector) */}
                <Link
                  href={baseHref}
                  className="text-xs font-mono uppercase tracking-wider truncate hover:opacity-80"
                  style={{
                    color: "var(--foreground)",
                    textDecoration: "none",
                    cursor: "pointer",
                  }}
                  title={`See the ${item.count} events tagged ${item.name}`}
                >
                  {item.name}
                </Link>

                {/* Col 3 — stacked BURN/MINT bar (green left, red right) */}
                <Link
                  href={baseHref}
                  title={`See the ${item.count} events tagged ${item.name}`}
                  className="hover:opacity-80"
                  style={{
                    position: "relative",
                    height: "8px",
                    backgroundColor: "var(--cw-bg-2)",
                    overflow: "hidden",
                    cursor: "pointer",
                    display: "block",
                  }}
                >
                  {total > 0 && (
                    <>
                      <div
                        style={{
                          position: "absolute",
                          top: 0,
                          bottom: 0,
                          left: 0,
                          width: `${posPct}%`,
                          backgroundColor: "var(--cw-burn)",
                        }}
                      />
                      <div
                        style={{
                          position: "absolute",
                          top: 0,
                          bottom: 0,
                          right: 0,
                          width: `${negPct}%`,
                          backgroundColor: "var(--cw-mint)",
                        }}
                      />
                    </>
                  )}
                </Link>

                {/* Col 4 — counts (each side filtered) */}
                <div
                  className="font-mono tabular-nums"
                  style={{
                    fontSize: "11px",
                    textAlign: "right",
                    whiteSpace: "nowrap",
                  }}
                >
                  <Link
                    href={`${baseHref}&decision=BURN`}
                    style={{
                      color: "var(--cw-burn)",
                      textDecoration: "none",
                      cursor: "pointer",
                    }}
                    className="hover:opacity-80"
                    title={`See the ${item.burn_count} BURN event(s) tagged ${item.name}`}
                  >
                    +{item.burn_count}
                  </Link>
                  <span style={{ color: "var(--muted)" }}> / </span>
                  <Link
                    href={`${baseHref}&decision=MINT`}
                    style={{
                      color: "var(--cw-mint)",
                      textDecoration: "none",
                      cursor: "pointer",
                    }}
                    className="hover:opacity-80"
                    title={`See the ${item.mint_count} MINT event(s) tagged ${item.name}`}
                  >
                    &#x2212;{item.mint_count}
                  </Link>
                  <span style={{ color: "var(--muted)" }}> ({item.count})</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
