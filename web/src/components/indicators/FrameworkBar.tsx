import Link from "next/link";

export interface FrameworkBarProps {
  /** Short code displayed in col 1 — e.g. "SDG", "UDHR", "PB" */
  code: string;
  /** Long name shown in the bar tooltip */
  name: string;
  /** Number of positive (BURN) citations over the window */
  positive: number;
  /** Number of negative (MINT) citations over the window */
  negative: number;
}

/**
 * FrameworkBar — Server Component
 *
 * Single row in the FrameworkActivityCard.
 * Grid: 80px | 1fr | 80px
 *   Col 1 — code label (uppercase mono)
 *   Col 2 — stacked bar: green (positive) left, red (negative) right
 *   Col 3 — "+N / −N" counts, right-aligned mono
 *
 * Empty case (total === 0): full-width grey track, counts show "+0 / −0".
 *
 * Note: the minus sign in the count is U+2212 (−), not a hyphen.
 *
 * Example:
 *   <FrameworkBar code="SDG" name="UN Sustainable Development Goals (17)" positive={16} negative={19} />
 */
export function FrameworkBar({
  code,
  name,
  positive,
  negative,
}: FrameworkBarProps) {
  const total = positive + negative;
  const posPct = total > 0 ? (positive / total) * 100 : 0;
  const negPct = total > 0 ? 100 - posPct : 0;

  // Three independent links: label+bar → all events for this framework (any
  // polarity), +N → positive (BURN) only, −N → negative (MINT) only. We keep
  // them inside a grid and use border-bottom hover to hint clickability.
  const baseHref = `/events?framework=${encodeURIComponent(code)}&since=7d`;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "80px 1fr 80px",
        alignItems: "center",
        gap: "12px",
        paddingTop: "8px",
        paddingBottom: "8px",
      }}
    >
      {/* Col 1 — code label (links to all polarities) */}
      <Link
        href={baseHref}
        className="font-mono text-xs uppercase hover:opacity-80"
        style={{ color: "var(--cw-fg-1)", textDecoration: "none", cursor: "pointer" }}
        title={`See all events touching ${name}`}
      >
        {code}
      </Link>

      {/* Col 2 — stacked bar (links to all polarities) */}
      <Link
        href={baseHref}
        title={`See all events touching ${name}`}
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

      {/* Col 3 — counts (each side is its own filtered link) */}
      <div
        className="font-mono tabular-nums"
        style={{
          fontSize: "11px",
          textAlign: "right",
          whiteSpace: "nowrap",
        }}
      >
        <Link
          href={`${baseHref}&framework_polarity=positive`}
          style={{ color: "var(--cw-burn)", textDecoration: "none", cursor: "pointer" }}
          className="hover:opacity-80"
          title={`See the ${positive} BURN events for ${code}`}
        >
          +{positive}
        </Link>
        <span style={{ color: "var(--cw-fg-3)" }}> / </span>
        <Link
          href={`${baseHref}&framework_polarity=negative`}
          style={{ color: "var(--cw-mint)", textDecoration: "none", cursor: "pointer" }}
          className="hover:opacity-80"
          title={`See the ${negative} MINT events for ${code}`}
        >
          &#x2212;{negative}
        </Link>
      </div>
    </div>
  );
}
