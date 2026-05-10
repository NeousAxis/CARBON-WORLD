"""
notify_review_backlog.py — Daily email digest of the human review backlog.

Sends an email to ADMIN_EMAIL via Infomaniak SMTP when the number of pending
review_queue items is at or above NOTIFY_THRESHOLD (default 5). Skips the
email entirely if the queue is below threshold to avoid noise.

Reuses the same SMTP configuration as the OTP login flow
(`web/src/lib/email.ts`) so there is one place to manage credentials. The
script loads `web/.env.local` (where the existing OTP creds already live)
without depending on python-dotenv — environments are simple key=value.

Triggered by: launcher/notify_review_backlog_daily.sh (cron 09:00 CEST)

Env vars (read from web/.env.local on the VPS):
  SMTP_HOST           — default mail.infomaniak.com
  SMTP_PORT           — default 587
  SMTP_USER           — required: full mailbox + From address
  SMTP_PASSWORD       — required
  ADMIN_EMAIL         — required: notification destination
  NOTIFY_THRESHOLD    — optional, default 5 (skip email when pending < this)

Exit code is always 0 unless SMTP itself errors — a "below threshold, no
email" run is a healthy state, not a failure.
"""

from __future__ import annotations

import logging
import os
import smtplib
import sqlite3
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Ensure worker/ is importable when run directly
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "worker"))

from config import DB_PATH  # noqa: E402

logger = logging.getLogger("notify_review_backlog")

DEFAULT_SMTP_HOST = "mail.infomaniak.com"
DEFAULT_SMTP_PORT = 587
DEFAULT_THRESHOLD = 5

WEB_ENV_PATH = ROOT / "web" / ".env.local"
ROOT_ENV_PATH = ROOT / ".env"


def _load_env_file(path: Path) -> None:
    """Light-weight .env loader — no external dependency. Only sets variables
    that are NOT already in os.environ, so a real env always wins."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        # Strip surrounding quotes if present
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if key and key not in os.environ:
            os.environ[key] = val


def _load_env() -> None:
    # web/.env.local is the canonical place for SMTP creds (used by the Next
    # OTP route); root .env is loaded as a fallback so a future operator can
    # consolidate without breaking this script.
    _load_env_file(WEB_ENV_PATH)
    _load_env_file(ROOT_ENV_PATH)


def fetch_backlog_summary() -> dict:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        total = con.execute(
            "SELECT COUNT(*) AS n FROM review_queue WHERE status = 'pending'"
        ).fetchone()["n"]

        if total == 0:
            return {"total": 0, "rows": [], "buckets": {}}

        # Bucket by structural flag prefix in sentinel_concern.
        buckets_raw = con.execute("""
            SELECT
              CASE
                WHEN sentinel_concern LIKE 'structural:%missing_positive%missing_negative%' THEN 'both lists empty'
                WHEN sentinel_concern LIKE 'structural:%missing_negative%' THEN 'missing negative aspects'
                WHEN sentinel_concern LIKE 'structural:%missing_positive%' THEN 'missing positive aspects'
                WHEN sentinel_concern LIKE 'structural:%fragile_burn%' THEN 'fragile BURN threshold'
                WHEN sentinel_concern LIKE 'structural:%fragile_mint%' THEN 'fragile MINT threshold'
                WHEN sentinel_concern LIKE 'structural:%disagreement%' THEN 'A/B disagreement'
                WHEN sentinel_concern LIKE 'structural:%' THEN 'other structural flag'
                ELSE 'LLM Sentinel concern'
              END AS bucket,
              COUNT(*) AS n
            FROM review_queue
            WHERE status = 'pending'
            GROUP BY bucket
            ORDER BY n DESC
        """).fetchall()
        buckets = {row["bucket"]: row["n"] for row in buckets_raw}

        # Top 10 newest pending rows for the email body.
        rows = con.execute("""
            SELECT id, event_title, event_source, suggested_decision,
                   suggested_amount_crbn, sentinel_concern, created_at
            FROM review_queue
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()

        return {"total": total, "rows": [dict(r) for r in rows], "buckets": buckets}
    finally:
        con.close()


def _format_amount(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _format_age(iso_ts: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except ValueError:
        return "?"
    delta = datetime.now(tz=timezone.utc) - dt
    hours = int(delta.total_seconds() // 3600)
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


def build_text_body(summary: dict) -> str:
    total = summary["total"]
    lines = [
        f"CARBON WORLD — review queue digest",
        f"",
        f"{total} events are waiting for your review on https://carbon-world.xyz/review",
        f"",
        f"By trigger:",
    ]
    for label, n in summary["buckets"].items():
        lines.append(f"  - {label}: {n}")
    lines.append("")
    lines.append("Most recent (top 10):")
    for r in summary["rows"]:
        amt = _format_amount(int(r["suggested_amount_crbn"] or 0))
        age = _format_age(r["created_at"])
        title = (r["event_title"] or "")[:80]
        lines.append(
            f"  #{r['id']:>4}  [{r['suggested_decision']:<7} {amt:>6}]  {age:>4} ago  {title}"
        )
    lines.append("")
    lines.append("— carbon-world.xyz")
    return "\n".join(lines)


def build_html_body(summary: dict) -> str:
    total = summary["total"]
    bucket_rows = "".join(
        f'<tr><td style="padding:6px 12px;color:#B8B9B6;">{label}</td>'
        f'<td style="padding:6px 12px;color:#FFFFFF;text-align:right;font-weight:700;">{n}</td></tr>'
        for label, n in summary["buckets"].items()
    )
    item_rows = "".join(
        '<tr>'
        f'<td style="padding:6px 12px;color:#FF8400;font-weight:700;">#{r["id"]}</td>'
        f'<td style="padding:6px 12px;color:#B8B9B6;font-size:11px;">'
        f'{r["suggested_decision"]} {_format_amount(int(r["suggested_amount_crbn"] or 0))}'
        f'</td>'
        f'<td style="padding:6px 12px;color:#666666;font-size:11px;">{_format_age(r["created_at"])} ago</td>'
        f'<td style="padding:6px 12px;color:#FFFFFF;">{(r["event_title"] or "")[:90]}</td>'
        '</tr>'
        for r in summary["rows"]
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#111111;font-family:'JetBrains Mono','SF Mono',Menlo,Consolas,monospace;color:#FFFFFF;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#111111;padding:32px 16px;">
<tr><td align="center">
<table role="presentation" width="100%" style="max-width:680px;background:#1A1A1A;border:1px solid #2E2E2E;">
<tr><td style="padding:24px 24px 12px 24px;border-bottom:1px solid #2E2E2E;">
<div style="font-size:13px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:#B6FFCE;">CARBON <span style="color:#0190A0;">WORLD</span></div>
<div style="margin-top:6px;font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#B8B9B6;">Review queue digest</div>
</td></tr>
<tr><td style="padding:28px 24px 12px 24px;">
<div style="font-size:11px;letter-spacing:0.22em;text-transform:uppercase;color:#0190A0;">Pending events</div>
<div style="font-size:48px;font-weight:700;color:#FF8400;line-height:1;margin-top:6px;">{total}</div>
<div style="font-size:12px;color:#B8B9B6;margin-top:8px;">
<a href="https://carbon-world.xyz/review" style="color:#FF8400;text-decoration:none;">https://carbon-world.xyz/review →</a>
</div>
</td></tr>
<tr><td style="padding:8px 24px;">
<div style="font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#0190A0;margin:16px 0 8px 0;">By trigger</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #2E2E2E;">{bucket_rows}</table>
</td></tr>
<tr><td style="padding:8px 24px 24px 24px;">
<div style="font-size:11px;letter-spacing:0.18em;text-transform:uppercase;color:#0190A0;margin:16px 0 8px 0;">Most recent (top 10)</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #2E2E2E;font-size:11px;">{item_rows}</table>
</td></tr>
<tr><td style="padding:12px 24px;border-top:1px solid #2E2E2E;font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:#666666;">
<a href="https://carbon-world.xyz/review" style="color:#B8B9B6;text-decoration:none;">carbon-world.xyz/review</a>
</td></tr>
</table>
</td></tr></table></body></html>"""


def send_digest(summary: dict) -> None:
    host = os.environ.get("SMTP_HOST", DEFAULT_SMTP_HOST)
    port = int(os.environ.get("SMTP_PORT", DEFAULT_SMTP_PORT))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    to = os.environ.get("ADMIN_EMAIL")

    if not user or not password:
        raise RuntimeError("SMTP_USER and SMTP_PASSWORD must be set in env")
    if not to:
        raise RuntimeError("ADMIN_EMAIL must be set in env")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"CARBON WORLD — {summary['total']} reviews pending"
    msg["From"] = f"CARBON WORLD <{user}>"
    msg["To"] = to
    msg.attach(MIMEText(build_text_body(summary), "plain", "utf-8"))
    msg.attach(MIMEText(build_html_body(summary), "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(user, password)
        smtp.send_message(msg)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _load_env()

    threshold = int(os.environ.get("NOTIFY_THRESHOLD", DEFAULT_THRESHOLD))

    summary = fetch_backlog_summary()
    total = summary["total"]
    logger.info("Pending review_queue items: %d (threshold=%d)", total, threshold)

    if total < threshold:
        logger.info("Below threshold — no email sent.")
        return 0

    try:
        send_digest(summary)
        logger.info("Digest email sent to %s.", os.environ.get("ADMIN_EMAIL"))
    except Exception as exc:
        logger.error("SMTP send failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
