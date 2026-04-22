export interface CacheHitRateCardProps {
  /** Number of events served from semantic cache (no LLM call) */
  hits: number;
  /** Total events evaluated during the period */
  total_events: number;
  /**
   * Pre-computed percentage (hits / total_events * 100).
   * Passed in to avoid division-by-zero on the frontend.
   */
  pct: number;
}

/**
 * CacheHitRateCard — Server Component
 *
 * Displays Phase 3 semantic dedup effectiveness over the last 7 days.
 * Large centered percentage number, colored orange when >= 20%, muted otherwise.
 *
 * Example props for smoke-test:
 * <CacheHitRateCard hits={8} total_events={35} pct={22.8} />
 */
export function CacheHitRateCard({
  hits,
  total_events,
  pct,
}: CacheHitRateCardProps) {
  const isGood = pct >= 20;
  const pctDisplay = pct.toFixed(1);

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
        CACHE HIT RATE · 7D
      </p>

      {/* Big number */}
      <div className="flex flex-col items-center gap-2">
        <span
          className="text-4xl font-mono tabular-nums font-bold leading-none"
          style={{ color: isGood ? "var(--primary)" : "var(--muted)" }}
        >
          {pctDisplay}%
        </span>

        {/* Sub-label */}
        <span
          className="text-xs font-mono uppercase tracking-wider"
          style={{ color: "var(--muted)" }}
        >
          {hits} / {total_events} EVENTS DEDUPLICATED
        </span>
      </div>

      {/* Info note */}
      <p
        className="text-[10px] font-mono mt-4 text-center"
        style={{ color: "var(--brand-teal)", lineHeight: "1.4" }}
        title="Phase 3 semantic cache reused verdicts for similar events"
      >
        SEMANTIC CACHE · COSINE &ge; 0.92 · 7-DAY WINDOW
      </p>
    </div>
  );
}
