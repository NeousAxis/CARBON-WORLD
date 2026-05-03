/**
 * auth.ts — Server-only authentication utilities for CARBON WORLD.
 *
 * Email-OTP based: a 6-digit code is sent to the founder's mailbox
 * (OTP_RECIPIENT, default hello@carbon-world.xyz). The user pastes it
 * into the /review login form. On success, a JWT session cookie is set.
 *
 * This module must only be imported from Server Components, Route Handlers,
 * or Server Functions — never from "use client" modules.
 */

import { SignJWT, jwtVerify } from "jose";

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function getSessionSecret(): Uint8Array {
  const secret = process.env.SESSION_SECRET;
  if (!secret || secret.length < 32) {
    throw new Error(
      "SESSION_SECRET env var is missing or too short (need 32+ chars)"
    );
  }
  return new TextEncoder().encode(secret);
}

// ---------------------------------------------------------------------------
// Session JWT
// ---------------------------------------------------------------------------

export interface SessionPayload {
  sub: string;
  iat: number;
  [key: string]: unknown;
}

/**
 * Signs a session JWT with HS256. Default expiry 24 h.
 */
export async function signSession(
  payload: SessionPayload,
  expiresIn = "24h"
): Promise<string> {
  return new SignJWT(payload)
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime(expiresIn)
    .sign(getSessionSecret());
}

/**
 * Verifies a session JWT. Returns the payload or null on failure.
 */
export async function verifySession(
  token: string
): Promise<SessionPayload | null> {
  try {
    const { payload } = await jwtVerify(token, getSessionSecret());
    return payload as unknown as SessionPayload;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Cookie helpers
// ---------------------------------------------------------------------------

const isProduction = process.env.NODE_ENV === "production";

export const SESSION_COOKIE = "cbwd-session";

export function sessionCookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: isProduction,
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}
