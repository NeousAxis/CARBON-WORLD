"""
generate_api_key.py — CLI tool to create a Tier 2 Partner or Enterprise API key.

Usage:
    python3 worker/generate_api_key.py <organization> <contact_email> \
        [--tier partner|enterprise] [--write-quota 5] [--notes "..."]

The raw key is printed ONCE and NEVER stored. Only the SHA-256 hash is saved in DB.
"""

import argparse
import hashlib
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from project root (python3 worker/generate_api_key.py ...)
_WORKER_DIR = Path(__file__).parent
sys.path.insert(0, str(_WORKER_DIR))

import config  # noqa: F401 — triggers env validation + sets DB_PATH
import sqlite3
from pathlib import Path as _P


def _get_conn() -> sqlite3.Connection:
    db_path = _P(config.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create api_keys table if not present (idempotent)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_hash TEXT NOT NULL UNIQUE,
            organization TEXT NOT NULL,
            contact_email TEXT NOT NULL,
            tier TEXT NOT NULL CHECK (tier IN ('partner', 'enterprise')),
            read_quota_daily INTEGER NOT NULL DEFAULT 0,
            write_quota_daily INTEGER NOT NULL DEFAULT 5,
            webhook_url TEXT,
            created_at TEXT NOT NULL,
            last_used_at TEXT,
            revoked_at TEXT,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
    """)
    conn.commit()


def generate_key(
    organization: str,
    contact_email: str,
    tier: str = "partner",
    write_quota: int = 5,
    notes: str = "",
) -> str:
    """
    Generate a new API key, store its SHA-256 hash in DB, and return the raw key.
    Raises ValueError on duplicate org+email, sqlite3.IntegrityError on hash collision (vanishingly rare).
    """
    raw_key = secrets.token_urlsafe(32)  # ~43 URL-safe chars
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    now = datetime.now(tz=timezone.utc).isoformat()

    conn = _get_conn()
    _ensure_tables(conn)

    # Check for existing non-revoked key for same org+email
    existing = conn.execute(
        "SELECT id FROM api_keys WHERE organization = ? AND contact_email = ? AND revoked_at IS NULL",
        (organization, contact_email),
    ).fetchone()
    if existing:
        conn.close()
        raise ValueError(
            f"An active key already exists for '{organization}' / '{contact_email}'. "
            "Revoke the existing key first (set revoked_at) before generating a new one."
        )

    read_quota = 0  # 0 = unlimited for partner/enterprise

    conn.execute(
        """
        INSERT INTO api_keys
            (key_hash, organization, contact_email, tier,
             read_quota_daily, write_quota_daily,
             created_at, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (key_hash, organization, contact_email, tier,
         read_quota, write_quota, now, notes or None),
    )
    conn.commit()
    conn.close()
    return raw_key


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a CARBON WORLD Tier 2 Partner API key.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 worker/generate_api_key.py "Amazon Watch" "api@amazonwatch.org"
  python3 worker/generate_api_key.py "The Shift Project" "contact@theshiftproject.org" --tier partner --write-quota 10
  python3 worker/generate_api_key.py "Acme Corp RSE" "rse@acme.com" --tier enterprise --notes "Enterprise trial"
        """,
    )
    parser.add_argument("organization", help="Partner organization name (shown in DB, audit logs)")
    parser.add_argument("contact_email", help="Contact email for the key owner")
    parser.add_argument(
        "--tier",
        choices=["partner", "enterprise"],
        default="partner",
        help="Key tier (default: partner)",
    )
    parser.add_argument(
        "--write-quota",
        type=int,
        default=5,
        dest="write_quota",
        help="Max write submissions per day (default: 5)",
    )
    parser.add_argument(
        "--notes",
        default="",
        help="Optional internal memo (not shown to key holder)",
    )

    args = parser.parse_args()

    try:
        raw_key = generate_key(
            organization=args.organization,
            contact_email=args.contact_email,
            tier=args.tier,
            write_quota=args.write_quota,
            notes=args.notes,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR generating key: {exc}", file=sys.stderr)
        return 1

    # Print key ONCE — never resaved
    print()
    print("=" * 60)
    print("  CARBON WORLD API KEY GENERATED")
    print("=" * 60)
    print(f"  Organization : {args.organization}")
    print(f"  Email        : {args.contact_email}")
    print(f"  Tier         : {args.tier}")
    print(f"  Write quota  : {args.write_quota} events/day")
    print()
    print(f"  KEY: {raw_key}")
    print()
    print("  WARNING: Store this key now — it will NOT be shown again.")
    print("  The database stores only the SHA-256 hash.")
    print("=" * 60)
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
