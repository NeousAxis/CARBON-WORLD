import Link from "next/link";
import {
  getEvents,
  getStats,
  formatAmount,
  formatDate,
} from "@/lib/data";

function DecisionBadge({ decision }: { decision: string }) {
  const styles: Record<string, string> = {
    BURN: "bg-emerald-100 text-emerald-700",
    MINT: "bg-red-100 text-red-700",
    NEUTRAL: "bg-gray-100 text-gray-600",
  };
  return (
    <span
      className={`inline-block rounded-full px-3 py-1 text-xs font-semibold uppercase ${styles[decision] ?? styles.NEUTRAL}`}
    >
      {decision}
    </span>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="flex flex-col items-center gap-1">
      <span className="text-xs font-medium uppercase tracking-wide text-gray-500">
        {label}
      </span>
      <span className={`text-2xl font-bold ${color ?? "text-gray-900"}`}>
        {value}
      </span>
    </div>
  );
}

export default function Home() {
  const events = getEvents();
  const stats = getStats();

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      {/* Hero */}
      <section className="text-center mb-12">
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 mb-3">
          CARBON WORLD
        </h1>
        <p className="text-lg text-gray-600 max-w-xl mx-auto">
          AI-powered ethical scoring of human decisions. Every government action
          is analyzed through 7 ethical frameworks &mdash; and the CBWD token
          supply adjusts accordingly.
        </p>
      </section>

      {/* Stats bar */}
      <section className="mb-12 rounded-2xl bg-white border border-gray-200 p-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <StatCard label="Events analyzed" value={String(stats.totalEvents)} />
          <StatCard
            label="Total burned"
            value={formatAmount(stats.totalBurned)}
            color="text-emerald-600"
          />
          <StatCard
            label="Total minted"
            value={formatAmount(stats.totalMinted)}
            color="text-red-600"
          />
          <StatCard
            label="Net supply change"
            value={
              (stats.netSupplyChange >= 0 ? "+" : "") +
              formatAmount(Math.abs(stats.netSupplyChange))
            }
            color={
              stats.netSupplyChange > 0 ? "text-red-600" : "text-emerald-600"
            }
          />
        </div>
      </section>

      {/* Events list */}
      <section>
        <h2 className="text-xl font-semibold text-gray-900 mb-6">
          Recent decisions
        </h2>
        <div className="space-y-4">
          {events.map((event) => (
            <Link
              key={event.id}
              href={`/event/${event.id}`}
              className="block rounded-2xl bg-white border border-gray-200 p-5 hover:border-gray-300 hover:shadow-sm transition-all"
            >
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <DecisionBadge decision={event.decision} />
                    <span className="text-xs text-gray-500">
                      {event.event_source}
                    </span>
                    <span className="text-xs text-gray-400">
                      {formatDate(event.created_at)}
                    </span>
                  </div>
                  <h3 className="text-base font-medium text-gray-900 leading-snug">
                    {event.event_title}
                  </h3>
                </div>
                <div className="flex items-center gap-4 text-sm shrink-0">
                  <div className="text-center">
                    <div className="text-xs text-gray-500">Score</div>
                    <div className="font-semibold">
                      {event.final_score.toFixed(1)}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-gray-500">Confidence</div>
                    <div className="font-semibold">{event.confidence}/10</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-gray-500">Amount</div>
                    <div
                      className={`font-semibold ${
                        event.decision === "BURN"
                          ? "text-emerald-600"
                          : event.decision === "MINT"
                            ? "text-red-600"
                            : "text-gray-600"
                      }`}
                    >
                      {formatAmount(event.amount_crbn)}
                    </div>
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
