import { getEvents, getStats, formatAmount } from "@/lib/data";
import { LiveTicker } from "@/components/LiveTicker";
import { SupplyChart } from "@/components/SupplyChart";
import { EventsTable } from "@/components/EventsTable";

function formatLastUpdate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Home() {
  const events = getEvents();
  const stats = getStats();

  const netSign = stats.netSupplyChange >= 0 ? "+" : "";
  const netColor =
    stats.netSupplyChange > 0 ? "text-red-500" : "text-emerald-500";

  return (
    <div className="min-h-screen" style={{ backgroundColor: "#f8fafc" }}>
      {/* Header bar — financial ticker strip */}
      <div className="border-b border-gray-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-2.5">
          <div className="flex items-center gap-6 overflow-x-auto text-xs">
            {/* Symbol */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-sm font-bold tracking-tight text-gray-900">
                CBWD
              </span>
              <span className="text-[10px] text-gray-400 uppercase tracking-wider">
                Solana
              </span>
            </div>

            {/* Divider */}
            <div className="h-4 w-px bg-gray-200 shrink-0" />

            {/* Net supply */}
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="text-gray-400 uppercase tracking-wider">
                Net
              </span>
              <span
                className={`font-mono font-semibold tabular-nums ${netColor}`}
              >
                {netSign}
                {formatAmount(Math.abs(stats.netSupplyChange))}
              </span>
            </div>

            {/* Divider */}
            <div className="h-4 w-px bg-gray-200 shrink-0" />

            {/* Burned */}
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="text-gray-400 uppercase tracking-wider">
                Burned
              </span>
              <span className="font-mono font-semibold tabular-nums text-emerald-500">
                {formatAmount(stats.totalBurned)}
              </span>
            </div>

            {/* Divider */}
            <div className="h-4 w-px bg-gray-200 shrink-0" />

            {/* Minted */}
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="text-gray-400 uppercase tracking-wider">
                Minted
              </span>
              <span className="font-mono font-semibold tabular-nums text-red-500">
                {formatAmount(stats.totalMinted)}
              </span>
            </div>

            {/* Divider */}
            <div className="h-4 w-px bg-gray-200 shrink-0" />

            {/* Events count */}
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="text-gray-400 uppercase tracking-wider">
                Events
              </span>
              <span className="font-mono font-semibold tabular-nums text-gray-700">
                {stats.totalEvents}
              </span>
            </div>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Last update */}
            <div className="flex items-center gap-1.5 shrink-0 text-gray-400">
              <span className="uppercase tracking-wider">Updated</span>
              <span className="font-mono tabular-nums">
                {formatLastUpdate(stats.generatedAt)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="mx-auto max-w-7xl px-4 py-6 space-y-6">
        {/* Supply chart — full width */}
        <SupplyChart events={events} />

        {/* Two-column layout: LiveTicker | EventsTable */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left — Live ticker */}
          <aside className="lg:col-span-4">
            <LiveTicker events={events} />
          </aside>

          {/* Right — Events table */}
          <section className="lg:col-span-8">
            <EventsTable events={events} />
          </section>
        </div>
      </div>
    </div>
  );
}
