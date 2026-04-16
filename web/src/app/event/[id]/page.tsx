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
  const styles: Record<string, string> = {
    BURN: "bg-emerald-100 text-emerald-700",
    MINT: "bg-red-100 text-red-700",
    NEUTRAL: "bg-gray-100 text-gray-600",
  };
  return (
    <span
      className={`inline-block rounded-full px-4 py-1.5 text-sm font-semibold uppercase ${styles[decision] ?? styles.NEUTRAL}`}
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
      ? "text-emerald-600"
      : event.final_score <= 4
        ? "text-red-600"
        : "text-gray-600";

  const amountColor =
    event.decision === "BURN"
      ? "text-emerald-600"
      : event.decision === "MINT"
        ? "text-red-600"
        : "text-gray-600";

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      {/* Back link */}
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900 mb-8"
      >
        &larr; Back to all events
      </Link>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <DecisionBadge decision={event.decision} />
          <span className="text-sm text-gray-500">{event.event_source}</span>
          <span className="text-sm text-gray-400">
            {formatDate(event.created_at)}
          </span>
        </div>
        <h1 className="text-2xl font-bold text-gray-900 leading-snug mb-2">
          {event.event_title}
        </h1>
        <a
          href={event.event_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-blue-600 hover:underline break-all"
        >
          View original article &rarr;
        </a>
      </div>

      {/* Score card */}
      <div className="rounded-2xl bg-white border border-gray-200 p-6 mb-8">
        <div className="grid grid-cols-3 gap-6 text-center">
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-1">
              Final score
            </div>
            <div className={`text-3xl font-bold ${scoreColor}`}>
              {event.final_score.toFixed(2)}
            </div>
          </div>
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-1">
              Confidence
            </div>
            <div className="text-3xl font-bold text-gray-900">
              {event.confidence}/10
            </div>
          </div>
          <div>
            <div className="text-xs font-medium uppercase tracking-wide text-gray-500 mb-1">
              Amount
            </div>
            <div className={`text-3xl font-bold ${amountColor}`}>
              {formatAmount(event.amount_crbn)}
            </div>
          </div>
        </div>
      </div>

      {/* Justification */}
      <div className="rounded-2xl bg-white border border-gray-200 p-6 mb-8">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-3">
          AI justification
        </h2>
        <p className="text-gray-700 leading-relaxed whitespace-pre-line">
          {event.justification}
        </p>
      </div>

      {/* On-chain status */}
      <div className="rounded-2xl bg-white border border-gray-200 p-6">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-3">
          On-chain transaction
        </h2>
        {event.tx_hash ? (
          <a
            href={`https://explorer.solana.com/tx/${event.tx_hash}?cluster=devnet`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline font-mono text-sm break-all"
          >
            {event.tx_hash}
          </a>
        ) : (
          <p className="text-gray-400 text-sm">
            Pending on-chain &mdash; transaction not yet submitted
          </p>
        )}
      </div>
    </div>
  );
}
