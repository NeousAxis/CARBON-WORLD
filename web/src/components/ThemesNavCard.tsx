/**
 * ThemesNavCard — Visible thematic navigation on the home page.
 *
 * Renders a single card with 10 narrative categories as toggle buttons.
 * Each button links to the existing /events drill-down with the matching
 * `category` query param, so the home becomes the discovery surface and
 * /events is the result page. No new backend, no DB migration — the regex
 * keyword match happens server-side in /events/page.tsx.
 */

import Link from "next/link";

const THEMES: Array<{ slug: string; label: string; accent: string }> = [
  { slug: "good-news", label: "Good news", accent: "#B6FFCE" },
  { slug: "pandemic", label: "Pandemic", accent: "#FF5C33" },
  { slug: "earthquake", label: "Natural disaster", accent: "#FF5C33" },
  { slug: "conflict", label: "Conflict / war", accent: "#FF5C33" },
  { slug: "climate", label: "Climate action", accent: "#0190A0" },
  { slug: "indigenous", label: "Indigenous", accent: "#0190A0" },
  { slug: "animal-welfare", label: "Animal welfare", accent: "#B6FFCE" },
  { slug: "justice", label: "Justice / legal", accent: "#0190A0" },
  { slug: "energy", label: "Energy transition", accent: "#B6FFCE" },
  { slug: "pollution", label: "Pollution", accent: "#FF5C33" },
];

export function ThemesNavCard() {
  return (
    <div
      style={{
        backgroundColor: "#1A1A1A",
        border: "1px solid #2E2E2E",
        padding: 20,
      }}
    >
      <div className="flex items-baseline justify-between mb-4 gap-3 flex-wrap">
        <div>
          <h2
            className="text-xl font-bold uppercase tracking-wider"
            style={{ color: "#FFFFFF" }}
          >
            Browse events by theme
          </h2>
          <p
            className="font-mono text-xs mt-1 uppercase tracking-wider"
            style={{ color: "#0190A0" }}
          >
            10 narrative categories · last 7 days
          </p>
        </div>
        <Link
          href="/events?since=7d"
          className="font-mono text-xs uppercase tracking-wider hover:opacity-80"
          style={{ color: "#FF8400", textDecoration: "none" }}
        >
          See all events →
        </Link>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
        {THEMES.map((t) => (
          <Link
            key={t.slug}
            href={`/events?category=${t.slug}&since=7d`}
            className="font-mono text-xs px-3 py-3 uppercase tracking-wider text-center hover:opacity-80"
            style={{
              backgroundColor: "#111111",
              border: `1px solid #2E2E2E`,
              borderLeft: `3px solid ${t.accent}`,
              color: "#FFFFFF",
              textDecoration: "none",
              transition: "all 120ms",
            }}
          >
            {t.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
