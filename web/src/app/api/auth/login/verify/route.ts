/**
 * POST /api/auth/login/verify
 *
 * Verifies the WebAuthn authentication response from the browser.
 * On success, issues a signed session cookie (cbwd-session, 24h TTL).
 */

import { cookies } from "next/headers";
import { verifyAuthenticationResponse } from "@simplewebauthn/server";
import type {
  AuthenticationResponseJSON,
  AuthenticatorTransportFuture,
} from "@simplewebauthn/server";
import {
  getCredential,
  signSession,
  verifyChallenge,
  AUTH_CHALLENGE_COOKIE,
  SESSION_COOKIE,
  sessionCookieOptions,
  RP_ID,
  RP_ORIGIN,
} from "@/lib/auth";

export async function POST(request: Request) {
  // ── 1. Parse body ───────────────────────────────────────────────────────
  let body: { response?: AuthenticationResponseJSON } = {};
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!body.response) {
    return Response.json({ error: "Missing response field" }, { status: 400 });
  }

  // ── 2. Load registered credential ──────────────────────────────────────
  const storedCred = getCredential();
  if (!storedCred) {
    return Response.json(
      { error: "No passkey registered." },
      { status: 404 }
    );
  }

  // ── 3. Recover challenge from cookie ───────────────────────────────────
  const cookieStore = await cookies();
  const challengeToken = cookieStore.get(AUTH_CHALLENGE_COOKIE)?.value;
  if (!challengeToken) {
    return Response.json(
      { error: "Challenge cookie missing or expired. Please try again." },
      { status: 400 }
    );
  }

  const expectedChallenge = await verifyChallenge(challengeToken);
  if (!expectedChallenge) {
    return Response.json(
      { error: "Challenge cookie is invalid or expired." },
      { status: 400 }
    );
  }

  // ── 4. Reconstruct WebAuthnCredential (publicKey back to Uint8Array) ───
  const publicKeyBytes = new Uint8Array(
    Buffer.from(storedCred.publicKey, "base64")
  );

  const webAuthnCredential = {
    id: storedCred.id,
    publicKey: publicKeyBytes,
    counter: storedCred.counter,
    transports: (storedCred.transports ?? []) as AuthenticatorTransportFuture[],
  };

  // ── 5. Verify authentication response ─────────────────────────────────
  let verification;
  try {
    verification = await verifyAuthenticationResponse({
      response: body.response,
      expectedChallenge,
      expectedOrigin: RP_ORIGIN,
      expectedRPID: RP_ID,
      credential: webAuthnCredential,
      requireUserVerification: true,
    });
  } catch (err) {
    console.error("[login/verify] verifyAuthenticationResponse threw:", err);
    return Response.json(
      { error: "Authentication verification failed", detail: String(err) },
      { status: 400 }
    );
  }

  if (!verification.verified) {
    return Response.json({ error: "Authentication not verified" }, { status: 401 });
  }

  // ── 6. Issue session cookie ─────────────────────────────────────────────
  const sessionToken = await signSession({
    sub: "admin",
    iat: Math.floor(Date.now() / 1000),
  });

  cookieStore.set(SESSION_COOKIE, sessionToken, {
    ...sessionCookieOptions(24 * 60 * 60), // 24 hours
  });

  // ── 7. Clear auth challenge cookie ──────────────────────────────────────
  cookieStore.set(AUTH_CHALLENGE_COOKIE, "", {
    ...sessionCookieOptions(0),
  });

  return Response.json({ ok: true });
}
