import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getEvents,
  getEventById,
  formatAmount,
  formatDate,
  parseJustification,
} from "@/lib/data";

// Pre-generate all event pages at build time
export function generateStaticParams() {
  return getEvents().map((e) => ({ id: String(e.id) }));
}

function DecisionBadge({ decision }: { decision: string }) {
  const styles: Record<string, { bg: string; color: string }> = {
    BURN: { bg: "#222924", color: "#B6FFCE" },
    MINT: { bg: "#24100B", color: "#FF5C33" },
    NEUTRAL: { bg: "#2E2E2E", color: "#B8B9B6" },
  };
  const s = styles[decision] ?? styles.NEUTRAL;
  return (
    <span
      className="inline-block px-3 py-1 sm:px-4 sm:py-1.5 text-xs sm:text-sm font-semibold uppercase"
      style={{ backgroundColor: s.bg, color: s.color }}
    >
      {decision}
    </span>
  );
}

function truncateSig(sig: string): string {
  return `${sig.slice(0, 8)}…${sig.slice(-8)}`;
}

export default async function EventPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const event = getEventById(Number(id));

  if (!event) {
    notFound();
  }

  const { reverseInfo, cleanText } = parseJustification(event.justification);

  const scoreColor =
    event.final_score >= 6
      ? "#B6FFCE"
      : event.final_score <= 4
        ? "#FF5C33"
        : "#B8B9B6";

  const amountColor =
    event.decision === "BURN"
      ? "#B6FFCE"
      : event.decision === "MINT"
        ? "#FF5C33"
        : "#B8B9B6";

  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-6 sm:py-12" style={{ backgroundColor: "#111111" }}>
      {/* Back link */}
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm hover:opacity-80 mb-6 sm:mb-8"
        style={{ color: "#B8B9B6" }}
      >
        &larr; Back to all events
      </Link>

      {/* Header */}
      <div className="mb-6 sm:mb-8">
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-3 sm:mb-4">
          <DecisionBadge decision={event.decision} />
          <span className="text-xs sm:text-sm" style={{ color: "#B8B9B6" }}>{event.event_source}</span>
          <span className="text-xs sm:text-sm" style={{ color: "#B8B9B6" }}>
            {formatDate(event.created_at)}
          </span>
        </div>
        <h1 className="text-xl sm:text-2xl font-bold leading-snug mb-2" style={{ color: "#FFFFFF" }}>
          {event.event_title}
        </h1>
        <a
          href={event.event_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm hover:underline break-all"
          style={{ color: "#FF8400" }}
        >
          View original article &rarr;
        </a>
      </div>

      {/* Reversed banner — only when the event has been corrected post-hoc */}
      {reverseInfo && (
        <div
          className="p-4 sm:p-5 mb-6 sm:mb-8"
          style={{
            backgroundColor: "#2A1F0A",
            border: "1px solid #FF8400",
          }}
        >
          <div className="flex items-center gap-2 mb-3">
            <span
              className="inline-block px-2 py-0.5 text-xs font-bold uppercase tracking-wide"
              style={{ backgroundColor: "#FF8400", color: "#111111" }}
            >
              Reversed
            </span>
            <span className="text-xs sm:text-sm" style={{ color: "#B8B9B6" }}>
              {reverseInfo.date}
            </span>
          </div>
          <p className="text-sm sm:text-base leading-relaxed mb-3" style={{ color: "#FFFFFF" }}>
            {reverseInfo.reason}
          </p>
          <div className="text-xs sm:text-sm" style={{ color: "#B8B9B6" }}>
            Original <span style={{ color: "#FF5C33" }}>{reverseInfo.originalDecision}</span> (
            <a
              href={`https://explorer.solana.com/tx/${reverseInfo.originalTx}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono hover:underline"
              style={{ color: "#FF8400" }}
            >
              {truncateSig(reverseInfo.originalTx)}
            </a>
            ) offset by <span style={{ color: "#B6FFCE" }}>{reverseInfo.reverseDecision}</span> (
            <a
              href={`https://explorer.solana.com/tx/${reverseInfo.reverseTx}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono hover:underline"
              style={{ color: "#FF8400" }}
            >
              {truncateSig(reverseInfo.reverseTx)}
            </a>
            ) — net supply impact: 0.
          </div>
        </div>
      )}

      {/* Score card */}
      <div
        className="p-4 sm:p-6 mb-6 sm:mb-8"
        style={{
          backgroundColor: "#1A1A1A",
          border: "1px solid #2E2E2E",
          boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
        }}
      >
        <div className="grid grid-cols-3 gap-3 sm:gap-6 text-center">
          <div>
            <div className="text-[10px] sm:text-xs font-medium uppercase tracking-wide mb-1" style={{ color: "#B8B9B6" }}>
              Final score
            </div>
            <div className="text-2xl sm:text-3xl font-bold font-mono" style={{ color: scoreColor }}>
              {event.final_score.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-[10px] sm:text-xs font-medium uppercase tracking-wide mb-1" style={{ color: "#B8B9B6" }}>
              Confidence
            </div>
            <div className="text-2xl sm:text-3xl font-bold font-mono" style={{ color: "#FFFFFF" }}>
              {event.confidence}/10
            </div>
          </div>
          <div>
            <div className="text-[10px] sm:text-xs font-medium uppercase tracking-wide mb-1" style={{ color: "#B8B9B6" }}>
              Amount
            </div>
            <div className="text-2xl sm:text-3xl font-bold font-mono" style={{ color: amountColor }}>
              {formatAmount(event.amount_crbn)}
            </div>
          </div>
        </div>
      </div>

      {/* Justification */}
      {cleanText && (
        <div
          className="p-4 sm:p-6 mb-6 sm:mb-8"
          style={{
            backgroundColor: "#1A1A1A",
            border: "1px solid #2E2E2E",
            boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
          }}
        >
          <h2 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: "#B8B9B6" }}>
            AI justification
          </h2>
          <p className="leading-relaxed whitespace-pre-line text-sm sm:text-base" style={{ color: "#B8B9B6" }}>
            {cleanText}
          </p>
        </div>
      )}

      {/* On-chain status */}
      <div
        className="p-4 sm:p-6"
        style={{
          backgroundColor: "#1A1A1A",
          border: "1px solid #2E2E2E",
          boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
        }}
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: "#B8B9B6" }}>
          On-chain transaction{reverseInfo ? "s" : ""}
        </h2>
        {reverseInfo ? (
          <div className="space-y-2 text-xs sm:text-sm">
            <div>
              <span className="mr-2 uppercase tracking-wide" style={{ color: "#B8B9B6" }}>
                Original
              </span>
              <a
                href={`https://explorer.solana.com/tx/${reverseInfo.originalTx}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono hover:underline break-all"
                style={{ color: "#FF8400" }}
              >
                {reverseInfo.originalTx}
              </a>
            </div>
            <div>
              <span className="mr-2 uppercase tracking-wide" style={{ color: "#B8B9B6" }}>
                Reverse
              </span>
              <a
                href={`https://explorer.solana.com/tx/${reverseInfo.reverseTx}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono hover:underline break-all"
                style={{ color: "#FF8400" }}
              >
                {reverseInfo.reverseTx}
              </a>
            </div>
          </div>
        ) : event.tx_hash ? (
          <a
            href={`https://explorer.solana.com/tx/${event.tx_hash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline font-mono text-xs sm:text-sm break-all"
            style={{ color: "#FF8400" }}
          >
            {event.tx_hash}
          </a>
        ) : (
          <p className="text-sm" style={{ color: "#B8B9B6" }}>
            Pending on-chain &mdash; transaction not yet submitted
          </p>
        )}
      </div>
    </div>
  );
}
