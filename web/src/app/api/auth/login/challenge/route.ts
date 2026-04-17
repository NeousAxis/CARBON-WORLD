/**
 * POST /api/auth/login/challenge
 *
 * Generates a WebAuthn authentication challenge.
 * Returns PublicKeyCredentialRequestOptionsJSON and sets a signed
 * challenge cookie (cbwd-auth-challenge, 5-min TTL).
 */

import { cookies } from "next/headers";
import { generateAuthenticationOptions } from "@simplewebauthn/server";
import type { AuthenticatorTransportFuture } from "@simplewebauthn/server";
import {
  getCredential,
  signChallenge,
  AUTH_CHALLENGE_COOKIE,
  sessionCookieOptions,
  RP_ID,
} from "@/lib/auth";

export async function POST() {
  // ── 1. Ensure a credential exists ──────────────────────────────────────
  const cred = getCredential();
  if (!cred) {
    return Response.json(
      {
        error:
          "No passkey registered yet. Visit /review/setup to register one.",
      },
      { status: 404 }
    );
  }

  // ── 2. Generate authentication options ─────────────────────────────────
  const options = await generateAuthenticationOptions({
    rpID: RP_ID,
    userVerification: "required",
    allowCredentials: [
      {
        id: cred.id,
        transports: (cred.transports ?? []) as AuthenticatorTransportFuture[],
      },
    ],
  });

  // ── 3. Sign challenge into a cookie ────────────────────────────────────
  const challengeToken = await signChallenge(options.challenge);
  const cookieStore = await cookies();
  cookieStore.set(AUTH_CHALLENGE_COOKIE, challengeToken, {
    ...sessionCookieOptions(5 * 60),
  });

  return Response.json(options);
}
