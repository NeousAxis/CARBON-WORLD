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

export async function sendOtpEmail(to: string, code: string): Promise<void> {
  const transporter = getTransporter();
  const from = process.env.SMTP_USER!;

  // Plain-text fallback (always sent, used by clients that block HTML)
  const text =
    `CARBON WORLD\n` +
    `ADMIN LOGIN CODE\n\n` +
    `${code}\n\n` +
    `This code expires in 10 minutes.\n` +
    `If you did not request it, ignore this email.\n\n` +
    `— carbon-world.xyz`;

  // HTML version — Lunaris Dark theme, monospace, branded
  const html = `<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>CARBON WORLD — admin login code</title>
  </head>
  <body style="margin:0;padding:0;background-color:#111111;font-family:'JetBrains Mono','SF Mono',Menlo,Consolas,monospace;color:#FFFFFF;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#111111;padding:40px 16px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" style="max-width:520px;background-color:#1A1A1A;border:1px solid #2E2E2E;">
            <tr>
              <td style="padding:32px 32px 16px 32px;border-bottom:1px solid #2E2E2E;">
                <div style="font-size:14px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#B6FFCE;">
                  CARBON <span style="color:#0190A0;">WORLD</span>
                </div>
                <div style="margin-top:6px;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#B8B9B6;">
                  Swiss-based · open-source · volunteer
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:36px 32px 8px 32px;">
                <div style="font-size:11px;letter-spacing:0.22em;text-transform:uppercase;color:#0190A0;">
                  ADMIN LOGIN CODE
                </div>
              </td>
            </tr>
            <tr>
              <td align="center" style="padding:24px 32px 24px 32px;">
                <div style="display:inline-block;padding:18px 28px;background-color:#111111;border:1px solid #2E2E2E;font-family:'JetBrains Mono','SF Mono',Menlo,Consolas,monospace;font-size:38px;font-weight:700;letter-spacing:0.32em;color:#FF8400;">
                  ${code}
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:8px 32px 32px 32px;font-size:13px;line-height:1.6;color:#B8B9B6;">
                This code expires in <strong style="color:#FFFFFF;">10 minutes</strong>.<br />
                If you did not request it, ignore this email.
              </td>
            </tr>
            <tr>
              <td style="padding:16px 32px;border-top:1px solid #2E2E2E;font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:#666666;">
                <a href="https://carbon-world.xyz" style="color:#B8B9B6;text-decoration:none;">carbon-world.xyz</a>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>`;

  await transporter.sendMail({
    from: `"CARBON WORLD" <${from}>`,
    to,
    subject: `CARBON WORLD — admin login code: ${code}`,
    text,
    html,
  });
}
