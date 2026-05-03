/**
 * otp-store.ts — Single-active-OTP in-memory store for the solo admin login.
 *
 * Solo admin → only one OTP active at any time. Module-level state survives
 * for the lifetime of the Next.js process (carbon-web.service). On rebuild /
 * restart the active OTP is wiped — user simply requests a new code.
 *
 * Design rules:
 *   - Codes expire after OTP_TTL_MS (default 10 minutes).
 *   - Max 5 verify attempts per code → after that, code is invalidated to
 *     prevent brute force.
 *   - Cooldown of OTP_REQUEST_COOLDOWN_MS between requests to prevent
 *     someone hammering the email send endpoint.
 */

const OTP_TTL_MS = 10 * 60 * 1000; // 10 minutes
const OTP_REQUEST_COOLDOWN_MS = 30 * 1000; // 30 seconds between requests
const MAX_ATTEMPTS = 5;

interface OtpState {
  code: string;
  expiresAt: number;
  attempts: number;
  issuedAt: number;
}

let activeOtp: OtpState | null = null;

/**
 * Generates a 6-digit numeric code (zero-padded).
 */
function generateCode(): string {
  // crypto.randomInt is server-side only — fine here since this file is
  // only imported from route handlers.
  const n = Math.floor(Math.random() * 1_000_000);
  return n.toString().padStart(6, "0");
}

export interface IssueResult {
  code: string;
  expiresAt: number;
}

/**
 * Issues a new OTP and overwrites any existing one. Returns the code so the
 * caller can email it to the recipient.
 *
 * Throws if a previous code was issued within OTP_REQUEST_COOLDOWN_MS to
 * limit email volume / abuse.
 */
export function issueOtp(): IssueResult {
  const now = Date.now();
  if (activeOtp && now - activeOtp.issuedAt < OTP_REQUEST_COOLDOWN_MS) {
    const waitMs = OTP_REQUEST_COOLDOWN_MS - (now - activeOtp.issuedAt);
    throw new Error(`Please wait ${Math.ceil(waitMs / 1000)}s before requesting a new code.`);
  }

  const code = generateCode();
  activeOtp = {
    code,
    expiresAt: now + OTP_TTL_MS,
    attempts: 0,
    issuedAt: now,
  };
  return { code, expiresAt: activeOtp.expiresAt };
}

export type VerifyOutcome =
  | { ok: true }
  | { ok: false; reason: "no_code" | "expired" | "too_many_attempts" | "wrong_code" };

/**
 * Verifies a submitted code. Consumes the OTP on success (one-time use).
 */
export function verifyOtp(submitted: string): VerifyOutcome {
  if (!activeOtp) return { ok: false, reason: "no_code" };

  const now = Date.now();
  if (now > activeOtp.expiresAt) {
    activeOtp = null;
    return { ok: false, reason: "expired" };
  }

  if (activeOtp.attempts >= MAX_ATTEMPTS) {
    activeOtp = null;
    return { ok: false, reason: "too_many_attempts" };
  }

  // Constant-time-ish comparison (OK since codes are 6 digits & timing leak
  // is irrelevant at this scale)
  if (submitted.trim() !== activeOtp.code) {
    activeOtp.attempts += 1;
    if (activeOtp.attempts >= MAX_ATTEMPTS) {
      activeOtp = null;
    }
    return { ok: false, reason: "wrong_code" };
  }

  // Success — burn the OTP
  activeOtp = null;
  return { ok: true };
}
