/**
 * GET /api/review/queue
 *
 * Returns review_queue.json. Requires a valid session cookie.
 * The file is read server-side from data/ (not in the public folder),
 * so it is never directly accessible by URL.
 */

import { cookies } from "next/headers";
import { verifySession, SESSION_COOKIE } from "@/lib/auth";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

export async function GET() {
  // ── 1. Auth check ───────────────────────────────────────────────────────
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;

  if (!token) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const payload = await verifySession(token);
  if (!payload) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  // ── 2. Read review_queue.json ───────────────────────────────────────────
  const filePath = path.join(process.cwd(), "data", "review_queue.json");

  let raw: string;
  try {
    raw = fs.readFileSync(filePath, "utf-8");
  } catch {
    // File may not exist yet if no events have been flagged for review
    return Response.json(
      { generated_at: new Date().toISOString(), total_pending: 0, reviews: [] },
      {
        status: 200,
        headers: { "Cache-Control": "no-store" },
      }
    );
  }

  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return Response.json({ error: "review_queue.json is malformed" }, { status: 500 });
  }

  return Response.json(data, {
    headers: { "Cache-Control": "no-store" },
  });
}
