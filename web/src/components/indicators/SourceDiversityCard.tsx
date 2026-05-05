import { InfoTooltip } from "../InfoTooltip";

export interface SourceDiversityCardProps {
  /** Percentage of niche/low-volume sources (0-100) */
  niche_pct: number;
  /** Percentage of mainstream sources (0-100) */
  mainstream_pct: number;
  /** Number of distinct sources that contributed at least one article */
  total_sources_used: number;
  /** Total articles processed (after source-cap) */
  articles_processed: number;
}

/**
 * SourceDiversityCard — Server Component
 *
 * Shows niche vs mainstream source breakdown over the last 7 days.
 * Stacked horizontal bar: niche (--success-fg green) + mainstream (--primary orange).
 *
 * Example props for smoke-test:
 * <SourceDiversityCard niche_pct={68} mainstream_pct={32} total_sources_used={42} articles_processed={220} />
 */
export function SourceDiversityCard({
  niche_pct,
  mainstream_pct,
  total_sources_used,
  articles_processed,
}: SourceDiversityCardProps) {
  // Clamp to avoid layout overflow when values don't sum to exactly 100
  const nicheW = Math.min(100, Math.max(0, niche_pct));
  const mainstreamW = Math.min(100, Math.max(0, mainstream_pct));

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
        className="text-xs uppercase tracking-wider font-mono mb-3"
        style={{ color: "var(--muted)" }}
      >
        SOURCE DIVERSITY · 7D
        <InfoTooltip text="Diversity of the pipeline's sourcing. NICHE = sources with ≤3 events over 7 days (regional press, NGOs, blogs). MAINSTREAM = sources with >3 events (Le Monde, The Guardian, etc.). The higher the NICHE share, the more local signals the pipeline picks up that mainstream media miss." />
      </p>

      {/* Stacked bar */}
      <div
        className="flex w-full overflow-hidden"
        style={{ height: "8px", backgroundColor: "var(--border)" }}
      >
        {nicheW > 0 && (
          <div
            style={{
              width: `${nicheW}%`,
              backgroundColor: "var(--success-fg)",
              height: "100%",
            }}
          />
        )}
        {mainstreamW > 0 && (
          <div
            style={{
              width: `${mainstreamW}%`,
              backgroundColor: "var(--primary)",
              height: "100%",
            }}
          />
        )}
      </div>

      {/* Legend */}
      <div className="flex flex-col gap-1 mt-2">
        <div className="flex items-center gap-2">
          <span
            style={{
              width: "8px",
              height: "8px",
              backgroundColor: "var(--success-fg)",
              display: "inline-block",
              flexShrink: 0,
            }}
          />
          <span
            className="text-xs font-mono tabular-nums"
            style={{ color: "var(--muted)" }}
          >
            NICHE {niche_pct}%
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span
            style={{
              width: "8px",
              height: "8px",
              backgroundColor: "var(--primary)",
              display: "inline-block",
              flexShrink: 0,
            }}
          />
          <span
            className="text-xs font-mono tabular-nums"
            style={{ color: "var(--muted)" }}
          >
            MAINSTREAM {mainstream_pct}%
          </span>
        </div>
      </div>

      {/* Footer stat */}
      <p
        className="text-xs font-mono tabular-nums mt-3"
        style={{ color: "var(--muted)" }}
      >
        {total_sources_used} sources · {articles_processed} articles
      </p>
    </div>
  );
}
