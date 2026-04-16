import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getEvents,
  getEventById,
  formatAmount,
  formatDate,
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
      className="inline-block px-4 py-1.5 text-sm font-semibold uppercase"
      style={{ backgroundColor: s.bg, color: s.color }}
    >
      {decision}
    </span>
  );
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
    <div className="mx-auto max-w-3xl px-6 py-12" style={{ backgroundColor: "#111111" }}>
      {/* Back link */}
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm hover:opacity-80 mb-8"
        style={{ color: "#B8B9B6" }}
      >
        &larr; Back to all events
      </Link>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <DecisionBadge decision={event.decision} />
          <span className="text-sm" style={{ color: "#B8B9B6" }}>{event.event_source}</span>
          <span className="text-sm" style={{ color: "#B8B9B6" }}>
            {formatDate(event.created_at)}
          </span>
        </div>
        <h1 className="text-2xl font-bold leading-snug mb-2" style={{ color: "#FFFFFF" }}>
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

      {/* Score card */}
      <div
        className="p-6 mb-8"
        style={{
          backgroundColor: "#1A1A1A",
          border: "1px solid #2E2E2E",
          boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
        }}
      >
        <div className="grid grid-cols-3 gap-6 text-center">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide mb-1" style={{ color: "#B8B9B6" }}>
              Final score
            </div>
            <div className="text-3xl font-bold font-mono" style={{ color: scoreColor }}>
              {event.final_score.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium uppercase tracking-wide mb-1" style={{ color: "#B8B9B6" }}>
              Confidence
            </div>
            <div className="text-3xl font-bold font-mono" style={{ color: "#FFFFFF" }}>
              {event.confidence}/10
            </div>
          </div>
          <div>
            <div className="text-xs font-medium uppercase tracking-wide mb-1" style={{ color: "#B8B9B6" }}>
              Amount
            </div>
            <div className="text-3xl font-bold font-mono" style={{ color: amountColor }}>
              {formatAmount(event.amount_crbn)}
            </div>
          </div>
        </div>
      </div>

      {/* Justification */}
      <div
        className="p-6 mb-8"
        style={{
          backgroundColor: "#1A1A1A",
          border: "1px solid #2E2E2E",
          boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
        }}
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: "#B8B9B6" }}>
          AI justification
        </h2>
        <p className="leading-relaxed whitespace-pre-line" style={{ color: "#B8B9B6" }}>
          {event.justification}
        </p>
      </div>

      {/* On-chain status */}
      <div
        className="p-6"
        style={{
          backgroundColor: "#1A1A1A",
          border: "1px solid #2E2E2E",
          boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
        }}
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide mb-3" style={{ color: "#B8B9B6" }}>
          On-chain transaction
        </h2>
        {event.tx_hash ? (
          <a
            href={`https://explorer.solana.com/tx/${event.tx_hash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:underline font-mono text-sm break-all"
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
