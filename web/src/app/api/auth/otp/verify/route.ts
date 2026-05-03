/**
 * POST /api/auth/otp/verify
 *
 * Body: { code: string }
 * On success → sets the session cookie and returns 200.
 * On failure → 401 with a reason.
 */

import { cookies } from "next/headers";
import { verifyOtp } from "@/lib/otp-store";
import { signSession, SESSION_COOKIE, sessionCookieOptions } from "@/lib/auth";

export async function POST(request: Request) {
  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    // empty body → no code
  }

  const code = (body as { code?: string }).code;
  if (typeof code !== "string" || !/^\d{6}$/.test(code.trim())) {
    return Response.json(
      { error: "A 6-digit code is required." },
      { status: 400 }
    );
  }

  const outcome = verifyOtp(code);
  if (!outcome.ok) {
    const errorMap: Record<string, string> = {
      no_code: "No active code. Request a new one.",
      expired: "Code expired. Request a new one.",
      too_many_attempts: "Too many attempts. Request a new one.",
      wrong_code: "Wrong code.",
    };
    return Response.json(
      { error: errorMap[outcome.reason] ?? "Invalid code." },
      { status: 401 }
    );
  }

  // Issue session
  const token = await signSession({ sub: "admin", iat: Math.floor(Date.now() / 1000) });
  const cookieStore = await cookies();
  cookieStore.set(SESSION_COOKIE, token, {
    ...sessionCookieOptions(24 * 60 * 60), // 24 h
  });

  return Response.json({ ok: true });
}
