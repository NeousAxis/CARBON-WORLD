/**
 * GET /api/v1/events/:id — Single event detail with full justification.
 *
 * Returns 404 if event not found.
 */

export const dynamic = "force-dynamic";

import { queryEventById } from "@/lib/api/db";
import { checkRateLimit, getClientIp } from "@/lib/api/rate-limit";
import { ok, rateLimitExceeded, notFound, badRequest, serverError, optionsResponse } from "@/lib/api/response";

export async function OPTIONS() {
  return optionsResponse();
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  // Rate limiting
  const ip = getClientIp(request);
  const rl = checkRateLimit(ip);
  if (!rl.allowed) return rateLimitExceeded(rl);

  try {
    const { id: rawId } = await params;
    const id = parseInt(rawId, 10);

    if (isNaN(id) || id < 1) {
      return badRequest("Event id must be a positive integer.");
    }

    const event = queryEventById(id);
    if (!event) {
      return notFound(`Event with id ${id} not found.`);
    }

    return ok(event, rl);
  } catch (err) {
    console.error("[GET /api/v1/events/:id]", err);
    return serverError();
  }
}
