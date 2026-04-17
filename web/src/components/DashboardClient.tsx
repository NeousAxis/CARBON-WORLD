"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import { LiveTicker } from "@/components/LiveTicker";
import { SupplyChart } from "@/components/SupplyChart";
import { BreakdownDonut } from "@/components/BreakdownDonut";
import { EventsTable } from "@/components/EventsTable";
import type { CarbonEvent, ExportData, Stats } from "@/lib/types";

// CountUp must be client-only (uses useEffect internally)
const CountUp = dynamic(() => import("react-countup"), { ssr: false });

function formatLastUpdate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function deriveStats(data: ExportData): Stats {
  return {
    totalEvents: data.total_events,
    totalBurned: data.total_burned,
    totalMinted: data.total_minted,
    netSupplyChange: data.total_minted - data.total_burned,
    generatedAt: data.generated_at,
  };
}

// Formatting helpers for CountUp formattingFn
function rawToDisplayValue(raw: number): number {
  const millions = raw / 1_000_000;
  if (millions >= 1) return parseFloat(millions.toFixed(1));
  return parseFloat((raw / 1_000).toFixed(0));
}

function rawToSuffix(raw: number): string {
  return raw / 1_000_000 >= 1 ? "M CBWD" : "K CBWD";
}

interface DashboardClientProps {
  initialData: ExportData;
}

export function DashboardClient({ initialData }: DashboardClientProps) {
  const [data, setData] = useState<ExportData>(initialData);
  const [isPolling, setIsPolling] = useState(true);
  const [fetchError, setFetchError] = useState(false);
  const previousGeneratedAt = useRef<string>(initialData.generated_at);
  const previousEventIds = useRef<Set<number>>(
    new Set(initialData.events.map((e) => e.id))
  );

  const poll = useCallback(async () => {
    if (document.visibilityState !== "visible") return;

    try {
      const res = await fetch("/api/stats", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const fresh: ExportData = await res.json();

      setFetchError(false);

      // Only update state if something actually changed
      if (fresh.generated_at !== previousGeneratedAt.current) {
        previousGeneratedAt.current = fresh.generated_at;
        setData(fresh);

        // Update tracked IDs for flash detection in LiveTicker
        previousEventIds.current = new Set(fresh.events.map((e) => e.id));
      }
    } catch (err) {
      console.error("[DashboardClient] Poll failed:", err);
      setFetchError(true);
    }
  }, []);

  useEffect(() => {
    setIsPolling(true);
    const id = setInterval(poll, 30_000);

    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        poll(); // immediate catch-up poll on tab focus
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [poll]);

  const stats = deriveStats(data);
  const events: CarbonEvent[] = data.events;

  const netAbs = Math.abs(stats.netSupplyChange);
  const netSign = stats.netSupplyChange >= 0 ? "+" : "-";
  const netColor = stats.netSupplyChange > 0 ? "#FF5C33" : "#B6FFCE";

  // Detect new event IDs to pass to LiveTicker
  const [newEventIds, setNewEventIds] = useState<Set<number>>(new Set());
  useEffect(() => {
    const currentIds = new Set(events.map((e) => e.id));
    const incoming = new Set<number>();
    currentIds.forEach((id) => {
      if (!previousEventIds.current.has(id)) incoming.add(id);
    });
    if (incoming.size > 0) {
      setNewEventIds(incoming);
      // Clear after 3.5s so flash animation can complete
      const t = setTimeout(() => setNewEventIds(new Set()), 3500);
      return () => clearTimeout(t);
    }
  }, [events]);

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
              <span className="font-mono font-semibold tabular-nums" style={{ color: netColor }}>
                {netSign}
                <CountUp
                  end={rawToDisplayValue(netAbs)}
                  decimals={netAbs / 1_000_000 >= 1 ? 1 : 0}
                  duration={1.2}
                  separator=","
                  preserveValue
                />
                {rawToSuffix(netAbs)}
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
                <CountUp
                  end={rawToDisplayValue(stats.totalBurned)}
                  decimals={stats.totalBurned / 1_000_000 >= 1 ? 1 : 0}
                  duration={1.2}
                  separator=","
                  preserveValue
                />
                {rawToSuffix(stats.totalBurned)}
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
                <CountUp
                  end={rawToDisplayValue(stats.totalMinted)}
                  decimals={stats.totalMinted / 1_000_000 >= 1 ? 1 : 0}
                  duration={1.2}
                  separator=","
                  preserveValue
                />
                {rawToSuffix(stats.totalMinted)}
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
                <CountUp
                  end={stats.totalEvents}
                  decimals={0}
                  duration={1.2}
                  separator=","
                  preserveValue
                />
              </span>
            </div>

            {/* Spacer */}
            <div className="flex-1" />

            {/* Last update + error indicator */}
            <div className="flex items-center gap-1.5 shrink-0" style={{ color: "#B8B9B6" }}>
              {fetchError && (
                <span
                  title="Live update unavailable"
                  style={{
                    display: "inline-block",
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    backgroundColor: "#FF5C33",
                    marginRight: 2,
                  }}
                />
              )}
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
            <LiveTicker events={events} newEventIds={newEventIds} isPolling={isPolling} />
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
