"""
solana_executor.py — Executes Solana mint/burn transactions for the CBWD token.

MINT: creates new CBWD tokens (negative decision — punitive supply increase)
BURN: destroys CBWD tokens (positive decision — rewarding supply decrease)
NEUTRAL: no-op
"""

import json
import logging
import struct
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
DECIMALS = 6


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


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_keypair() -> Keypair:
    """Load the Solana keypair from the default CLI wallet file."""
    data = json.loads(KEYPAIR_PATH.read_text())
    return Keypair.from_bytes(bytes(data))


def _get_client() -> Client:
    """Return a Solana RPC client pointing at the configured network."""
    return Client(RPC_URL)


# ── Public API ───────────────────────────────────────────────────────────────

def execute_decision(decision: str, amount_crbn: int) -> Optional[str]:
    """
    Execute the on-chain action corresponding to a pipeline decision.

    Args:
        decision: "MINT", "BURN", or "NEUTRAL".
        amount_crbn: Number of CBWD tokens (human-readable units).

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

        if decision == "MINT":
            ix = _build_mint_to_ix(MINT_ADDRESS, TREASURY_ATA, authority, raw_amount)
            logger.info("MINT: %d CBWD (%d raw) to treasury", amount_crbn, raw_amount)
        else:
            ix = _build_burn_ix(TREASURY_ATA, MINT_ADDRESS, authority, raw_amount)
            logger.info("BURN: %d CBWD (%d raw) from treasury", amount_crbn, raw_amount)

        # Get recent blockhash
        blockhash_resp = client.get_latest_blockhash(commitment="finalized")
        recent_blockhash = blockhash_resp.value.blockhash

        # Build and sign transaction
        msg = Message.new_with_blockhash([ix], authority, recent_blockhash)
        tx = Transaction.new_unsigned(msg)
        tx.sign([keypair], recent_blockhash)

        # Send (skip_preflight to avoid devnet simulation timing issues)
        from solana.rpc.types import TxOpts
        opts = TxOpts(skip_preflight=True, preflight_commitment="finalized")
        resp = client.send_raw_transaction(bytes(tx), opts=opts)
        sig = str(resp.value)

        logger.info("%s success — tx: %s", decision, sig)
        return sig

    except Exception as exc:
        logger.error("Solana %s failed for %d CBWD: %s", decision, amount_crbn, exc)
        return None
