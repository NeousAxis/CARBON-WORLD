import Link from "next/link";
import type { CarbonEvent } from "@/lib/data";
import { formatAmount } from "@/lib/data";

function formatCompactDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function EventsTable({ events }: { events: CarbonEvent[] }) {
  // Sort by date descending (newest first)
  const sorted = [...events].sort(
    (a, b) =>
      new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* Table header */}
      <div className="px-4 py-2.5 border-b border-gray-200 bg-gray-50/80">
        <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">
          Event Log
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 text-xs text-gray-400 uppercase tracking-wider">
              <th className="text-left py-2 px-3 font-medium">Date</th>
              <th className="text-left py-2 px-3 font-medium">Decision</th>
              <th className="text-left py-2 px-3 font-medium">Event</th>
              <th className="text-left py-2 px-3 font-medium">Source</th>
              <th className="text-right py-2 px-3 font-medium">Score</th>
              <th className="text-right py-2 px-3 font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((event, i) => {
              const isBurn = event.decision === "BURN";
              const isMint = event.decision === "MINT";
              const scoreColor =
                event.final_score >= 6
                  ? "text-emerald-600"
                  : event.final_score <= 4
                    ? "text-red-500"
                    : "text-gray-600";
              const amountColor = isBurn
                ? "text-emerald-600"
                : isMint
                  ? "text-red-500"
                  : "text-gray-500";
              const rowBg = i % 2 === 0 ? "bg-white" : "bg-gray-50/50";

              return (
                <tr
                  key={event.id}
                  className={`${rowBg} border-b border-gray-50 hover:bg-blue-50/40 transition-colors`}
                >
                  <td className="py-2 px-3 text-xs text-gray-500 whitespace-nowrap font-mono tabular-nums">
                    {formatCompactDate(event.created_at)}
                  </td>
                  <td className="py-2 px-3">
                    <span
                      className={`inline-block text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded ${
                        isBurn
                          ? "bg-emerald-50 text-emerald-600"
                          : isMint
                            ? "bg-red-50 text-red-500"
                            : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {event.decision}
                    </span>
                  </td>
                  <td className="py-2 px-3 max-w-[280px]">
                    <Link
                      href={`/event/${event.id}`}
                      className="text-xs text-gray-800 hover:text-blue-600 hover:underline truncate block"
                      title={event.event_title}
                    >
                      {event.event_title}
                    </Link>
                  </td>
                  <td className="py-2 px-3 text-[10px] text-gray-400 uppercase tracking-wider whitespace-nowrap">
                    {event.event_source}
                  </td>
                  <td
                    className={`py-2 px-3 text-right font-mono text-xs font-semibold tabular-nums ${scoreColor}`}
                  >
                    {event.final_score.toFixed(1)}
                  </td>
                  <td
                    className={`py-2 px-3 text-right font-mono text-xs font-semibold tabular-nums whitespace-nowrap ${amountColor}`}
                  >
                    {isMint ? "+" : isBurn ? "-" : ""}
                    {formatAmount(event.amount_crbn)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
