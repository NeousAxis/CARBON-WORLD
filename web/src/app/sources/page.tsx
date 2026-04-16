import fs from "fs";
import path from "path";
import Link from "next/link";

interface Source {
  name: string;
  region: string;
  category: string;
  language: string;
  url: string;
  status?: string;
}

function loadSources(): Source[] {
  const filePath = path.join(process.cwd(), "data", "sources.json");
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as Source[];
}

const categoryColors: Record<string, { bg: string; text: string }> = {
  "Climate & Environment": { bg: "#222924", text: "#B6FFCE" },
  "Science & Research": { bg: "#1a1a3a", text: "#B2B2FF" },
  "Technology & Innovation": { bg: "#291C0F", text: "#FF8400" },
  "Medicine & Health": { bg: "#24100B", text: "#FF5C33" },
  "Good News & Solutions": { bg: "#1a2a1a", text: "#34D399" },
  "Policy & Governance": { bg: "#2E2E2E", text: "#FFFFFF" },
  "World News": { bg: "#2E2E2E", text: "#B8B9B6" },
  "Science & Environment": { bg: "#222924", text: "#B6FFCE" },
};

export default function SourcesPage() {
  const sources = loadSources();
  const active = sources.filter((s) => s.status !== "down");
  const down = sources.filter((s) => s.status === "down");

  const categories = [...new Set(sources.map((s) => s.category))].sort();
  const regions = [...new Set(sources.map((s) => s.region))].sort();

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <Link
        href="/"
        className="text-sm hover:opacity-80 mb-6 inline-block"
        style={{ color: "#FF8400" }}
      >
        &larr; Back to dashboard
      </Link>

      <h1
        className="text-3xl font-bold mb-2"
        style={{ fontFamily: "'JetBrains Mono', monospace", color: "#FFFFFF" }}
      >
        Data Sources
      </h1>
      <p className="mb-8" style={{ color: "#B8B9B6" }}>
        {active.length} active feeds across {regions.length} regions and{" "}
        {categories.length} categories. Every source is checked 3 times per day.
        Non-English articles are automatically translated.
      </p>

      {/* Stats strip */}
      <div
        className="flex items-center gap-6 mb-8 p-4 text-xs"
        style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
      >
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>ACTIVE</span>
          <span
            className="font-mono font-bold"
            style={{ color: "#B6FFCE" }}
          >
            {active.length}
          </span>
        </div>
        <div style={{ width: 1, height: 16, backgroundColor: "#2E2E2E" }} />
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>DOWN</span>
          <span
            className="font-mono font-bold"
            style={{ color: "#FF5C33" }}
          >
            {down.length}
          </span>
        </div>
        <div style={{ width: 1, height: 16, backgroundColor: "#2E2E2E" }} />
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>REGIONS</span>
          <span className="font-mono font-bold" style={{ color: "#FF8400" }}>
            {regions.length}
          </span>
        </div>
        <div style={{ width: 1, height: 16, backgroundColor: "#2E2E2E" }} />
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>CATEGORIES</span>
          <span className="font-mono font-bold" style={{ color: "#FF8400" }}>
            {categories.length}
          </span>
        </div>
      </div>

      {/* Table */}
      <div
        style={{
          backgroundColor: "#1A1A1A",
          border: "1px solid #2E2E2E",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center px-4 py-2 text-xs font-bold uppercase tracking-wider"
          style={{
            backgroundColor: "#2E2E2E",
            color: "#B8B9B6",
            letterSpacing: "0.05em",
          }}
        >
          <span className="w-8">#</span>
          <span className="flex-1">Source</span>
          <span className="w-40">Region</span>
          <span className="w-52">Category</span>
          <span className="w-12 text-center">Lang</span>
          <span className="w-16 text-center">Status</span>
        </div>

        {/* Rows */}
        {sources.map((source, i) => {
          const cat = categoryColors[source.category] || {
            bg: "#2E2E2E",
            text: "#B8B9B6",
          };
          const isDown = source.status === "down";

          return (
            <div
              key={source.name}
              className="flex items-center px-4 py-3 text-sm"
              style={{
                backgroundColor: i % 2 === 0 ? "#1A1A1A" : "#111111",
                borderBottom: "1px solid #2E2E2E",
                opacity: isDown ? 0.5 : 1,
              }}
            >
              <span
                className="w-8 font-mono text-xs"
                style={{ color: "#666" }}
              >
                {i + 1}
              </span>
              <span className="flex-1">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:underline"
                  style={{ color: isDown ? "#666" : "#FFFFFF" }}
                >
                  {source.name}
                </a>
              </span>
              <span className="w-40 text-xs" style={{ color: "#B8B9B6" }}>
                {source.region}
              </span>
              <span className="w-52">
                <span
                  className="inline-block px-2 py-0.5 text-xs font-medium"
                  style={{ backgroundColor: cat.bg, color: cat.text }}
                >
                  {source.category}
                </span>
              </span>
              <span
                className="w-12 text-center font-mono text-xs"
                style={{ color: "#B8B9B6" }}
              >
                {source.language}
              </span>
              <span className="w-16 text-center">
                {isDown ? (
                  <span
                    className="inline-block px-2 py-0.5 text-xs font-bold"
                    style={{ backgroundColor: "#24100B", color: "#FF5C33" }}
                  >
                    DOWN
                  </span>
                ) : (
                  <span
                    className="inline-block px-2 py-0.5 text-xs font-bold"
                    style={{ backgroundColor: "#222924", color: "#B6FFCE" }}
                  >
                    LIVE
                  </span>
                )}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
