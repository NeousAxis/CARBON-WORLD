/**
 * POST /api/auth/logout
 *
 * Clears the session cookie.
 */

import { cookies } from "next/headers";
import { SESSION_COOKIE, sessionCookieOptions } from "@/lib/auth";

export async function POST() {
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, "", {
    ...sessionCookieOptions(0), // maxAge 0 → immediate expiry
  });
  return Response.json({ ok: true });
}
