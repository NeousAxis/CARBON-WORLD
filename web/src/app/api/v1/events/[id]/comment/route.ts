/**
 * POST /api/v1/events/:id/comment — Partner annotation of a scored event.
 *
 * Allows a verified Tier 2 partner to attach a contextual comment to an event.
 * Comment is stored in event_comments table. Bearer required.
 */

export const dynamic = "force-dynamic";

import { z } from "zod";
import Database from "better-sqlite3";
import path from "path";
import { verifyBearer, unauthorized } from "@/lib/api/auth";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

const CommentSchema = z.object({
  comment: z.string().min(10, "comment min 10 chars").max(1000, "comment max 1000 chars"),
});

let _db: Database.Database | null = null;

function getDb(): Database.Database {
  if (_db) return _db;
  const dbPath =
    process.env.CARBON_DB_PATH ||
    path.join(process.cwd(), "..", "data", "carbon.db");
  _db = new Database(dbPath, { readonly: false, fileMustExist: true });
  _db.pragma("journal_mode = WAL");
  // Ensure event_comments table exists
  _db.exec(`
    CREATE TABLE IF NOT EXISTS event_comments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event_id INTEGER NOT NULL REFERENCES carbon_events(id),
      api_key_id INTEGER NOT NULL REFERENCES api_keys(id),
      comment TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_event_comments_event ON event_comments(event_id);
  `);
  return _db;
}

export async function OPTIONS() {
  return new Response(null, { status: 204, headers: CORS_HEADERS });
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  // Auth
  const keyRecord = await verifyBearer(request);
  if (!keyRecord) return unauthorized();

  const { id } = await params;
  const eventId = parseInt(id, 10);
  if (isNaN(eventId) || eventId <= 0) {
    return new Response(JSON.stringify({ error: "Invalid event id." }), {
      status: 400,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  // Parse body
  let rawBody: unknown;
  try {
    rawBody = await request.json();
  } catch {
    return new Response(JSON.stringify({ error: "Body must be valid JSON." }), {
      status: 400,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  const parseResult = CommentSchema.safeParse(rawBody);
  if (!parseResult.success) {
    return new Response(
      JSON.stringify({
        error: "validation_error",
        details: parseResult.error.flatten().fieldErrors,
      }),
      {
        status: 422,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      }
    );
  }

  const { comment } = parseResult.data;

  try {
    const db = getDb();

    // Verify event exists
    const event = db
      .prepare("SELECT id FROM carbon_events WHERE id = ?")
      .get(eventId);
    if (!event) {
      return new Response(
        JSON.stringify({ error: "Event not found.", event_id: eventId }),
        {
          status: 404,
          headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
        }
      );
    }

    const now = new Date().toISOString();
    const result = db
      .prepare(
        `INSERT INTO event_comments (event_id, api_key_id, comment, created_at)
         VALUES (?, ?, ?, ?)`
      )
      .run(eventId, keyRecord.id, comment, now) as Database.RunResult;

    return new Response(
      JSON.stringify({
        status: "created",
        comment_id: result.lastInsertRowid,
        event_id: eventId,
        organization: keyRecord.organization,
        created_at: now,
      }),
      {
        status: 201,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    console.error("[POST /api/v1/events/:id/comment]", err);
    return new Response(JSON.stringify({ error: "Internal server error." }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
}
