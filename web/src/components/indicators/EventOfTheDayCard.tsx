import Link from "next/link";
import { formatAmount } from "./formatAmount";
import { InfoTooltip } from "../InfoTooltip";

export interface EventOfTheDayEvent {
  id: number;
  event_title: string;
  decision: "BURN" | "MINT" | "NEUTRAL";
  amount_crbn: number;
  final_score: number;
  confidence?: number;
  country?: string | null;
  region?: string | null;
  created_at?: string;
}

export interface EventOfTheDayCardProps {
  event: EventOfTheDayEvent | null;
}

/**
 * EventOfTheDayCard — Server Component
 *
 * Featured card for the highest-impact event of the current 24h window.
 * Larger visual weight than the other indicator cards.
 *
 * Example props for smoke-test:
 * <EventOfTheDayCard event={{
 *   id: 42,
 *   event_title: "Brazil ratifies Amazon protection treaty covering 12M hectares",
 *   decision: "BURN",
 *   amount_crbn: 750000,
 *   final_score: 6.21,
 *   confidence: 8,
 *   country: "Brazil",
 *   region: "Latin America",
 *   created_at: "2026-04-21T15:30:00Z",
 * }} />
 */
export function EventOfTheDayCard({ event }: EventOfTheDayCardProps) {
  const isBurn = event?.decision === "BURN";
  const isMint = event?.decision === "MINT";

  const badgeStyle = isBurn
    ? {
        backgroundColor: "var(--success-bg)",
        color: "var(--success-fg)",
        border: "1px solid var(--success-fg)",
      }
    : isMint
    ? {
        backgroundColor: "var(--error-bg)",
        color: "var(--error-fg)",
        border: "1px solid var(--error-fg)",
      }
    : {
        backgroundColor: "var(--warning-bg)",
        color: "var(--warning-fg)",
        border: "1px solid var(--warning-fg)",
      };

  const accentColor = isBurn
    ? "var(--success-fg)"
    : isMint
    ? "var(--error-fg)"
    : "var(--warning-fg)";

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
        EVENT OF THE DAY · 24H
        <InfoTooltip text="The most impactful event of the last 24 hours, ranked by absolute final score. If no event today, falls back to the last 7 days so the card is never empty. Click to see the full ethical analysis." />
      </p>

      {event === null ? (
        <div className="flex items-center justify-center py-8">
          <span
            className="text-xs font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)" }}
          >
            NO EVENT TODAY
          </span>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {/* Badge row: decision + geo */}
          <div className="flex items-center gap-3 flex-wrap">
            <span
              className="text-xs font-mono uppercase tracking-wider px-2 py-1"
              style={badgeStyle}
            >
              {event.decision}
            </span>

            {(event.country || event.region) && (
              <span
                className="text-xs font-mono uppercase tracking-wider"
                style={{ color: "var(--muted)" }}
              >
                {[event.country, event.region]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
            )}
          </div>

          {/* Event title */}
          <p
            className="text-base font-mono leading-snug"
            style={{
              color: "var(--foreground)",
              display: "-webkit-box",
              WebkitLineClamp: 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {event.event_title}
          </p>

          {/* Stats row */}
          <div className="flex items-center gap-4 flex-wrap">
            <span
              className="text-xs font-mono tabular-nums"
              style={{ color: accentColor }}
            >
              SCORE: {event.final_score.toFixed(2)}
            </span>
            <span
              className="text-xs font-mono tabular-nums"
              style={{ color: accentColor }}
            >
              AMOUNT: {formatAmount(event.amount_crbn)} CBWD
            </span>
            {event.confidence !== undefined && (
              <span
                className="text-xs font-mono tabular-nums"
                style={{ color: "var(--muted)" }}
              >
                CONFIDENCE: {event.confidence}/10
              </span>
            )}
          </div>

          {/* View details link */}
          <div>
            <Link
              href={`/event/${event.id}`}
              className="text-xs font-mono uppercase tracking-wider"
              style={{ color: "var(--primary)" }}
            >
              VIEW DETAILS →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
