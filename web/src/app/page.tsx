import { getEvents, getStats, formatAmount } from "@/lib/data";
import { LiveTicker } from "@/components/LiveTicker";
import { SupplyChart } from "@/components/SupplyChart";
import { BreakdownDonut } from "@/components/BreakdownDonut";
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
    stats.netSupplyChange > 0 ? "#FF5C33" : "#B6FFCE";

  return (
    <div className="min-h-screen" style={{ backgroundColor: "#111111" }}>
      {/* Header bar — financial ticker strip */}
      <div style={{ backgroundColor: "#1A1A1A", borderBottom: "1px solid #2E2E2E" }}>
        <div className="mx-auto max-w-7xl px-4 py-2.5">
          <div className="flex items-center gap-6 overflow-x-auto text-xs">
            {/* Symbol */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-sm font-bold tracking-tight" style={{ color: "#FF8400" }}>
                CBWD
              </span>
              <span className="text-[10px] uppercase tracking-wider" style={{ color: "#B8B9B6" }}>
                Solana
              </span>
            </div>

            {/* Divider */}
            <div className="h-4 w-px shrink-0" style={{ backgroundColor: "#2E2E2E" }} />

            {/* Net supply */}
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="uppercase tracking-wider" style={{ color: "#B8B9B6" }}>
                Net
              </span>
              <span
                className="font-mono font-semibold tabular-nums"
                style={{ color: netColor }}
              >
                {netSign}
                {formatAmount(Math.abs(stats.netSupplyChange))}
              </span>
            </div>

            {/* Divider */}
            <div className="h-4 w-px shrink-0" style={{ backgroundColor: "#2E2E2E" }} />

            {/* Burned */}
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="uppercase tracking-wider" style={{ color: "#B8B9B6" }}>
                Burned
              </span>
              <span className="font-mono font-semibold tabular-nums" style={{ color: "#B6FFCE" }}>
                {formatAmount(stats.totalBurned)}
              </span>
            </div>

            {/* Divider */}
            <div className="h-4 w-px shrink-0" style={{ backgroundColor: "#2E2E2E" }} />

            {/* Minted */}
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="uppercase tracking-wider" style={{ color: "#B8B9B6" }}>
                Minted
              </span>
              <span className="font-mono font-semibold tabular-nums" style={{ color: "#FF5C33" }}>
                {formatAmount(stats.totalMinted)}
              </span>
            </div>

            {/* Divider */}
            <div className="h-4 w-px shrink-0" style={{ backgroundColor: "#2E2E2E" }} />

            {/* Events count */}
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="uppercase tracking-wider" style={{ color: "#B8B9B6" }}>
                Events
              </span>
              <span className="font-mono font-semibold tabular-nums" style={{ color: "#FFFFFF" }}>
                {stats.totalEvents}
              </span>
            </div>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Last update */}
            <div className="flex items-center gap-1.5 shrink-0" style={{ color: "#B8B9B6" }}>
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
        {/* Charts row: supply chart + donut */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-8">
            <SupplyChart events={events} />
          </div>
          <div className="lg:col-span-4">
            <BreakdownDonut events={events} />
          </div>
        </div>

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
