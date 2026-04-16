"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

interface ReviewItem {
  id: number;
  event_title: string;
  event_url: string;
  event_source: string;
  analyst_a_verdict: string;
  analyst_b_verdict: string;
  reconciler_verdict: string;
  sentinel_concern: string;
  suggested_decision: string;
  suggested_amount_crbn: number;
  status: string;
  created_at: string;
}

interface ReviewData {
  generated_at: string;
  total_pending: number;
  reviews: ReviewItem[];
}

const STORAGE_KEY = "cbwd_review_auth";
// Simple obfuscated check — not cryptographic security, just keeps casual visitors out.
// Password: carbon-world-admin-2026
const PASSWORD_HASH = "carbon-world-admin-2026";

function AuthGate({ onAuth }: { onAuth: () => void }) {
  const [pw, setPw] = useState("");
  const [err, setErr] = useState(false);

  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div
        className="w-full max-w-md p-8"
        style={{
          backgroundColor: "#1A1A1A",
          border: "1px solid #2E2E2E",
        }}
      >
        <h1
          className="text-2xl font-bold mb-2"
          style={{ color: "#FF8400", fontFamily: "'JetBrains Mono', monospace" }}
        >
          ADMIN AREA
        </h1>
        <p className="text-sm mb-6" style={{ color: "#B8B9B6" }}>
          Human review queue — restricted access.
        </p>
        <input
          type="password"
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              if (pw === PASSWORD_HASH) {
                localStorage.setItem(STORAGE_KEY, "ok");
                onAuth();
              } else {
                setErr(true);
              }
            }
          }}
          placeholder="Password"
          className="w-full px-3 py-2 font-mono text-sm"
          style={{
            backgroundColor: "#111111",
            border: "1px solid #2E2E2E",
            color: "#FFFFFF",
          }}
        />
        <button
          onClick={() => {
            if (pw === PASSWORD_HASH) {
              localStorage.setItem(STORAGE_KEY, "ok");
              onAuth();
            } else {
              setErr(true);
            }
          }}
          className="mt-3 w-full py-2 font-bold text-sm"
          style={{
            backgroundColor: "#FF8400",
            color: "#111111",
          }}
        >
          UNLOCK
        </button>
        {err && (
          <p className="mt-3 text-sm" style={{ color: "#FF5C33" }}>
            Wrong password.
          </p>
        )}
      </div>
    </div>
  );
}

function ReviewCard({ item }: { item: ReviewItem }) {
  const [expanded, setExpanded] = useState(false);

  const parseJson = (s: string): Record<string, unknown> => {
    try {
      return JSON.parse(s);
    } catch {
      return {};
    }
  };

  const a = parseJson(item.analyst_a_verdict);
  const b = parseJson(item.analyst_b_verdict);
  const r = parseJson(item.reconciler_verdict);

  const agree = a.decision === b.decision;

  return (
    <div
      className="mb-4 p-4"
      style={{
        backgroundColor: "#1A1A1A",
        border: "1px solid #2E2E2E",
        borderLeft: "3px solid #FF8400",
      }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0 pr-4">
          <div className="flex items-center gap-2 mb-1 text-xs" style={{ color: "#B8B9B6" }}>
            <span style={{ color: "#FF8400" }}>#{item.id}</span>
            <span>•</span>
            <span>{item.event_source}</span>
            <span>•</span>
            <span>{new Date(item.created_at).toLocaleString()}</span>
          </div>
          <h3
            className="text-base font-medium mb-2"
            style={{ color: "#FFFFFF" }}
          >
            {item.event_title}
          </h3>
          <a
            href={item.event_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs hover:underline"
            style={{ color: "#FF8400" }}
          >
            View article →
          </a>
        </div>
        <span
          className="px-2 py-1 text-xs font-bold shrink-0"
          style={{
            backgroundColor: item.suggested_decision === "BURN" ? "#222924" : "#24100B",
            color: item.suggested_decision === "BURN" ? "#B6FFCE" : "#FF5C33",
          }}
        >
          {item.suggested_decision} {(item.suggested_amount_crbn / 1_000_000).toFixed(2)}M
        </span>
      </div>

      {/* Sentinel concern — the reason it was flagged */}
      <div
        className="p-3 mb-3 text-sm"
        style={{
          backgroundColor: "#291C0F",
          border: "1px solid #FF8400",
          color: "#FF8400",
        }}
      >
        <div className="text-xs font-bold mb-1" style={{ color: "#FF8400" }}>
          SENTINEL FLAG
        </div>
        <div style={{ color: "#FFFFFF" }}>{item.sentinel_concern || "No concern recorded"}</div>
      </div>

      {/* A/B/R verdicts */}
      <div className="grid grid-cols-3 gap-2 text-xs mb-3">
        <div className="p-2" style={{ backgroundColor: "#111111", border: "1px solid #2E2E2E" }}>
          <div style={{ color: "#B8B9B6" }}>ANALYST A (Qwen3)</div>
          <div className="font-mono mt-1" style={{ color: "#FFFFFF" }}>
            {String(a.decision ?? "?")} {Number(a.final_score ?? 0).toFixed(2)}
          </div>
        </div>
        <div className="p-2" style={{ backgroundColor: "#111111", border: "1px solid #2E2E2E" }}>
          <div style={{ color: "#B8B9B6" }}>ANALYST B (Llama)</div>
          <div className="font-mono mt-1" style={{ color: "#FFFFFF" }}>
            {String(b.decision ?? "?")} {Number(b.final_score ?? 0).toFixed(2)}
          </div>
        </div>
        <div className="p-2" style={{ backgroundColor: "#111111", border: "1px solid #2E2E2E" }}>
          <div style={{ color: "#B8B9B6" }}>RECONCILER</div>
          <div className="font-mono mt-1" style={{ color: "#FFFFFF" }}>
            {String(r.decision ?? item.suggested_decision)} {Number(r.final_score ?? 0).toFixed(2)}
          </div>
        </div>
      </div>

      {!agree && (
        <div
          className="p-2 mb-3 text-xs font-medium"
          style={{ backgroundColor: "#24100B", color: "#FF5C33" }}
        >
          ⚠ DISAGREEMENT: A and B produced different decisions
        </div>
      )}

      {/* Resolution instructions */}
      <div className="text-xs" style={{ color: "#B8B9B6" }}>
        To resolve: run{" "}
        <code style={{ color: "#FF8400", fontFamily: "'JetBrains Mono', monospace" }}>
          python worker/resolve_review.py {item.id} &lt;approve|reverse|reject&gt;
        </code>
      </div>

      {/* Expandable full data */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="mt-3 text-xs hover:opacity-80"
        style={{ color: "#FF8400" }}
      >
        {expanded ? "− Hide" : "+ Show"} full verdicts
      </button>

      {expanded && (
        <div className="mt-3 space-y-2 text-xs">
          <details open>
            <summary style={{ color: "#B8B9B6", cursor: "pointer" }}>Analyst A full</summary>
            <pre
              className="p-2 mt-1 overflow-x-auto"
              style={{ backgroundColor: "#111111", color: "#B8B9B6" }}
            >
              {JSON.stringify(a, null, 2)}
            </pre>
          </details>
          <details>
            <summary style={{ color: "#B8B9B6", cursor: "pointer" }}>Analyst B full</summary>
            <pre
              className="p-2 mt-1 overflow-x-auto"
              style={{ backgroundColor: "#111111", color: "#B8B9B6" }}
            >
              {JSON.stringify(b, null, 2)}
            </pre>
          </details>
          <details>
            <summary style={{ color: "#B8B9B6", cursor: "pointer" }}>Reconciler full</summary>
            <pre
              className="p-2 mt-1 overflow-x-auto"
              style={{ backgroundColor: "#111111", color: "#B8B9B6" }}
            >
              {JSON.stringify(r, null, 2)}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}

export default function ReviewPage() {
  const [authed, setAuthed] = useState(false);
  const [data, setData] = useState<ReviewData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === "ok") {
      setAuthed(true);
    }
  }, []);

  useEffect(() => {
    if (!authed) return;
    fetch("/data/review_queue.json")
      .then((r) => r.json())
      .then((d: ReviewData) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [authed]);

  if (!authed) {
    return <AuthGate onAuth={() => setAuthed(true)} />;
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <Link
          href="/"
          className="text-sm hover:opacity-80"
          style={{ color: "#FF8400" }}
        >
          ← Back to dashboard
        </Link>
        <button
          onClick={() => {
            localStorage.removeItem(STORAGE_KEY);
            setAuthed(false);
          }}
          className="text-xs"
          style={{ color: "#B8B9B6" }}
        >
          Sign out
        </button>
      </div>

      <h1
        className="text-3xl font-bold mb-2"
        style={{ fontFamily: "'JetBrains Mono', monospace", color: "#FFFFFF" }}
      >
        Review Queue
      </h1>
      <p className="mb-6" style={{ color: "#B8B9B6" }}>
        Events flagged by the Sentinel as potentially incoherent. Each flagged
        decision has NOT been executed on-chain — they wait for your review.
      </p>

      {loading && <div style={{ color: "#B8B9B6" }}>Loading…</div>}

      {!loading && data && data.total_pending === 0 && (
        <div
          className="p-6 text-center"
          style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
        >
          <div style={{ color: "#B6FFCE", fontSize: "1.1rem" }}>
            ✓ No pending reviews
          </div>
          <div className="mt-2 text-sm" style={{ color: "#B8B9B6" }}>
            The Sentinel didn&apos;t flag any incoherent verdicts since last run.
          </div>
        </div>
      )}

      {!loading && data && data.total_pending > 0 && (
        <>
          <div
            className="mb-6 p-4 flex items-center gap-4"
            style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
          >
            <div>
              <div className="text-xs" style={{ color: "#B8B9B6" }}>
                PENDING
              </div>
              <div
                className="text-2xl font-bold font-mono"
                style={{ color: "#FF8400" }}
              >
                {data.total_pending}
              </div>
            </div>
            <div style={{ width: 1, height: 40, backgroundColor: "#2E2E2E" }} />
            <div className="text-xs" style={{ color: "#B8B9B6" }}>
              Last update:{" "}
              <span className="font-mono" style={{ color: "#FFFFFF" }}>
                {new Date(data.generated_at).toLocaleString()}
              </span>
            </div>
          </div>

          {data.reviews.map((r) => (
            <ReviewCard key={r.id} item={r} />
          ))}
        </>
      )}
    </div>
  );
}
