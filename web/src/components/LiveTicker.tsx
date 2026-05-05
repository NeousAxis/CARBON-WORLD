"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import type { CarbonEvent } from "@/lib/types";

function formatTickerAmount(raw: number): string {
  const m = raw / 1_000_000;
  if (m >= 1) return `${m.toFixed(1).replace(/\.0$/, "")}M`;
  return `${(raw / 1_000).toFixed(0)}K`;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

interface LiveTickerProps {
  events: CarbonEvent[];
  newEventIds?: Set<number>;
  isPolling?: boolean;
}

export function LiveTicker({
  events,
  newEventIds = new Set(),
  isPolling = false,
}: LiveTickerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [highlightedIds, setHighlightedIds] = useState<Set<number>>(new Set());

  // Auto-scroll loop — robust against pause-without-resume bugs:
  //  - RAF is ALWAYS running; pause is just a no-op flag.
  //    Mismatched mouseenter/mouseleave (touch, focus shift, navigation
  //    interrupt, devtools open) can no longer freeze the ticker forever.
  //  - Reset threshold uses the full scrollable height when events aren't
  //    doubled (events.length < 10), so the loop covers the whole list
  //    instead of cutting off at half.
  //  - Touch is treated as a tap-pause that auto-resumes after 4s.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let animationId: number;
    let scrollPos = 0;
    let paused = false;
    let touchResumeTimer: ReturnType<typeof setTimeout> | null = null;

    function tick() {
      if (!el) return;
      if (!paused) {
        scrollPos += 0.5;
        // When the list is doubled (events ≥ 10), one copy is half the
        // scrollHeight. When not doubled, loop on the full overflow.
        const reset = events.length >= 10
          ? el.scrollHeight / 2
          : Math.max(0, el.scrollHeight - el.clientHeight);
        if (reset > 0 && scrollPos >= reset) {
          scrollPos = 0;
        }
        el.scrollTop = scrollPos;
      }
      animationId = requestAnimationFrame(tick);
    }
    animationId = requestAnimationFrame(tick);

    const pause = () => { paused = true; };
    const resume = () => { paused = false; };
    const touchPause = () => {
      paused = true;
      if (touchResumeTimer) clearTimeout(touchResumeTimer);
      touchResumeTimer = setTimeout(() => { paused = false; }, 4000);
    };

    el.addEventListener("mouseenter", pause);
    el.addEventListener("mouseleave", resume);
    el.addEventListener("touchstart", touchPause, { passive: true });

    return () => {
      cancelAnimationFrame(animationId);
      if (touchResumeTimer) clearTimeout(touchResumeTimer);
      el.removeEventListener("mouseenter", pause);
      el.removeEventListener("mouseleave", resume);
      el.removeEventListener("touchstart", touchPause);
    };
  }, [events.length]);

  // Flash newly arrived event IDs
  useEffect(() => {
    if (newEventIds.size === 0) return;

    setHighlightedIds((prev) => {
      const next = new Set(prev);
      newEventIds.forEach((id) => next.add(id));
      return next;
    });

    const timer = setTimeout(() => {
      setHighlightedIds((prev) => {
        const next = new Set(prev);
        newEventIds.forEach((id) => next.delete(id));
        return next;
      });
    }, 3000);

    return () => clearTimeout(timer);
  }, [newEventIds]);

  // Duplicate events for seamless looping — only when enough items to make scrolling sensible.
  // With a small event array, duplication just shows the same items twice which looks buggy.
  const doubled = events.length >= 10 ? [...events, ...events] : events;

  return (
    <div
      className="overflow-hidden"
      style={{
        backgroundColor: "#1A1A1A",
        border: "1px solid #2E2E2E",
        boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
      }}
    >
      {/* Header */}
      <div
        className="px-4 py-3 flex items-center gap-2"
        style={{ borderBottom: "1px solid #2E2E2E" }}
      >
        {/* Green dot — pulses when polling is active */}
        <span className="relative flex h-2.5 w-2.5 shrink-0">
          <span
            className="absolute inline-flex h-full w-full rounded-full"
            style={{
              backgroundColor: "#4ADE80",
              opacity: 0.7,
            }}
          />
          <span
            className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
              isPolling ? "animate-live-pulse" : ""
            }`}
            style={{ backgroundColor: "#22C55E" }}
          />
        </span>
        <span
          className="text-xs font-medium uppercase tracking-wider"
          style={{ color: "#B8B9B6" }}
        >
          Live activity
        </span>
      </div>

      {/* Scrolling feed */}
      <div
        ref={containerRef}
        className="h-[600px] overflow-hidden"
        style={{ scrollBehavior: "auto" }}
      >
        {doubled.map((event, i) => {
          const isBurn = event.decision === "BURN";
          const isMint = event.decision === "MINT";
          // Only flash on the first copy (i < events.length) to avoid double flash
          const isHighlighted = i < events.length && highlightedIds.has(event.id);

          return (
            <Link
              key={`${event.id}-${i}`}
              href={`/event/${event.id}`}
              className={`block px-4 py-3 transition-colors${
                isHighlighted ? " animate-flash" : ""
              }`}
              style={{ borderBottom: "1px solid #2E2E2E" }}
            >
              <div className="flex items-center justify-between mb-1">
                <span
                  className="text-xs font-bold uppercase"
                  style={{
                    color: isBurn ? "#B6FFCE" : isMint ? "#FF5C33" : "#B8B9B6",
                  }}
                >
                  {event.decision}
                </span>
                <span className="text-[10px]" style={{ color: "#666" }}>
                  {timeAgo(event.created_at)}
                </span>
              </div>
              <p
                className="text-sm leading-snug line-clamp-2 mb-1.5"
                style={{ color: "#E5E5E5" }}
              >
                {event.event_title}
              </p>
              <div className="flex items-center justify-between">
                <span className="text-[10px]" style={{ color: "#666" }}>
                  {event.event_source}
                </span>
                <span
                  className="text-xs font-semibold"
                  style={{
                    color: isBurn ? "#B6FFCE" : isMint ? "#FF5C33" : "#B8B9B6",
                  }}
                >
                  {isMint ? "+" : "-"}
                  {formatTickerAmount(event.amount_crbn)} CBWD
                </span>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
