/**
 * email.ts — SMTP transport for transactional email (OTP login codes).
 *
 * Uses Infomaniak SMTP (mail.infomaniak.com:587 STARTTLS). All credentials
 * read from env vars; the module fails fast on missing config so production
 * never silently sends nothing.
 *
 * Env vars expected:
 *   SMTP_HOST       — hostname (default mail.infomaniak.com)
 *   SMTP_PORT       — port (default 587)
 *   SMTP_USER       — full mailbox address used as auth username AND From
 *   SMTP_PASSWORD   — mailbox password
 *   OTP_RECIPIENT   — where to send OTP codes (default = SMTP_USER)
 */

import nodemailer from "nodemailer";
import type { Transporter } from "nodemailer";

let cachedTransporter: Transporter | null = null;

function getTransporter(): Transporter {
  if (cachedTransporter) return cachedTransporter;

  const host = process.env.SMTP_HOST ?? "mail.infomaniak.com";
  const port = Number(process.env.SMTP_PORT ?? "587");
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASSWORD;

  if (!user || !pass) {
    throw new Error(
      "SMTP_USER and SMTP_PASSWORD env vars are required to send OTP emails."
    );
  }

  cachedTransporter = nodemailer.createTransport({
    host,
    port,
    secure: false, // STARTTLS, not implicit TLS — port 587
    requireTLS: true,
    auth: { user, pass },
  });
  return cachedTransporter;
}

export function getOtpRecipient(): string {
  const recipient = process.env.OTP_RECIPIENT ?? process.env.SMTP_USER;
  if (!recipient) {
    throw new Error("OTP_RECIPIENT (or SMTP_USER fallback) is not configured.");
  }
  return recipient;
}

export async function sendOtpEmail(code: string): Promise<void> {
  const transporter = getTransporter();
  const from = process.env.SMTP_USER!;
  const to = getOtpRecipient();

  await transporter.sendMail({
    from: `"CARBON WORLD admin" <${from}>`,
    to,
    subject: `CBWD admin login code: ${code}`,
    text:
      `Your CARBON WORLD admin login code is:\n\n` +
      `   ${code}\n\n` +
      `It expires in 10 minutes. If you did not request this, ignore this email.\n\n` +
      `— CARBON WORLD`,
  });
}
