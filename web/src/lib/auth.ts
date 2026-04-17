/**
 * auth.ts — Server-only authentication utilities for CARBON WORLD.
 *
 * Covers:
 *  - WebAuthn credential persistence (env var + dev .credential.json fallback)
 *  - JWT session signing / verification (jose, HS256)
 *  - Challenge signing / verification (short-lived JWT for challenge cookies)
 *
 * This module must only be imported from Server Components, Route Handlers,
 * or Server Functions — never from "use client" modules.
 */

import { SignJWT, jwtVerify } from "jose";
import fs from "fs";
import path from "path";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

export const RP_NAME = "Carbon World Admin";
export const RP_ID = process.env.RP_ID ?? "localhost";
export const RP_ORIGIN = process.env.RP_ORIGIN ?? "http://localhost:3000";

const DEV_CREDENTIAL_PATH = path.join(process.cwd(), ".credential.json");

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
// Stored credential shape
// ---------------------------------------------------------------------------

/**
 * The shape we persist in the PASSKEY_CREDENTIAL env var (and .credential.json
 * in dev). publicKey is base64-encoded (standard, not base64url) because env
 * vars / JSON must carry it as a string.
 */
export interface StoredCredential {
  id: string; // base64url credential ID
  publicKey: string; // base64-encoded Uint8Array
  counter: number;
  transports?: string[];
}

// ---------------------------------------------------------------------------
// getCredential / saveCredential
// ---------------------------------------------------------------------------

/**
 * Returns the registered WebAuthn credential, or null if none has been
 * registered yet. Reads PASSKEY_CREDENTIAL env var first; falls back to
 * .credential.json in dev (process.cwd()).
 */
export function getCredential(): StoredCredential | null {
  // 1. Try env var
  const raw = process.env.PASSKEY_CREDENTIAL;
  if (raw && raw.trim().length > 0) {
    try {
      const json = Buffer.from(raw.trim(), "base64").toString("utf-8");
      return JSON.parse(json) as StoredCredential;
    } catch {
      console.error("[auth] Failed to parse PASSKEY_CREDENTIAL env var");
    }
  }

  // 2. Dev fallback: .credential.json
  if (process.env.NODE_ENV !== "production") {
    try {
      if (fs.existsSync(DEV_CREDENTIAL_PATH)) {
        const json = fs.readFileSync(DEV_CREDENTIAL_PATH, "utf-8");
        return JSON.parse(json) as StoredCredential;
      }
    } catch {
      // ignore — file may not exist yet
    }
  }

  return null;
}

/**
 * Persists a newly registered credential.
 *
 * Because we cannot write env vars at runtime, this function:
 *  1. Encodes the credential as base64(JSON) and logs it to stdout with clear
 *     markers so you can copy it into the PASSKEY_CREDENTIAL env var.
 *  2. In non-production, writes it to .credential.json for dev convenience.
 *  3. Returns the base64 string so the /review/setup UI can display it.
 */
export function saveCredential(cred: StoredCredential): string {
  const json = JSON.stringify(cred);
  const base64 = Buffer.from(json).toString("base64");

  // Always log so the operator can copy it
  console.log("\n");
  console.log("=".repeat(72));
  console.log("PASSKEY CREDENTIAL REGISTERED — copy the value below into");
  console.log("the PASSKEY_CREDENTIAL environment variable, then redeploy.");
  console.log("=".repeat(72));
  console.log(base64);
  console.log("=".repeat(72));
  console.log("\n");

  // Dev: write to .credential.json so it survives server restarts
  if (process.env.NODE_ENV !== "production") {
    try {
      fs.writeFileSync(DEV_CREDENTIAL_PATH, json, "utf-8");
      console.log(`[auth] Dev: credential written to ${DEV_CREDENTIAL_PATH}`);
    } catch (e) {
      console.warn("[auth] Dev: could not write .credential.json:", e);
    }
  }

  return base64;
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
// Challenge JWT (stateless one-time challenges via signed cookies)
// ---------------------------------------------------------------------------

/**
 * Signs a WebAuthn challenge string into a short-lived JWT (5 min).
 * We store this in an httpOnly cookie so no DB / Redis is needed.
 */
export async function signChallenge(challenge: string): Promise<string> {
  return new SignJWT({ chal: challenge })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("5m")
    .sign(getSessionSecret());
}

/**
 * Verifies a challenge cookie JWT. Returns the challenge string or null.
 */
export async function verifyChallenge(token: string): Promise<string | null> {
  try {
    const { payload } = await jwtVerify(token, getSessionSecret());
    const chal = (payload as Record<string, unknown>).chal;
    if (typeof chal !== "string" || !chal) return null;
    return chal;
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Cookie helpers (shared options)
// ---------------------------------------------------------------------------

const isProduction = process.env.NODE_ENV === "production";

export const SESSION_COOKIE = "cbwd-session";
export const REG_CHALLENGE_COOKIE = "cbwd-reg-challenge";
export const AUTH_CHALLENGE_COOKIE = "cbwd-auth-challenge";

export function sessionCookieOptions(maxAge: number) {
  return {
    httpOnly: true,
    secure: isProduction,
    sameSite: "lax" as const,
    path: "/",
    maxAge,
  };
}
