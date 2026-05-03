"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import dynamic from "next/dynamic";
import { LiveTicker } from "@/components/LiveTicker";
import { SupplyChart } from "@/components/SupplyChart";
import { BreakdownDonut } from "@/components/BreakdownDonut";
import { EventsTable } from "@/components/EventsTable";
import { PartnersSection } from "@/components/PartnersSection";
import { WorldMap } from "@/components/WorldMap";
import {
  TopCountriesMintCard,
  TopCountriesBurnCard,
  BurnCompositionCard,
  MintCompositionCard,
  TopRegionsDestructiveCard,
  TopRegionsSustainableCard,
  TopInstitutionsCard,
  TopSectorsCard,
  SupplyTrendCard,
  EventOfTheDayCard,
  FrameworkActivityCard,
  SourceDiversityCard,
  CacheHitRateCard,
  PartnerActivityCard,
} from "@/components/indicators";
import type { CarbonEvent, ExportData, Stats, Aggregates } from "@/lib/types";

const EMPTY_AGGREGATES: Aggregates = {
  top_countries_mint: [],
  top_countries_burn: [],
  top_regions_sustainable: [],
  supply_trend_7d: [],
  event_of_the_day: null,
  framework_activity_7d: {
    SDG: { positive: 0, negative: 0 },
    UDHR: { positive: 0, negative: 0 },
    ILO: { positive: 0, negative: 0 },
    CRC: { positive: 0, negative: 0 },
    UNDRIP: { positive: 0, negative: 0 },
    Animal: { positive: 0, negative: 0 },
    PB: { positive: 0, negative: 0 },
  },
  source_diversity_7d: {
    niche_pct: 0,
    mainstream_pct: 0,
    total_sources_used: 0,
    articles_processed: 0,
  },
  cache_hit_rate_7d: { hits: 0, total_events: 0, pct: 0 },
  active_partners_7d: [],
  top_institutions_7d: [],
  top_sectors_7d: [],
  burn_composition_7d: {
    total_burn: 0,
    direct_action: { count: 0, pct: 0 },
    editorial_consciousness: { count: 0, pct: 0 },
    untyped: { count: 0, pct: 0 },
  },
  burn_composition_all_time: {
    total_burn: 0,
    direct_action: { count: 0, pct: 0 },
    editorial_consciousness: { count: 0, pct: 0 },
    untyped: { count: 0, pct: 0 },
  },
  mint_composition_7d: {
    total_mint: 0,
    direct_action: { count: 0, pct: 0 },
    editorial_alarm: { count: 0, pct: 0 },
    untyped: { count: 0, pct: 0 },
  },
  mint_composition_all_time: {
    total_mint: 0,
    direct_action: { count: 0, pct: 0 },
    editorial_alarm: { count: 0, pct: 0 },
    untyped: { count: 0, pct: 0 },
  },
  top_regions_destructive: [],
};

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
  const aggregates: Aggregates = data.aggregates ?? EMPTY_AGGREGATES;

  // Live ticker shows only events from the last 48h so the feed reflects
  // genuinely recent pipeline activity, not the full historical window.
  const recentEvents = useMemo(() => {
    const cutoff = Date.now() - 48 * 60 * 60 * 1000;
    return events.filter((e) => new Date(e.created_at).getTime() >= cutoff);
  }, [events]);

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
              <span className="text-[10px] uppercase tracking-wider" style={{ color: "var(--brand-teal)" }}>
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
        {/* Event of the Day — full width featured card */}
        <EventOfTheDayCard event={aggregates.event_of_the_day} />

        {/* Charts row: supply chart + donut (existing) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-8">
            <SupplyChart events={events} />
          </div>
          <div className="lg:col-span-4">
            <BreakdownDonut events={events} />
          </div>
        </div>

        {/* World map — choropleth + pulse rings, MINT-orange / BURN-green dominance */}
        <WorldMap events={events} windowDays={7} height={460} />

        {/* Geographic indicators row 1: Top countries MINT/BURN + Supply trend */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <TopCountriesMintCard countries={aggregates.top_countries_mint} />
          <TopCountriesBurnCard countries={aggregates.top_countries_burn} />
          <SupplyTrendCard trend={aggregates.supply_trend_7d} />
        </div>

        {/* Geographic indicators row 2: Top regions sustainable + destructive (mirror) + institutions */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <TopRegionsSustainableCard regions={aggregates.top_regions_sustainable} />
          <TopRegionsDestructiveCard regions={aggregates.top_regions_destructive ?? []} />
          <TopInstitutionsCard institutions={aggregates.top_institutions_7d} />
        </div>

        {/* Sectors — full row to keep it readable */}
        <div className="grid grid-cols-1 lg:grid-cols-1 gap-6">
          <TopSectorsCard sectors={aggregates.top_sectors_7d} />
        </div>

        {/* Framework Activity — full-width panoptic ethical card */}
        <FrameworkActivityCard data={aggregates.framework_activity_7d} />

        {/* Decision composition — BURN (direct actions vs editorial consciousness)
            and MINT (direct actions vs editorial alarm), 7D + ALL TIME */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {aggregates.burn_composition_7d && (
            <BurnCompositionCard
              composition={aggregates.burn_composition_7d}
              windowLabel="7D"
            />
          )}
          {aggregates.burn_composition_all_time && (
            <BurnCompositionCard
              composition={aggregates.burn_composition_all_time}
              windowLabel="ALL TIME"
            />
          )}
          {aggregates.mint_composition_7d && (
            <MintCompositionCard
              composition={aggregates.mint_composition_7d}
              windowLabel="7D"
            />
          )}
          {aggregates.mint_composition_all_time && (
            <MintCompositionCard
              composition={aggregates.mint_composition_all_time}
              windowLabel="ALL TIME"
            />
          )}
        </div>

        {/* Pipeline health row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <SourceDiversityCard {...aggregates.source_diversity_7d} />
          <CacheHitRateCard {...aggregates.cache_hit_rate_7d} />
          <PartnerActivityCard partners={aggregates.active_partners_7d} />
        </div>

        {/* Partners section — early supporters with logos */}
        <PartnersSection />

        {/* Two-column layout: LiveTicker | EventsTable (existing) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left — Live ticker */}
          <aside className="lg:col-span-4">
            <LiveTicker events={recentEvents} newEventIds={newEventIds} isPolling={isPolling} />
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
