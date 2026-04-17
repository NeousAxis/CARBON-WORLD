/**
 * GET /api/auth/me
 *
 * Returns { authed: true } if the session cookie is valid, 401 otherwise.
 * Used by the client to determine whether to show the login UI or queue.
 */

import { cookies } from "next/headers";
import { verifySession, SESSION_COOKIE } from "@/lib/auth";

export async function GET() {
  const cookieStore = await cookies();
  const token = cookieStore.get(SESSION_COOKIE)?.value;

  if (!token) {
    return Response.json({ authed: false }, { status: 401 });
  }

  const payload = await verifySession(token);
  if (!payload) {
    return Response.json({ authed: false }, { status: 401 });
  }

  return Response.json({ authed: true, sub: payload.sub });
}
