export interface PositiveStreakCardProps {
  /** Number of consecutive BURN decisions ending at the most recent event */
  current: number;
  /** Longest consecutive BURN streak observed in the last 7 days */
  longest_7d: number;
}

/**
 * PositiveStreakCard — Server Component
 *
 * Displays consecutive BURN (positive decision) streak counts.
 * Current streak shown in --success-fg green when > 0, muted when 0.
 * Longest 7-day streak always shown in --foreground white.
 *
 * Example props for smoke-test:
 * <PositiveStreakCard current={3} longest_7d={5} />
 * <PositiveStreakCard current={0} longest_7d={4} />
 */
export function PositiveStreakCard({
  current,
  longest_7d,
}: PositiveStreakCardProps) {
  const currentColor =
    current > 0 ? "var(--success-fg)" : "var(--muted)";

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
        className="text-xs uppercase tracking-wider font-mono mb-4"
        style={{ color: "var(--muted)" }}
      >
        POSITIVE STREAK
      </p>

      {/* Two-column layout */}
      <div className="flex gap-6">
        {/* Left: current streak */}
        <div className="flex flex-col gap-1 flex-1">
          <span
            className="text-[10px] font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)" }}
          >
            CURRENT
          </span>
          <span
            className="text-4xl font-mono tabular-nums font-bold leading-none"
            style={{ color: currentColor }}
          >
            {current}
          </span>
          <span
            className="text-[10px] font-mono uppercase"
            style={{ color: "var(--muted)" }}
          >
            CONSECUTIVE BURNS
          </span>
        </div>

        {/* Divider */}
        <div
          style={{
            width: "1px",
            backgroundColor: "var(--border)",
            alignSelf: "stretch",
          }}
        />

        {/* Right: longest streak over 7d */}
        <div className="flex flex-col gap-1 flex-1">
          <span
            className="text-[10px] font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)" }}
          >
            LONGEST · 7D
          </span>
          <span
            className="text-4xl font-mono tabular-nums font-bold leading-none"
            style={{ color: "var(--foreground)" }}
          >
            {longest_7d}
          </span>
          <span
            className="text-[10px] font-mono uppercase"
            style={{ color: "var(--muted)" }}
          >
            BEST RUN
          </span>
        </div>
      </div>
    </div>
  );
}
