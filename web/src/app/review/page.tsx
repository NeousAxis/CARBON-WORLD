"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Types (matching the review_queue.json shape)
// ---------------------------------------------------------------------------

interface ReviewItem {
  id: number;
  event_title: string;
  event_url: string;
  event_source: string;
  // The DB columns are nullable — early review_queue rows (e.g. id 27) were
  // written before the writer carried Analyst A/B verdicts, so any of these
  // three fields can come back as null OR a JSON-encoded string.
  analyst_a_verdict: string | null;
  analyst_b_verdict: string | null;
  reconciler_verdict: string | null;
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

// ---------------------------------------------------------------------------
// ReviewCard — with inline Approve / Reverse / Reject buttons
// ---------------------------------------------------------------------------

type ResolveVerdict = "approve" | "reverse" | "reject";

interface ResolveResult {
  kind: "ok" | "err";
  msg: string;
}

function ReviewCard({
  item,
  onResolved,
}: {
  item: ReviewItem;
  onResolved?: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState<ResolveVerdict | null>(null);
  const [result, setResult] = useState<ResolveResult | null>(null);

  // Defensive parse: the DB columns are nullable, so item.analyst_a_verdict can
  // be null. JSON.parse(null) does NOT throw — it coerces to the string "null"
  // and returns the JSON null value, so a naive try/catch leaves you with a
  // null reference and the next `.decision` access crashes the whole page.
  // Guard explicitly: anything that isn't a plain object becomes {}.
  const parseJson = (s: string | null | undefined): Record<string, unknown> => {
    if (typeof s !== "string" || s.trim() === "") return {};
    try {
      const parsed = JSON.parse(s);
      return parsed && typeof parsed === "object" && !Array.isArray(parsed)
        ? (parsed as Record<string, unknown>)
        : {};
    } catch {
      return {};
    }
  };

  const a = parseJson(item.analyst_a_verdict);
  const b = parseJson(item.analyst_b_verdict);
  const r = parseJson(item.reconciler_verdict);

  // Both verdicts must be present AND have a decision field for "agree" to be
  // meaningful. Missing data should surface as the disagreement banner being
  // hidden, not as a confident "agree".
  const agree =
    a.decision !== undefined &&
    b.decision !== undefined &&
    a.decision === b.decision;

  const resolved = result?.kind === "ok";

  async function resolve(verdict: ResolveVerdict) {
    if (verdict === "reject") {
      if (
        !window.confirm(
          `Reject event #${item.id} definitively? No on-chain transaction will be executed.`
        )
      ) {
        return;
      }
    }
    setBusy(verdict);
    setResult(null);
    try {
      const res = await fetch(`/api/review/resolve/${item.id}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ verdict, reason }),
      });
      const data = await res.json() as Record<string, unknown>;
      const detail = typeof data.detail === "string" ? data.detail : "";
      const errMsgRaw = typeof data.error === "string" ? data.error : "";

      // Treat "not found (or already resolved)" as a success: the action
      // succeeded on a previous click but the UI didn't refresh because the
      // Solana confirmation outran the 120 s execFile timeout. We refresh
      // the queue so the row disappears and the user is not confused.
      const alreadyResolved =
        /not found.*already resolved/i.test(detail) ||
        /not found.*already resolved/i.test(errMsgRaw);

      if (res.ok || alreadyResolved) {
        setResult({
          kind: "ok",
          msg: alreadyResolved ? "Already resolved — queue refreshed" : "Done",
        });
        onResolved?.();
      } else {
        const errMsg = detail || errMsgRaw || "Unknown error";
        setResult({ kind: "err", msg: errMsg });
      }
    } catch (err) {
      setResult({
        kind: "err",
        msg: err instanceof Error ? err.message : "Network error",
      });
    } finally {
      setBusy(null);
      // Always refresh the queue on action complete — even on errors. If
      // the Python CLI succeeded but the route timed out (504), the row is
      // already gone from review_queue server-side and a refresh aligns the
      // UI with reality.
      onResolved?.();
    }
  }

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
          <h3 className="text-base font-medium mb-2" style={{ color: "#FFFFFF" }}>
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

      {/* Sentinel concern */}
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

      {/* Resolution actions */}
      <div className="mt-1">
        {/* Reason textarea */}
        <textarea
          rows={2}
          placeholder="Reason (optional, for audit trail)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          disabled={resolved || busy !== null}
          className="w-full mb-2 p-2 text-xs"
          style={{
            backgroundColor: "#111111",
            border: "1px solid #2E2E2E",
            color: "#FFFFFF",
            fontFamily: "'JetBrains Mono', monospace",
            resize: "vertical",
          }}
        />

        {/* Action buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => resolve("approve")}
            disabled={resolved || busy !== null}
            className="px-3 py-2 text-xs font-bold"
            style={{
              backgroundColor: resolved || busy !== null ? undefined : "#B6FFCE",
              color: "#0A1A0E",
              fontFamily: "'JetBrains Mono', monospace",
              cursor: busy === "approve" ? "wait" : resolved || busy !== null ? "not-allowed" : "pointer",
              opacity: resolved || (busy !== null && busy !== "approve") ? 0.5 : 1,
            }}
          >
            {busy === "approve" ? "Executing…" : "APPROVE"}
          </button>

          <button
            onClick={() => resolve("reverse")}
            disabled={resolved || busy !== null}
            className="px-3 py-2 text-xs font-bold"
            style={{
              backgroundColor: resolved || busy !== null ? undefined : "#FF8400",
              color: "#111111",
              fontFamily: "'JetBrains Mono', monospace",
              cursor: busy === "reverse" ? "wait" : resolved || busy !== null ? "not-allowed" : "pointer",
              opacity: resolved || (busy !== null && busy !== "reverse") ? 0.5 : 1,
            }}
          >
            {busy === "reverse" ? "Executing…" : "REVERSE MINT↔BURN"}
          </button>

          <button
            onClick={() => resolve("reject")}
            disabled={resolved || busy !== null}
            className="px-3 py-2 text-xs font-bold"
            style={{
              backgroundColor: "transparent",
              border: "1px solid #FF5C33",
              color: "#FF5C33",
              fontFamily: "'JetBrains Mono', monospace",
              cursor: busy === "reject" ? "wait" : resolved || busy !== null ? "not-allowed" : "pointer",
              opacity: resolved || (busy !== null && busy !== "reject") ? 0.5 : 1,
            }}
          >
            {busy === "reject" ? "Executing…" : "REJECT"}
          </button>
        </div>

        {/* Status feedback */}
        {result && (
          <div
            className="mt-2 text-xs px-2 py-1"
            style={{
              backgroundColor: result.kind === "ok" ? "#222924" : "#24100B",
              color: result.kind === "ok" ? "#B6FFCE" : "#FF5C33",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {result.kind === "ok" ? "✓ Resolved — refresh to update queue" : `✗ Error: ${result.msg}`}
          </div>
        )}
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

// ---------------------------------------------------------------------------
// OtpLoginUI — email-based 6-digit code (no passkey, no password manager)
// ---------------------------------------------------------------------------

function OtpLoginUI({ onSuccess }: { onSuccess: () => void }) {
  const [step, setStep] = useState<"request" | "verify">("request");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [email, setEmail] = useState("");
  const [recipient, setRecipient] = useState("");
  const [code, setCode] = useState("");

  async function handleRequest() {
    setStatus("loading");
    setErrorMsg("");
    try {
      const r = await fetch("/api/auth/otp/request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error((err as { error?: string }).error ?? `HTTP ${r.status}`);
      }
      const { recipient: masked } = (await r.json()) as { recipient?: string };
      setRecipient(masked ?? "");
      setStep("verify");
      setStatus("idle");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  }

  async function handleVerify() {
    setStatus("loading");
    setErrorMsg("");
    try {
      const r = await fetch("/api/auth/otp/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim() }),
      });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error((err as { error?: string }).error ?? "Verification failed");
      }
      onSuccess();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  }

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

        {step === "request" && (
          <>
            <label
              className="block text-xs font-mono uppercase tracking-wider mb-2"
              style={{ color: "#B8B9B6" }}
            >
              Email
            </label>
            <input
              type="email"
              autoFocus
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && email.includes("@")) handleRequest();
              }}
              placeholder="you@example.com"
              className="w-full px-3 py-3 mb-3 text-sm font-mono"
              style={{
                backgroundColor: "#111111",
                border: "1px solid #2E2E2E",
                color: "#FFFFFF",
                outline: "none",
              }}
            />
            <button
              onClick={handleRequest}
              disabled={status === "loading" || !email.includes("@")}
              className="w-full py-3 font-bold text-sm disabled:opacity-50"
              style={{
                backgroundColor: "#FF8400",
                color: "#111111",
                fontFamily: "'JetBrains Mono', monospace",
                cursor:
                  status === "loading" || !email.includes("@")
                    ? "not-allowed"
                    : "pointer",
              }}
            >
              {status === "loading" ? "Sending code…" : "Send me a login code"}
            </button>
          </>
        )}

        {step === "verify" && (
          <>
            <p className="text-xs font-mono mb-3" style={{ color: "#B8B9B6" }}>
              Code sent to <span style={{ color: "#B6FFCE" }}>{recipient}</span>.
              Check your inbox and paste the 6-digit code below.
            </p>
            <input
              type="text"
              inputMode="numeric"
              pattern="\d{6}"
              maxLength={6}
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              onKeyDown={(e) => {
                if (e.key === "Enter" && code.length === 6) handleVerify();
              }}
              placeholder="123456"
              className="w-full px-3 py-3 mb-3 text-lg font-mono tracking-[0.3em] text-center"
              style={{
                backgroundColor: "#111111",
                border: "1px solid #2E2E2E",
                color: "#FFFFFF",
                outline: "none",
              }}
            />
            <button
              onClick={handleVerify}
              disabled={status === "loading" || code.length !== 6}
              className="w-full py-3 font-bold text-sm disabled:opacity-50"
              style={{
                backgroundColor: "#FF8400",
                color: "#111111",
                fontFamily: "'JetBrains Mono', monospace",
                cursor:
                  status === "loading" || code.length !== 6
                    ? "not-allowed"
                    : "pointer",
              }}
            >
              {status === "loading" ? "Verifying…" : "Sign in"}
            </button>
            <button
              onClick={() => {
                setStep("request");
                setCode("");
                setErrorMsg("");
                setStatus("idle");
              }}
              className="w-full mt-2 py-2 text-xs font-mono uppercase tracking-wider"
              style={{
                backgroundColor: "transparent",
                color: "#B8B9B6",
                border: "1px solid #2E2E2E",
                cursor: "pointer",
              }}
            >
              ← Send a new code
            </button>
          </>
        )}

        {status === "error" && (
          <p className="mt-3 text-sm" style={{ color: "#FF5C33" }}>
            {errorMsg}
          </p>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main ReviewPage
// ---------------------------------------------------------------------------

type AuthState = "checking" | "unauthenticated" | "authenticated";

export default function ReviewPage() {
  const [authState, setAuthState] = useState<AuthState>("checking");
  const [data, setData] = useState<ReviewData | null>(null);
  const [queueLoading, setQueueLoading] = useState(false);
  const [queueError, setQueueError] = useState("");

  // Check session on mount
  useEffect(() => {
    fetch("/api/auth/me")
      .then((r) => {
        if (r.ok) {
          setAuthState("authenticated");
        } else {
          setAuthState("unauthenticated");
        }
      })
      .catch(() => setAuthState("unauthenticated"));
  }, []);

  // Fetch queue when authenticated
  const fetchQueue = useCallback(async () => {
    setQueueLoading(true);
    setQueueError("");
    try {
      const r = await fetch("/api/review/queue");
      if (r.status === 401) {
        setAuthState("unauthenticated");
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d: ReviewData = await r.json();
      setData(d);
    } catch (err) {
      setQueueError(err instanceof Error ? err.message : "Failed to load queue");
    } finally {
      setQueueLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authState === "authenticated") {
      fetchQueue();
    }
  }, [authState, fetchQueue]);

  async function handleLogout() {
    await fetch("/api/auth/logout", { method: "POST" });
    setAuthState("unauthenticated");
    setData(null);
  }

  // ── Render ─────────────────────────────────────────────────────────────

  if (authState === "checking") {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <p style={{ color: "#B8B9B6" }}>Checking session…</p>
      </div>
    );
  }

  if (authState === "unauthenticated") {
    return <OtpLoginUI onSuccess={() => setAuthState("authenticated")} />;
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <Link href="/" className="text-sm hover:opacity-80" style={{ color: "#FF8400" }}>
          ← Back to dashboard
        </Link>
        <button onClick={handleLogout} className="text-xs hover:opacity-80" style={{ color: "#B8B9B6" }}>
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

      {queueLoading && <div style={{ color: "#B8B9B6" }}>Loading…</div>}

      {queueError && (
        <div
          className="p-4 mb-4"
          style={{ backgroundColor: "#24100B", border: "1px solid #FF5C33", color: "#FF5C33" }}
        >
          Error loading queue: {queueError}
        </div>
      )}

      {!queueLoading && data && data.total_pending === 0 && (
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

      {!queueLoading && data && data.total_pending > 0 && (
        <>
          <div
            className="mb-6 p-4 flex items-center gap-4"
            style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
          >
            <div>
              <div className="text-xs" style={{ color: "#B8B9B6" }}>PENDING</div>
              <div className="text-2xl font-bold font-mono" style={{ color: "#FF8400" }}>
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

          {data.reviews.map((item) => (
            <ReviewCard key={item.id} item={item} onResolved={fetchQueue} />
          ))}
        </>
      )}
    </div>
  );
}
