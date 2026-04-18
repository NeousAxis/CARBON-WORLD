/**
 * POST /api/review/resolve/:id
 *
 * Wraps the CLI `worker/resolve_review.py` via execFile (no shell injection).
 * Requires a valid session cookie — same auth pattern as /api/review/queue.
 *
 * Body:  { verdict: "approve" | "reverse" | "reject", reason?: string }
 * 200:   { ok: true, stdout: string }
 * 400:   { error: string }
 * 401:   { error: "Unauthorized" }
 * 503:   { error: string }  (dev environment — CLI not available on local Mac)
 * 504:   { error: string, detail: string }  (execFile timeout)
 * 500:   { error: string, detail?: string }  (non-zero exit code)
 *
 * NOTE: This route is only functional in production on the VPS Hetzner
 * (157.90.250.40) where the Python venv and Solana keypair are present.
 * In dev (NODE_ENV !== "production"), the route returns 503 immediately to
 * prevent accidental CLI calls from a Mac dev environment.
 */

import { cookies } from "next/headers";
import { verifySession, SESSION_COOKIE } from "@/lib/auth";
import { execFile } from "child_process";
import { promisify } from "util";
import fs from "fs";
import path from "path";

const execFileAsync = promisify(execFile);

// Whitelist — "edit" intentionally excluded from v1 (add later if needed)
const ALLOWED_VERDICTS = ["approve", "reverse", "reject"] as const;
type Verdict = (typeof ALLOWED_VERDICTS)[number];

// Production paths on VPS Hetzner
const VPS_PYTHON = "/home/carbon/CARBON-WORLD/venv/bin/python3";
const VPS_SCRIPT = "/home/carbon/CARBON-WORLD/worker/resolve_review.py";
const VPS_CWD = "/home/carbon/CARBON-WORLD";

// Timeout: 120 s — Solana confirmation can take up to ~60 s
const EXEC_TIMEOUT_MS = 120_000;

export const dynamic = "force-dynamic";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  // ── 1. Auth ────────────────────────────────────────────────────────────────
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;

  if (!token) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = await verifySession(token);
  if (!payload) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  // ── 2. Dev guard ───────────────────────────────────────────────────────────
  // The Python CLI and Solana keypair only exist on the VPS. Block in dev to
  // avoid misleading errors or accidental file-not-found executions.
  if (process.env.NODE_ENV !== "production") {
    return Response.json(
      {
        error:
          "Resolve is only available in production (VPS). " +
          "Run the CLI directly: python worker/resolve_review.py <id> <verdict>",
      },
      { status: 503 }
    );
  }

  // ── 3. Validate params.id ──────────────────────────────────────────────────
  const { id: rawId } = await params;
  const id = parseInt(rawId, 10);
  if (!Number.isInteger(id) || id < 1) {
    return Response.json(
      { error: "Invalid id — must be a positive integer" },
      { status: 400 }
    );
  }

  // ── 4. Parse + validate body ───────────────────────────────────────────────
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Request body must be valid JSON" }, { status: 400 });
  }

  if (typeof body !== "object" || body === null) {
    return Response.json({ error: "Request body must be a JSON object" }, { status: 400 });
  }

  const { verdict: rawVerdict, reason: rawReason } = body as Record<string, unknown>;

  if (!ALLOWED_VERDICTS.includes(rawVerdict as Verdict)) {
    return Response.json(
      {
        error: `Invalid verdict. Must be one of: ${ALLOWED_VERDICTS.join(", ")}`,
      },
      { status: 400 }
    );
  }

  const verdict = rawVerdict as Verdict;
  // Sanitise reason: string, max 500 chars, fall back to empty string
  const reason =
    typeof rawReason === "string" ? rawReason.slice(0, 500) : "";

  // ── 5. Verify binaries exist (fast-fail before spawning) ──────────────────
  if (!fs.existsSync(VPS_PYTHON)) {
    console.error(`[resolve] Python binary not found at ${VPS_PYTHON}`);
    return Response.json(
      { error: `Python binary not found: ${VPS_PYTHON}` },
      { status: 503 }
    );
  }

  if (!fs.existsSync(VPS_SCRIPT)) {
    console.error(`[resolve] Script not found at ${VPS_SCRIPT}`);
    return Response.json(
      { error: `resolve_review.py not found: ${VPS_SCRIPT}` },
      { status: 503 }
    );
  }

  // ── 6. Build args array (NO shell concat — execFile only) ─────────────────
  // Array is built statically; each element is a discrete, untrusted-but-safe arg.
  const args: string[] = [
    VPS_SCRIPT,
    String(id),
    verdict,
    "--reason",
    reason,
  ];

  // ── 7. Execute ────────────────────────────────────────────────────────────
  let stdout: string;
  let stderr: string;

  try {
    const result = await execFileAsync(VPS_PYTHON, args, {
      cwd: VPS_CWD,
      timeout: EXEC_TIMEOUT_MS,
      // Explicitly no shell — execFile default, but be explicit
      shell: false,
      // Increase maxBuffer to capture verbose Solana output (4 MB)
      maxBuffer: 4 * 1024 * 1024,
    });
    stdout = result.stdout;
    stderr = result.stderr;
  } catch (err: unknown) {
    const e = err as NodeJS.ErrnoException & {
      killed?: boolean;
      code?: number | string;
      stdout?: string;
      stderr?: string;
      signal?: string;
    };

    // Timeout: killed=true + signal=SIGTERM
    if (e.killed || e.signal === "SIGTERM") {
      console.error(`[resolve] execFile timeout after ${EXEC_TIMEOUT_MS}ms for review #${id}`);
      return Response.json(
        {
          error: "Execution timed out (120 s). The Solana transaction may still confirm — check explorer.",
          detail: (e.stderr ?? "").slice(0, 200),
        },
        { status: 504 }
      );
    }

    // Non-zero exit code
    const detail = (e.stderr ?? "").slice(0, 200);
    console.error(
      `[resolve] review #${id} exited with code ${String(e.code)}:\n${detail}`
    );
    return Response.json(
      {
        error: `Process exited with code ${String(e.code)}`,
        detail,
      },
      { status: 500 }
    );
  }

  // Non-empty stderr at exit 0 — log but still return 200
  if (stderr.trim()) {
    console.warn(`[resolve] review #${id} stderr (exit 0):\n${stderr.slice(0, 400)}`);
  }

  return Response.json(
    { ok: true, stdout: stdout.trim() },
    { headers: { "Cache-Control": "no-store" } }
  );
}
