"use client";

import { useEffect, useState } from "react";

interface RawArticle {
  title: string;
  source: string;
  link: string;
  published: string;
}

interface RawFeed {
  generated_at: string;
  count: number;
  articles: RawArticle[];
}

export function RawFeedTicker() {
  const [feed, setFeed] = useState<RawFeed | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const res = await fetch("/api/feed", { cache: "no-store" });
        if (!res.ok) return;
        const data = (await res.json()) as RawFeed;
        if (!cancelled) setFeed(data);
      } catch {
        // silent — ticker just keeps last value
      }
    };
    poll();
    const id = setInterval(poll, 60_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  if (!feed || feed.articles.length === 0) return null;

  const items = [...feed.articles, ...feed.articles];

  return (
    <div
      className="overflow-hidden relative"
      style={{
        backgroundColor: "#0B0B0B",
        borderBottom: "1px solid #2E2E2E",
        height: 36,
      }}
    >
      <div className="marquee-track flex items-center gap-8 absolute whitespace-nowrap" style={{ top: 0, bottom: 0 }}>
        {items.map((a, i) => (
          <a
            key={`${i}-${a.link || a.title}`}
            href={a.link || "#"}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs hover:opacity-80"
            style={{ color: "#B8B9B6" }}
          >
            <span
              className="uppercase tracking-wider mr-2"
              style={{ color: "var(--brand-teal)", fontWeight: 600 }}
            >
              {a.source}
            </span>
            <span>{a.title}</span>
          </a>
        ))}
      </div>
    </div>
  );
}
