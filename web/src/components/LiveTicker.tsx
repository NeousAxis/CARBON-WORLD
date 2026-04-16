"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import type { CarbonEvent } from "@/lib/data";

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

export function LiveTicker({ events }: { events: CarbonEvent[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let animationId: number;
    let scrollPos = 0;

    function tick() {
      if (!el) return;
      scrollPos += 0.5;
      if (scrollPos >= el.scrollHeight / 2) {
        scrollPos = 0;
      }
      el.scrollTop = scrollPos;
      animationId = requestAnimationFrame(tick);
    }

    animationId = requestAnimationFrame(tick);

    const pauseScroll = () => cancelAnimationFrame(animationId);
    const resumeScroll = () => {
      animationId = requestAnimationFrame(tick);
    };

    el.addEventListener("mouseenter", pauseScroll);
    el.addEventListener("mouseleave", resumeScroll);

    return () => {
      cancelAnimationFrame(animationId);
      el.removeEventListener("mouseenter", pauseScroll);
      el.removeEventListener("mouseleave", resumeScroll);
    };
  }, []);

  // Duplicate events for seamless looping
  const doubled = [...events, ...events];

  return (
    <div className="rounded-2xl bg-gray-900 border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-700 flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
        </span>
        <span className="text-xs font-medium text-gray-300 uppercase tracking-wider">
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
          return (
            <Link
              key={`${event.id}-${i}`}
              href={`/event/${event.id}`}
              className="block px-4 py-3 border-b border-gray-800 hover:bg-gray-800/50 transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <span
                  className={`text-xs font-bold uppercase ${
                    isBurn
                      ? "text-emerald-400"
                      : isMint
                        ? "text-red-400"
                        : "text-gray-400"
                  }`}
                >
                  {event.decision}
                </span>
                <span className="text-[10px] text-gray-500">
                  {timeAgo(event.created_at)}
                </span>
              </div>
              <p className="text-sm text-gray-200 leading-snug line-clamp-2 mb-1.5">
                {event.event_title}
              </p>
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-gray-500">
                  {event.event_source}
                </span>
                <span
                  className={`text-xs font-semibold ${
                    isBurn
                      ? "text-emerald-400"
                      : isMint
                        ? "text-red-400"
                        : "text-gray-400"
                  }`}
                >
                  {isMint ? "+" : "-"}{formatTickerAmount(event.amount_crbn)} CBWD
                </span>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
