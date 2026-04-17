/**
 * POST /api/auth/register/verify
 *
 * Verifies the WebAuthn registration response from the browser.
 * On success:
 *  - Serializes the credential to base64(JSON) and returns it to the client
 *    so the operator can copy it into the PASSKEY_CREDENTIAL env var.
 *  - In development, also writes it to .credential.json.
 *  - Clears the reg-challenge cookie.
 */

import { cookies } from "next/headers";
import { verifyRegistrationResponse } from "@simplewebauthn/server";
import type { RegistrationResponseJSON } from "@simplewebauthn/server";
import {
  getCredential,
  saveCredential,
  verifyChallenge,
  REG_CHALLENGE_COOKIE,
  sessionCookieOptions,
  RP_ID,
  RP_ORIGIN,
} from "@/lib/auth";

export async function POST(request: Request) {
  // ── 1. Verify setup secret ──────────────────────────────────────────────
  const setupSecret = process.env.SETUP_SECRET;
  if (!setupSecret) {
    return Response.json(
      { error: "Setup is disabled (SETUP_SECRET not configured)" },
      { status: 403 }
    );
  }

  let body: { secret?: string; response?: RegistrationResponseJSON } = {};
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (body.secret !== setupSecret) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  if (!body.response) {
    return Response.json({ error: "Missing response field" }, { status: 400 });
  }

  // ── 2. Reject if already registered ─────────────────────────────────────
  if (getCredential() !== null) {
    return Response.json(
      { error: "A passkey is already registered." },
      { status: 409 }
    );
  }

  // ── 3. Recover challenge from signed cookie ─────────────────────────────
  const cookieStore = await cookies();
  const challengeToken = cookieStore.get(REG_CHALLENGE_COOKIE)?.value;
  if (!challengeToken) {
    return Response.json(
      { error: "Challenge cookie missing or expired. Please restart the registration flow." },
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

  // ── 4. Verify registration response ────────────────────────────────────
  let verification;
  try {
    verification = await verifyRegistrationResponse({
      response: body.response,
      expectedChallenge,
      expectedOrigin: RP_ORIGIN,
      expectedRPID: RP_ID,
      requireUserVerification: true,
    });
  } catch (err) {
    console.error("[register/verify] verifyRegistrationResponse threw:", err);
    return Response.json(
      { error: "Registration verification failed", detail: String(err) },
      { status: 400 }
    );
  }

  if (!verification.verified || !verification.registrationInfo) {
    return Response.json(
      { error: "Registration not verified" },
      { status: 400 }
    );
  }

  // ── 5. Extract and store credential ────────────────────────────────────
  const { credential } = verification.registrationInfo;

  // publicKey is a Uint8Array — convert to base64 string for JSON storage.
  const storedCred = {
    id: credential.id,
    publicKey: Buffer.from(credential.publicKey).toString("base64"),
    counter: credential.counter,
    transports: credential.transports ?? [],
  };

  const credentialBase64 = saveCredential(storedCred);

  // ── 6. Clear challenge cookie ───────────────────────────────────────────
  cookieStore.set(REG_CHALLENGE_COOKIE, "", {
    ...sessionCookieOptions(0), // maxAge 0 → delete
  });

  return Response.json({
    ok: true,
    credentialBase64,
    instructions:
      'Copy the "credentialBase64" value into the PASSKEY_CREDENTIAL environment variable in Vercel (or your .env.local), then redeploy. After that, delete (or empty) SETUP_SECRET.',
  });
}
