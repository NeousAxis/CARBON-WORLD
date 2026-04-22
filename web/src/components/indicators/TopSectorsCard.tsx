import type { TaxonomyEntry } from "@/lib/types";

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
        <div className="flex flex-col">
          {items.map((item, i) => (
            <div
              key={item.name}
              className="flex items-center gap-3 py-2"
              style={{
                borderBottom:
                  i < items.length - 1 ? "1px solid var(--border)" : "none",
              }}
            >
              {/* Rank */}
              <span
                className="text-xs font-mono tabular-nums shrink-0 w-6"
                style={{ color: "var(--muted)" }}
              >
                {String(i + 1).padStart(2, "0")}.
              </span>

              {/* Sector name */}
              <span
                className="text-xs font-mono uppercase tracking-wider flex-1 truncate"
                style={{ color: "var(--foreground)" }}
              >
                {item.name}
              </span>

              {/* BURN / MINT split + total */}
              <div className="flex items-center gap-1.5 shrink-0 font-mono tabular-nums text-[10px]">
                <span style={{ color: "var(--success-fg)" }}>
                  +{item.burn_count}
                </span>
                <span style={{ color: "var(--muted)" }}>/</span>
                <span style={{ color: "var(--error-fg)" }}>
                  &#8722;{item.mint_count}
                </span>
                <span style={{ color: "var(--muted)" }}>
                  ({item.count})
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
