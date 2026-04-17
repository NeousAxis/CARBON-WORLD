/**
 * POST /api/auth/register/challenge
 *
 * Generates a WebAuthn registration challenge.
 * Gated by SETUP_SECRET — only callable during initial setup.
 * Returns PublicKeyCredentialCreationOptionsJSON and sets a signed
 * challenge cookie (cbwd-reg-challenge, 5-min TTL).
 */

import { cookies } from "next/headers";
import { generateRegistrationOptions } from "@simplewebauthn/server";
import {
  getCredential,
  signChallenge,
  REG_CHALLENGE_COOKIE,
  sessionCookieOptions,
  RP_ID,
  RP_NAME,
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

  let body: Record<string, unknown> = {};
  try {
    body = await request.json();
  } catch {
    // empty body is fine — secret may come as query param
  }

  const url = new URL(request.url);
  const providedSecret =
    (body.secret as string | undefined) ?? url.searchParams.get("secret") ?? "";

  if (providedSecret !== setupSecret) {
    return Response.json({ error: "Forbidden" }, { status: 403 });
  }

  // ── 2. Reject if credential already registered ─────────────────────────
  if (getCredential() !== null) {
    return Response.json(
      {
        error:
          "A passkey is already registered. Delete PASSKEY_CREDENTIAL and redeploy to re-register.",
      },
      { status: 409 }
    );
  }

  // ── 3. Generate registration options ───────────────────────────────────
  const options = await generateRegistrationOptions({
    rpName: RP_NAME,
    rpID: RP_ID,
    // Use a stable user ID — single-admin setup, so a fixed string is fine.
    userID: new TextEncoder().encode("admin"),
    userName: "admin",
    userDisplayName: "Carbon World Admin",
    authenticatorSelection: {
      residentKey: "required",
      userVerification: "required",
      // "platform" restricts to built-in authenticators (Touch ID / Face ID / Windows Hello)
      authenticatorAttachment: "platform",
    },
  });

  // ── 4. Sign the challenge into a short-lived cookie ────────────────────
  const challengeToken = await signChallenge(options.challenge);
  const cookieStore = await cookies();
  cookieStore.set(REG_CHALLENGE_COOKIE, challengeToken, {
    ...sessionCookieOptions(5 * 60), // 5 minutes
  });

  return Response.json(options);
}
