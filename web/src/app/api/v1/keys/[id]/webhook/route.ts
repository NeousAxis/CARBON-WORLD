/**
 * POST /api/v1/keys/:id/webhook — Register or update a webhook URL for a partner key.
 *
 * The :id in the path is informational / REST style. The actual key used is
 * determined by the Bearer token. Bearer must match the key id in path.
 */

export const dynamic = "force-dynamic";

import { z } from "zod";
import Database from "better-sqlite3";
import path from "path";
import { verifyBearer, unauthorized, forbidden } from "@/lib/api/auth";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

const WebhookSchema = z.object({
  webhook_url: z.string().url("webhook_url must be a valid URL"),
});

let _db: Database.Database | null = null;

function getDb(): Database.Database {
  if (_db) return _db;
  const dbPath =
    process.env.CARBON_DB_PATH ||
    path.join(process.cwd(), "..", "data", "carbon.db");
  _db = new Database(dbPath, { readonly: false, fileMustExist: true });
  _db.pragma("journal_mode = WAL");
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
  const pathKeyId = parseInt(id, 10);

  // Verify the path :id matches the authenticated key
  if (isNaN(pathKeyId) || pathKeyId !== keyRecord.id) {
    return forbidden("Key id in path does not match authenticated key.");
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

  const parseResult = WebhookSchema.safeParse(rawBody);
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

  const { webhook_url } = parseResult.data;

  try {
    const db = getDb();
    db.prepare(
      "UPDATE api_keys SET webhook_url = ? WHERE id = ?"
    ).run(webhook_url, keyRecord.id);

    return new Response(
      JSON.stringify({
        status: "updated",
        key_id: keyRecord.id,
        webhook_url,
        organization: keyRecord.organization,
      }),
      {
        status: 200,
        headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
      }
    );
  } catch (err) {
    console.error("[POST /api/v1/keys/:id/webhook]", err);
    return new Response(JSON.stringify({ error: "Internal server error." }), {
      status: 500,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
}
