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
    <div
      className="overflow-hidden"
      style={{
        backgroundColor: "#1A1A1A",
        border: "1px solid #2E2E2E",
        boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
      }}
    >
      {/* Table header */}
      <div className="px-4 py-2.5" style={{ borderBottom: "1px solid #2E2E2E", backgroundColor: "#2E2E2E" }}>
        <span className="text-xs font-medium uppercase tracking-wider" style={{ color: "#B8B9B6" }}>
          Event Log
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs uppercase tracking-wider" style={{ borderBottom: "1px solid #2E2E2E", color: "#B8B9B6" }}>
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
                  ? "#B6FFCE"
                  : event.final_score <= 4
                    ? "#FF5C33"
                    : "#B8B9B6";
              const amountColor = isBurn
                ? "#B6FFCE"
                : isMint
                  ? "#FF5C33"
                  : "#B8B9B6";
              const rowBg = i % 2 === 0 ? "#1A1A1A" : "#111111";

              return (
                <tr
                  key={event.id}
                  style={{ backgroundColor: rowBg, borderBottom: "1px solid #2E2E2E" }}
                  className="hover:opacity-90 transition-colors"
                >
                  <td className="py-2 px-3 text-xs whitespace-nowrap font-mono tabular-nums" style={{ color: "#B8B9B6" }}>
                    {formatCompactDate(event.created_at)}
                  </td>
                  <td className="py-2 px-3">
                    <span
                      className="inline-block text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5"
                      style={{
                        backgroundColor: isBurn ? "#222924" : isMint ? "#24100B" : "#2E2E2E",
                        color: isBurn ? "#B6FFCE" : isMint ? "#FF5C33" : "#B8B9B6",
                      }}
                    >
                      {event.decision}
                    </span>
                  </td>
                  <td className="py-2 px-3 max-w-[280px]">
                    <Link
                      href={`/event/${event.id}`}
                      className="text-xs truncate block hover:underline"
                      style={{ color: "#FFFFFF" }}
                    >
                      {event.event_title}
                    </Link>
                  </td>
                  <td className="py-2 px-3 text-[10px] uppercase tracking-wider whitespace-nowrap" style={{ color: "#B8B9B6" }}>
                    {event.event_source}
                  </td>
                  <td
                    className="py-2 px-3 text-right font-mono text-xs font-semibold tabular-nums"
                    style={{ color: scoreColor }}
                  >
                    {event.final_score.toFixed(1)}
                  </td>
                  <td
                    className="py-2 px-3 text-right font-mono text-xs font-semibold tabular-nums whitespace-nowrap"
                    style={{ color: amountColor }}
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
