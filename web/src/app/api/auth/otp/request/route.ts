/**
 * POST /api/auth/otp/request
 *
 * Body: { email: string }
 *
 * The user submits their email. The server checks it matches the
 * allowlisted admin email (ADMIN_EMAIL env var). If yes, generates a
 * 6-digit code, stores it in memory for 10 minutes, and sends it via
 * Infomaniak SMTP (Nodemailer).
 *
 * To avoid leaking which emails are authorized, the response is the same
 * shape (200 OK, masked recipient) whether or not the email matched —
 * but no code is actually sent if the email is not whitelisted.
 */

import { issueOtp } from "@/lib/otp-store";
import { sendOtpEmail } from "@/lib/email";

function isAdminEmail(submitted: string): boolean {
  const allowed = (process.env.ADMIN_EMAIL ?? "").trim().toLowerCase();
  if (!allowed) return false;
  return submitted.trim().toLowerCase() === allowed;
}

function maskEmail(email: string): string {
  const [local, domain] = email.split("@");
  if (!local || !domain) return email;
  const visible = local.slice(0, 1);
  return `${visible}${"*".repeat(Math.max(0, local.length - 1))}@${domain}`;
}

export async function POST(request: Request) {
  let body: unknown = {};
  try {
    body = await request.json();
  } catch {
    // empty body falls through and gets a generic error
  }

  const email = (body as { email?: string }).email;
  if (typeof email !== "string" || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return Response.json(
      { error: "Please enter a valid email address." },
      { status: 400 }
    );
  }

  // Constant-shape response: same body whether allowlisted or not.
  // Real email is sent only on match.
  const responsePayload = {
    ok: true,
    recipient: maskEmail(email),
  };

  if (!isAdminEmail(email)) {
    // Silent ignore — pretend we sent the code.
    return Response.json(responsePayload);
  }

  try {
    const { code } = issueOtp();
    await sendOtpEmail(email, code);
    return Response.json(responsePayload);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
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
