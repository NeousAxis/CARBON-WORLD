import Link from "next/link";
import { formatAmount } from "./formatAmount";

export interface TopCountriesMintCardProps {
  countries: Array<{ country: string; count: number; total_amount: number }>;
}

/**
 * TopCountriesMintCard — Server Component
 *
 * Shows top 5 countries with most MINT decisions (institutional regressions) over 7 days.
 *
 * Example props for smoke-test:
 * <TopCountriesMintCard countries={[
 *   { country: "USA", count: 5, total_amount: 12500000 },
 *   { country: "China", count: 3, total_amount: 7200000 },
 * ]} />
 */
export function TopCountriesMintCard({ countries }: TopCountriesMintCardProps) {
  const items = countries.slice(0, 5);

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
        TOP COUNTRIES · MINT · 7D
      </p>
      <p
        className="text-[10px] uppercase tracking-wider font-mono mb-4"
        style={{ color: "var(--brand-teal)" }}
      >
        INSTITUTIONAL REGRESSIONS
      </p>

      {items.length === 0 ? (
        <div className="flex items-center justify-center py-6">
          <span
            className="text-xs font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)" }}
          >
            NO DATA YET
          </span>
        </div>
      ) : (
        <div className="flex flex-col">
          {items.map((item, i) => (
            <Link
              key={item.country}
              href={`/events?country=${encodeURIComponent(item.country)}&decision=MINT&since=7d`}
              className="flex items-center gap-3 py-2 hover:opacity-80"
              style={{
                borderBottom:
                  i < items.length - 1 ? "1px solid var(--border)" : "none",
                cursor: "pointer",
              }}
              title={`See the ${item.count} MINT events from ${item.country}`}
            >
              {/* Rank */}
              <span
                className="text-xs font-mono tabular-nums shrink-0 w-6"
                style={{ color: "var(--muted)" }}
              >
                {String(i + 1).padStart(2, "0")}.
              </span>

              {/* Country name */}
              <span
                className="text-xs font-mono uppercase tracking-wider flex-1 truncate"
                style={{ color: "var(--foreground)" }}
              >
                {item.country}
              </span>

              {/* Count + amount */}
              <div className="flex items-center gap-2 shrink-0">
                <span
                  className="text-[10px] font-mono tabular-nums"
                  style={{ color: "var(--error-fg)" }}
                >
                  {item.count}&times;
                </span>
                <span
                  className="text-xs font-mono tabular-nums"
                  style={{ color: "var(--error-fg)" }}
                >
                  {formatAmount(item.total_amount)} CBWD
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
