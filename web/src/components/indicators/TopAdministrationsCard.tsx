import Link from "next/link";

export interface TopAdministrationsCardProps {
  administrations: Array<{
    administration: string;
    burn_ratio: number;
    events: number;
  }>;
}

/**
 * Converts "France-Renaissance" → "FRANCE / RENAISSANCE"
 * Handles multi-word segments joined by hyphens.
 */
function formatAdministration(raw: string): string {
  return raw
    .split("-")
    .map((part) => part.toUpperCase())
    .join(" / ");
}

/**
 * TopAdministrationsCard — Server Component
 *
 * Shows top 10 political administrations ranked by BURN ratio over 7 days.
 * Denser list than regions (up to 10 items, smaller sub-lines).
 *
 * Example props for smoke-test:
 * <TopAdministrationsCard administrations={[
 *   { administration: "France-Renaissance", burn_ratio: 0.75, events: 4 },
 *   { administration: "Germany-SPD", burn_ratio: 0.68, events: 3 },
 * ]} />
 */
export function TopAdministrationsCard({
  administrations,
}: TopAdministrationsCardProps) {
  const items = administrations.slice(0, 10);

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
        TOP ADMINISTRATIONS · SUSTAINABLE · 7D
      </p>
      <p
        className="text-[10px] uppercase tracking-wider font-mono mb-4"
        style={{ color: "var(--brand-teal)" }}
      >
        BURN RATIO WEIGHTED
      </p>

      {items.length === 0 ? (
        <div className="flex items-center justify-center py-6">
          <span
            className="text-xs font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)" }}
          >
            NO ADMINISTRATION DATA YET
          </span>
        </div>
      ) : (
        <div className="flex flex-col">
          {items.map((item, i) => {
            const pct = Math.round(item.burn_ratio * 100);
            const barWidth = Math.min(100, Math.max(0, pct));

            return (
              <Link
                key={item.administration}
                href={`/events?administration=${encodeURIComponent(item.administration)}&since=7d`}
                className="block py-1.5 hover:opacity-80"
                style={{
                  borderBottom:
                    i < items.length - 1 ? "1px solid var(--border)" : "none",
                  cursor: "pointer",
                }}
                title={`See the ${item.events} events tracked under ${formatAdministration(item.administration)}`}
              >
                {/* Top row */}
                <div className="flex items-center gap-2">
                  {/* Rank */}
                  <span
                    className="text-[10px] font-mono tabular-nums shrink-0 w-6"
                    style={{ color: "var(--muted)" }}
                  >
                    {String(i + 1).padStart(2, "0")}.
                  </span>

                  {/* Administration name */}
                  <span
                    className="text-[10px] font-mono uppercase tracking-wider flex-1 truncate"
                    style={{ color: "var(--foreground)" }}
                  >
                    {formatAdministration(item.administration)}
                  </span>

                  {/* Mini bar */}
                  <div
                    style={{
                      width: "48px",
                      height: "3px",
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

                  {/* Pct + count */}
                  <span
                    className="text-[10px] font-mono tabular-nums shrink-0"
                    style={{ color: "var(--success-fg)" }}
                  >
                    {pct}%
                  </span>
                  <span
                    className="text-[10px] font-mono tabular-nums shrink-0"
                    style={{ color: "var(--muted)" }}
                  >
                    · {item.events}
                  </span>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
