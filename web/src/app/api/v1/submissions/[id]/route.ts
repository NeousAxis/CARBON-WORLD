/**
 * GET /api/v1/submissions/:id — Submission status polling endpoint.
 *
 * Public — no Bearer required (callback_url given to the submitting partner).
 * Returns the current status of a partner submission and, when scored,
 * links to the resulting event.
 */

export const dynamic = "force-dynamic";

import Database from "better-sqlite3";
import path from "path";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

let _db: Database.Database | null = null;

function getDb(): Database.Database {
  if (_db) return _db;
  const dbPath =
    process.env.CARBON_DB_PATH ||
    path.join(process.cwd(), "..", "data", "carbon.db");
  _db = new Database(dbPath, { readonly: true, fileMustExist: true });
  _db.pragma("journal_mode = WAL");
  return _db;
}

interface SubmissionRow {
  id: string;
  api_key_id: number;
  received_at: string;
  processed_at: string | null;
  resulting_event_id: number | null;
  status: string;
}

export async function OPTIONS() {
  return new Response(null, { status: 204, headers: CORS_HEADERS });
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  if (!id || typeof id !== "string") {
    return new Response(JSON.stringify({ error: "Invalid submission id." }), {
      status: 400,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }

  try {
    const db = getDb();
    const row = db
      .prepare(
        `SELECT id, api_key_id, received_at, processed_at,
                resulting_event_id, status
         FROM submissions WHERE id = ?`
      )
      .get(id) as SubmissionRow | undefined;

    if (!row) {
      return new Response(
        JSON.stringify({ error: "Submission not found.", submission_id: id }),
        {
          status: 404,
          headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
        }
      );
    }

    const baseUrl =
      process.env.NEXT_PUBLIC_BASE_URL ||
      (request.headers.get("origin") ?? "https://carbon-world.xyz");

    const resultingEventUrl =
      row.resulting_event_id != null
        ? `${baseUrl}/api/v1/events/${row.resulting_event_id}`
        : null;

    return new Response(
      JSON.stringify({
        submission_id: row.id,
        status: row.status,
        received_at: row.received_at,
        processed_at: row.processed_at ?? null,
        resulting_event_id: row.resulting_event_id ?? null,
        resulting_event_url: resultingEventUrl,
      }),
      {
        status: 200,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    console.error("[GET /api/v1/submissions/:id]", err);
    return new Response(JSON.stringify({ error: "Internal server error." }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
}
