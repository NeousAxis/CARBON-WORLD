/**
 * POST /api/auth/otp/request
 *
 * Issues a fresh 6-digit OTP, emails it to OTP_RECIPIENT
 * (default = SMTP_USER = hello@carbon-world.xyz). Always returns 200 to
 * avoid leaking whether email config is healthy to anonymous callers, but
 * the server logs the real error.
 */

import { issueOtp } from "@/lib/otp-store";
import { sendOtpEmail, getOtpRecipient } from "@/lib/email";

export async function POST() {
  try {
    const { code, expiresAt } = issueOtp();
    await sendOtpEmail(code);
    return Response.json({
      ok: true,
      recipient: maskEmail(getOtpRecipient()),
      expiresAt,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    // Cooldown error → return 429 so the client can show "wait Xs"
    if (msg.toLowerCase().includes("please wait")) {
      return Response.json({ error: msg }, { status: 429 });
    }
    console.error("[auth/otp/request] failed:", msg);
    return Response.json(
      { error: "Could not send OTP email. Check server logs." },
      { status: 500 }
    );
  }
}

/** Mask a@b.tld → a***@b.tld (informational only, no security claim). */
function maskEmail(email: string): string {
  const [local, domain] = email.split("@");
  if (!local || !domain) return email;
  const visible = local.slice(0, 1);
  return `${visible}${"*".repeat(Math.max(0, local.length - 1))}@${domain}`;
}
