import type { MintComposition } from "@/lib/types";
import { InfoTooltip } from "../InfoTooltip";

export interface MintCompositionCardProps {
  composition: MintComposition;
  /** Window label, e.g. "7D" or "ALL TIME" */
  windowLabel: string;
}

/**
 * MintCompositionCard — Server Component
 *
 * Mirror of BurnCompositionCard for negative decisions. Breaks down the
 * MINT events into two subtypes:
 *   - Direct Actions: regulatory rollback, fossil expansion, rights repealed
 *     (the strict structural-regression definition — red)
 *   - Editorial Alarm: credible educational outlet sounding the alarm on a
 *     decline that has no single decision to point at (orange — distinct
 *     from direct red, signals "warning" rather than "destruction")
 *
 * The "untyped" bucket exists for legacy MINT events whose subtype was never
 * assigned. Once backfill runs and all new events are auto-typed, untyped
 * should stay at 0.
 */
export function MintCompositionCard({
  composition,
  windowLabel,
}: MintCompositionCardProps) {
  const { total_mint, direct_action, editorial_alarm, untyped } = composition;

  const directW = Math.min(100, Math.max(0, direct_action.pct));
  const editorialW = Math.min(100, Math.max(0, editorial_alarm.pct));
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
        MINT COMPOSITION · {windowLabel}
        <InfoTooltip text="Découpage des events MINT par sous-type : DIRECT ACTION (régression institutionnelle directe : décret fossile, atteinte aux droits, etc.) vs EDITORIAL ALARM (article alertant sur un enjeu sans décision concrète) vs UNTYPED (events anciens)." />
      </p>

      {total_mint === 0 ? (
        <p
          className="text-xs font-mono mt-2"
          style={{ color: "var(--muted)" }}
        >
          No MINT events yet in this window.
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
                  backgroundColor: "#FF5C33",
                  height: "100%",
                }}
              />
            )}
            {editorialW > 0 && (
              <div
                style={{
                  width: `${editorialW}%`,
                  backgroundColor: "#FF8400",
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
                  backgroundColor: "#FF5C33",
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
                  backgroundColor: "#FF8400",
                  display: "inline-block",
                  flexShrink: 0,
                }}
              />
              <span
                className="text-xs font-mono tabular-nums"
                style={{ color: "var(--muted)" }}
              >
                EDITORIAL ALARM {editorial_alarm.count} · {editorial_alarm.pct}%
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
            {total_mint} MINT total
          </p>
        </>
      )}
    </div>
  );
}
