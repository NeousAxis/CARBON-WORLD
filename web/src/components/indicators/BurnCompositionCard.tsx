import type { BurnComposition } from "@/lib/types";
import { InfoTooltip } from "../InfoTooltip";

export interface BurnCompositionCardProps {
  composition: BurnComposition;
  /** Window label, e.g. "7D" or "ALL TIME" */
  windowLabel: string;
}

/**
 * BurnCompositionCard — Server Component
 *
 * Breaks down the BURN events into two subtypes:
 *   - Direct Actions: treaty signed, biome protected, breakthrough deployed
 *     (the strict structural-shift definition — green)
 *   - Editorial Consciousness: credible educational commentary that fosters
 *     progress of consciousness (teal — visually distinct)
 *
 * The "untyped" bucket exists for legacy BURN events whose subtype was never
 * assigned. Once backfill runs and all new events are auto-typed by the
 * pipeline, untyped should stay at 0.
 */
export function BurnCompositionCard({
  composition,
  windowLabel,
}: BurnCompositionCardProps) {
  const { total_burn, direct_action, editorial_consciousness, untyped } = composition;

  // Stacked bar widths — clamped so they sum to ≤ 100 if data is malformed
  const directW = Math.min(100, Math.max(0, direct_action.pct));
  const editorialW = Math.min(100, Math.max(0, editorial_consciousness.pct));
  const untypedW = Math.min(100, Math.max(0, untyped.pct));

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
        style={{ color: "var(--brand-teal)" }}
      >
        BURN COMPOSITION · {windowLabel}
        <InfoTooltip text="Breakdown of BURN events by subtype. DIRECT ACTION = concrete on-the-ground act (treaty signed, biome protected, citizen victory). EDITORIAL CONSCIOUSNESS = editorial coverage amplifying public awareness (Mongabay, Yale E360, etc.). UNTYPED = older events with no subtype assigned." />
      </p>

      {total_burn === 0 ? (
        <p
          className="text-xs font-mono mt-2"
          style={{ color: "var(--muted)" }}
        >
          No BURN events yet in this window.
        </p>
      ) : (
        <>
          {/* Stacked bar */}
          <div
            className="flex w-full overflow-hidden"
            style={{ height: "8px", backgroundColor: "var(--border)" }}
          >
            {directW > 0 && (
              <div
                style={{
                  width: `${directW}%`,
                  backgroundColor: "var(--success-fg)",
                  height: "100%",
                }}
              />
            )}
            {editorialW > 0 && (
              <div
                style={{
                  width: `${editorialW}%`,
                  backgroundColor: "var(--brand-teal)",
                  height: "100%",
                }}
              />
            )}
            {untypedW > 0 && (
              <div
                style={{
                  width: `${untypedW}%`,
                  backgroundColor: "var(--muted)",
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
                DIRECT ACTIONS {direct_action.count} · {direct_action.pct}%
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span
                style={{
                  width: "8px",
                  height: "8px",
                  backgroundColor: "var(--brand-teal)",
                  display: "inline-block",
                  flexShrink: 0,
                }}
              />
              <span
                className="text-xs font-mono tabular-nums"
                style={{ color: "var(--muted)" }}
              >
                EDITORIAL CONSCIOUSNESS {editorial_consciousness.count} · {editorial_consciousness.pct}%
              </span>
            </div>
            {untyped.count > 0 && (
              <div className="flex items-center gap-2">
                <span
                  style={{
                    width: "8px",
                    height: "8px",
                    backgroundColor: "var(--muted)",
                    display: "inline-block",
                    flexShrink: 0,
                  }}
                />
                <span
                  className="text-xs font-mono tabular-nums"
                  style={{ color: "var(--muted)" }}
                >
                  LEGACY (UNTYPED) {untyped.count} · {untyped.pct}%
                </span>
              </div>
            )}
          </div>

          {/* Footer */}
          <p
            className="text-xs font-mono tabular-nums mt-3"
            style={{ color: "var(--muted)" }}
          >
            {total_burn} BURN total
          </p>
        </>
      )}
    </div>
  );
}
