/**
 * GET /api/v1/events  — Paginated list of scored events (Tier 1 public).
 * POST /api/v1/events — Submit a new event for scoring (Tier 2 partner, Bearer required).
 */

export const dynamic = "force-dynamic";

import { z } from "zod";
import { createHash } from "crypto";
import Database from "better-sqlite3";
import path from "path";
import { queryEvents } from "@/lib/api/db";
import { checkRateLimit, getClientIp } from "@/lib/api/rate-limit";
import { ok, rateLimitExceeded, badRequest, serverError, optionsResponse } from "@/lib/api/response";
import { verifyBearer, unauthorized } from "@/lib/api/auth";
import { checkWriteLimit, writeQuotaExceeded } from "@/lib/api/write-limit";

const VALID_DECISIONS = new Set(["BURN", "MINT", "NEUTRAL"]);

// ---------------------------------------------------------------------------
// POST /api/v1/events — zod schema
// ---------------------------------------------------------------------------

const EVENT_TYPE_VALUES = [
  "legal_win",
  "community_action",
  "conservation_win",
  "indigenous_rights",
  "labor_rights",
  "policy_influence",
  "whistleblower",
  "corporate_regression",
  "institutional_decision",
] as const;

const LANGUAGE_VALUES = ["en", "fr", "es", "pt", "ar", "zh"] as const;

const PostEventSchema = z.object({
  title: z.string().min(10, "title must be at least 10 chars").max(500, "title max 500 chars"),
  description: z.string().min(100, "description must be at least 100 chars").max(3000, "description max 3000 chars"),
  source_url: z.string().url("source_url must be a valid URL"),
  published_at: z
    .string()
    .refine((v) => !isNaN(new Date(v).getTime()), { message: "published_at must be ISO8601 datetime" }),
  organization: z.string().min(2, "organization min 2 chars").max(200, "organization max 200 chars"),
  event_type: z.enum(EVENT_TYPE_VALUES, {
    message: `event_type must be one of: ${EVENT_TYPE_VALUES.join(", ")}`,
  }),
  region: z.string().max(200).optional(),
  sdgs_hint: z
    .array(z.number().int().min(1).max(17))
    .max(17)
    .optional(),
  evidence_urls: z
    .array(z.string().url())
    .max(10, "evidence_urls max 10 items")
    .optional(),
  language: z.enum(LANGUAGE_VALUES).optional(),
});

// ---------------------------------------------------------------------------
// Write DB helper (needs write access, separate from read-only db.ts)
// ---------------------------------------------------------------------------

let _writeDb: Database.Database | null = null;

function getWriteDb(): Database.Database {
  if (_writeDb) return _writeDb;
  const dbPath =
    process.env.CARBON_DB_PATH ||
    path.join(process.cwd(), "..", "data", "carbon.db");
  _writeDb = new Database(dbPath, { readonly: false, fileMustExist: true });
  _writeDb.pragma("journal_mode = WAL");
  return _writeDb;
}

function slugify(str: string): string {
  return str
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "")
    .slice(0, 12);
}

function buildSubmissionId(organization: string): string {
  const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const orgSlug = slugify(organization);
  const hex = createHash("sha256").update(String(Date.now())).digest("hex").slice(0, 6);
  return `sub_${dateStr}_${orgSlug}_${hex}`;
}

function logUsage(
  db: Database.Database,
  apiKeyId: number,
  ip: string,
  endpoint: string,
  method: string,
  statusCode: number
): void {
  try {
    db.prepare(
      `INSERT INTO api_usage (api_key_id, ip_address, endpoint, method, status_code, timestamp)
       VALUES (?, ?, ?, ?, ?, ?)`
    ).run(apiKeyId, ip, endpoint, method, statusCode, new Date().toISOString());
  } catch {
    // Non-fatal
  }
}

// ---------------------------------------------------------------------------
// Route handlers
// ---------------------------------------------------------------------------

export async function OPTIONS() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    },
  });
}

export async function GET(request: Request) {
  // Rate limiting
  const ip = getClientIp(request);
  const rl = checkRateLimit(ip);
  if (!rl.allowed) return rateLimitExceeded(rl);

  try {
    const { searchParams } = new URL(request.url);

    // Parse + validate query params
    const rawLimit = searchParams.get("limit");
    const rawOffset = searchParams.get("offset");
    const decisionFilter = searchParams.get("decision")?.toUpperCase();
    const sinceFilter = searchParams.get("since");
    const sourceFilter = searchParams.get("source");

    let limit = rawLimit ? parseInt(rawLimit, 10) : 20;
    let offset = rawOffset ? parseInt(rawOffset, 10) : 0;

    if (isNaN(limit) || limit < 1) limit = 20;
    if (limit > 100) limit = 100;
    if (isNaN(offset) || offset < 0) offset = 0;

    if (decisionFilter && !VALID_DECISIONS.has(decisionFilter)) {
      return badRequest(
        `Invalid decision filter. Must be one of: BURN, MINT, NEUTRAL`
      );
    }

    // Validate ISO8601 date if provided
    if (sinceFilter) {
      const parsed = new Date(sinceFilter);
      if (isNaN(parsed.getTime())) {
        return badRequest(`Invalid 'since' parameter. Must be ISO8601 datetime.`);
      }
    }

    const { events, total } = queryEvents({
      limit,
      offset,
      decision: decisionFilter,
      since: sinceFilter ?? undefined,
      source: sourceFilter ?? undefined,
    });

    return ok(
      {
        events,
        pagination: {
          limit,
          offset,
          total,
          has_more: offset + events.length < total,
        },
      },
      rl
    );
  } catch (err) {
    console.error("[GET /api/v1/events]", err);
    return serverError();
  }
}

// ---------------------------------------------------------------------------
// POST /api/v1/events — Tier 2 partner submit
// ---------------------------------------------------------------------------

export async function POST(request: Request) {
  const ip = getClientIp(request);

  // 1. Bearer auth
  const keyRecord = await verifyBearer(request);
  if (!keyRecord) return unauthorized();

  // 2. Write rate limit
  const wl = checkWriteLimit(keyRecord.id, keyRecord.write_quota_daily);
  if (!wl.allowed) {
    logUsage(getWriteDb(), keyRecord.id, ip, "/api/v1/events", "POST", 429);
    return writeQuotaExceeded(wl);
  }

  // 3. Parse + validate body
  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return badRequest("Request body must be valid JSON.");
  }

  const parseResult = PostEventSchema.safeParse(rawBody);
  if (!parseResult.success) {
    logUsage(getWriteDb(), keyRecord.id, ip, "/api/v1/events", "POST", 422);
    return new Response(
      JSON.stringify({
        error: "validation_error",
        details: parseResult.error.flatten().fieldErrors,
      }),
      {
        status: 422,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      }
    );
  }

  const payload = parseResult.data;

  // 4. Build submission_id + insert
  const submissionId = buildSubmissionId(payload.organization);

  try {
    const db = getWriteDb();

    // Count queue position (pending + classifying ahead)
    const queueRow = db
      .prepare(
        "SELECT COUNT(*) AS c FROM submissions WHERE status IN ('pending', 'classifying')"
      )
      .get() as { c: number };
    const queuePosition = queueRow?.c ?? 0;

    db.prepare(
      `INSERT INTO submissions
         (id, api_key_id, raw_payload_json, received_at, status)
       VALUES (?, ?, ?, ?, 'pending')`
    ).run(
      submissionId,
      keyRecord.id,
      JSON.stringify(payload),
      new Date().toISOString()
    );

    logUsage(db, keyRecord.id, ip, "/api/v1/events", "POST", 202);

    const baseUrl =
      process.env.NEXT_PUBLIC_BASE_URL ||
      (request.headers.get("origin") ?? "https://carbon-world.xyz");

    return new Response(
      JSON.stringify({
        status: "accepted",
        submission_id: submissionId,
        queue_position: queuePosition,
        estimated_scoring_time_seconds: 180,
        callback_url: `${baseUrl}/api/v1/submissions/${submissionId}`,
      }),
      {
        status: 202,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
        },
      }
    );
  } catch (err) {
    console.error("[POST /api/v1/events]", err);
    return serverError("Failed to queue submission.");
  }
}
