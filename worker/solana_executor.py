"""
solana_executor.py — Executes Solana mint/burn transactions for the CBWD token.

MINT: creates new CBWD tokens (negative decision — punitive supply increase)
BURN: destroys CBWD tokens (positive decision — rewarding supply decrease)
NEUTRAL: no-op
"""

import json
import logging
import struct
import time
import uuid
from pathlib import Path
from typing import Optional

from solana.rpc.api import Client
from solders.keypair import Keypair  # type: ignore
from solders.pubkey import Pubkey  # type: ignore
from solders.instruction import Instruction, AccountMeta  # type: ignore
from solders.transaction import Transaction  # type: ignore
from solders.message import Message  # type: ignore

logger = logging.getLogger("solana_executor")

# ── Constants ────────────────────────────────────────────────────────────────

# Network selection via env var: "mainnet" (default) or "devnet"
import os
SOLANA_NETWORK = os.getenv("SOLANA_NETWORK", "mainnet")

if SOLANA_NETWORK == "devnet":
    RPC_URL = "https://api.devnet.solana.com"
    MINT_ADDRESS = Pubkey.from_string("HRqmMnbA18VgstcfjCueAuzVZEoHHbLbbu973AqmK3Fs")
    TREASURY_ATA = Pubkey.from_string("2iNtuKTthWRGiDoK4VZYQJ7dC8t4d2DkR1dbLQx5QqFK")
else:  # mainnet
    RPC_URL = "https://api.mainnet-beta.solana.com"
    MINT_ADDRESS = Pubkey.from_string("Ewd57GaqZHx8xN7roqqEr6wz6RGxticPVaWFZneMncLm")
    TREASURY_ATA = Pubkey.from_string("DZnTxVL5qo7aG8eEUMdLc5i2Ji9S46zZcGDBk2ha3PTq")

KEYPAIR_PATH = Path.home() / ".config" / "solana" / "id.json"
TOKEN_PROGRAM_ID = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
MEMO_PROGRAM_ID = Pubkey.from_string("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr")
DECIMALS = 6

# How long to wait for the network to confirm a broadcast transaction before
# giving up. Kept well under the 120 s execFile timeout of the web review
# route (which also sleeps 5 s before broadcasting).
CONFIRM_TIMEOUT_S = float(os.getenv("SOLANA_CONFIRM_TIMEOUT", "45"))
CONFIRM_POLL_S = 2.0


# ── SPL Token instruction builders (manual, no spl-token dependency) ─────────

def _build_mint_to_ix(mint: Pubkey, dest: Pubkey, authority: Pubkey, amount: int) -> Instruction:
    """Build a SPL Token MintTo instruction (opcode 7)."""
    data = struct.pack("<BQ", 7, amount)
    accounts = [
        AccountMeta(pubkey=mint, is_signer=False, is_writable=True),
        AccountMeta(pubkey=dest, is_signer=False, is_writable=True),
        AccountMeta(pubkey=authority, is_signer=True, is_writable=False),
    ]
    return Instruction(program_id=TOKEN_PROGRAM_ID, data=data, accounts=accounts)


def _build_burn_ix(account: Pubkey, mint: Pubkey, owner: Pubkey, amount: int) -> Instruction:
    """Build a SPL Token Burn instruction (opcode 8)."""
    data = struct.pack("<BQ", 8, amount)
    accounts = [
        AccountMeta(pubkey=account, is_signer=False, is_writable=True),
        AccountMeta(pubkey=mint, is_signer=False, is_writable=True),
        AccountMeta(pubkey=owner, is_signer=True, is_writable=False),
    ]
    return Instruction(program_id=TOKEN_PROGRAM_ID, data=data, accounts=accounts)


def _build_memo_ix(memo: str) -> Instruction:
    """Build an SPL Memo instruction (no accounts — it only writes to the log)."""
    return Instruction(program_id=MEMO_PROGRAM_ID, data=memo.encode("utf-8"), accounts=[])


# ── Transaction assembly ─────────────────────────────────────────────────────

def build_memo(decision: str, event_id: Optional[int]) -> str:
    """
    Build the per-event memo payload.

    The memo is what makes every transaction unique. Without it, two events
    sharing a decision, an amount and a blockhash window serialize to the exact
    same bytes, so Solana returns the same signature for both and only ONE
    transfer lands — while the DB records both as executed (bug found
    2026-07-24: 160 duplicated signatures over 323 rows).

    It doubles as on-chain provenance: the event id is readable straight from
    Solana Explorer.
    """
    if event_id is not None:
        return f"CBWD:{decision}:{event_id}"
    # No event id available — fall back to a random nonce so we can never
    # silently collide with another transaction again.
    return f"CBWD:{decision}:anon-{uuid.uuid4().hex[:12]}"


def build_message(
    decision: str,
    raw_amount: int,
    authority: Pubkey,
    recent_blockhash,
    memo: str,
) -> Message:
    """Assemble the unsigned message for a MINT or BURN, memo instruction included."""
    if decision == "MINT":
        token_ix = _build_mint_to_ix(MINT_ADDRESS, TREASURY_ATA, authority, raw_amount)
    else:
        token_ix = _build_burn_ix(TREASURY_ATA, MINT_ADDRESS, authority, raw_amount)

    return Message.new_with_blockhash(
        [token_ix, _build_memo_ix(memo)], authority, recent_blockhash
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_keypair() -> Keypair:
    """Load the Solana keypair from the default CLI wallet file."""
    data = json.loads(KEYPAIR_PATH.read_text())
    return Keypair.from_bytes(bytes(data))


def _get_client() -> Client:
    """Return a Solana RPC client pointing at the configured network."""
    return Client(RPC_URL)


def _await_confirmation(client: Client, signature) -> Optional[bool]:
    """
    Poll the signature status until the cluster has confirmed the transaction.

    Returns:
        True  — landed and succeeded.
        False — the cluster rejected it (definitively did not apply).
        None  — still unknown when the timeout expired.

    Waiting here also means the next event of the run picks up a fresh
    blockhash, which is the second half of the duplicate-signature fix.
    """
    if CONFIRM_TIMEOUT_S <= 0:
        return None

    deadline = time.monotonic() + CONFIRM_TIMEOUT_S
    while True:
        try:
            statuses = client.get_signature_statuses([signature]).value
            status = statuses[0] if statuses else None
        except Exception as exc:
            logger.warning("Signature status lookup failed: %s", exc)
            status = None

        if status is not None:
            if status.err is not None:
                logger.error("Transaction %s failed on-chain: %s", signature, status.err)
                return False
            level = str(getattr(status, "confirmation_status", "") or "").lower()
            if "confirmed" in level or "finalized" in level or status.confirmations is None:
                return True

        if time.monotonic() >= deadline:
            return None
        time.sleep(CONFIRM_POLL_S)


# ── Public API ───────────────────────────────────────────────────────────────

def execute_decision(
    decision: str,
    amount_crbn: int,
    event_id: Optional[int] = None,
) -> Optional[str]:
    """
    Execute the on-chain action corresponding to a pipeline decision.

    Args:
        decision: "MINT", "BURN", or "NEUTRAL".
        amount_crbn: Number of CBWD tokens (human-readable units).
        event_id: DB id of the event, embedded in the transaction memo so that
            two events with the same decision and amount never serialize to the
            same bytes (and therefore never share a signature).

    Returns:
        Transaction signature string on success, None on failure or NEUTRAL.
    """
    decision = decision.upper().strip()

    if decision == "NEUTRAL":
        logger.info("Decision is NEUTRAL — no on-chain action.")
        return None

    if decision not in ("MINT", "BURN"):
        logger.warning("Unknown decision '%s' — skipping on-chain action.", decision)
        return None

    if amount_crbn <= 0:
        logger.warning("amount_crbn=%d is not positive — skipping.", amount_crbn)
        return None

    raw_amount = amount_crbn * (10 ** DECIMALS)

    try:
        keypair = _load_keypair()
    except FileNotFoundError:
        logger.error("Keypair file not found at %s.", KEYPAIR_PATH)
        return None
    except Exception as exc:
        logger.error("Failed to load keypair: %s", exc)
        return None

    try:
        client = _get_client()
        authority = keypair.pubkey()

        memo = build_memo(decision, event_id)
        if decision == "MINT":
            logger.info("MINT: %d CBWD (%d raw) to treasury [%s]", amount_crbn, raw_amount, memo)
        else:
            logger.info("BURN: %d CBWD (%d raw) from treasury [%s]", amount_crbn, raw_amount, memo)

        # Get recent blockhash
        blockhash_resp = client.get_latest_blockhash(commitment="finalized")
        recent_blockhash = blockhash_resp.value.blockhash

        # Build and sign transaction
        msg = build_message(decision, raw_amount, authority, recent_blockhash, memo)
        tx = Transaction.new_unsigned(msg)
        tx.sign([keypair], recent_blockhash)

        # Send (skip_preflight to avoid devnet simulation timing issues)
        from solana.rpc.types import TxOpts
        opts = TxOpts(skip_preflight=True, preflight_commitment="finalized")
        resp = client.send_raw_transaction(bytes(tx), opts=opts)
        signature = resp.value
        sig = str(signature)

        confirmed = _await_confirmation(client, signature)
        if confirmed is False:
            logger.error(
                "%s of %d CBWD rejected on-chain (tx %s) — reporting failure so "
                "reconcile_tx can replay it.", decision, amount_crbn, sig,
            )
            return None
        if confirmed is None:
            # Unknown outcome. Record the signature anyway: replaying a
            # transaction that may in fact have landed would double the supply
            # move, which is worse than a signature awaiting manual audit.
            logger.warning(
                "%s of %d CBWD not confirmed within %.0fs — recording tx %s "
                "unverified. Check it on Solana Explorer.",
                decision, amount_crbn, CONFIRM_TIMEOUT_S, sig,
            )
            return sig

        logger.info("%s success — tx: %s", decision, sig)
        return sig

    except Exception as exc:
        logger.error("Solana %s failed for %d CBWD: %s", decision, amount_crbn, exc)
        return None
