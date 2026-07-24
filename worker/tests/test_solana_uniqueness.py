"""
test_solana_uniqueness.py — Unit tests for the per-event transaction memo in
worker/solana_executor.py.

Regression guard for the duplicate-signature bug found on 2026-07-24: 160
signatures were shared by 323 rows of carbon_events, because a transaction was
built from (signer, amount, blockhash) only. Two events with the same decision
and the same amount inside one blockhash window serialized to identical bytes,
so Solana returned the same signature for both and only ONE transfer landed.

Run with:
    cd /Users/cyrilleger/CARBON-WORLD
    source venv/bin/activate
    python -m pytest worker/tests/test_solana_uniqueness.py -v
"""

import os
import sys

# Allow importing from worker/ when running pytest from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from solders.hash import Hash  # type: ignore
from solders.message import Message  # type: ignore
from solders.pubkey import Pubkey  # type: ignore

from solana_executor import (
    MEMO_PROGRAM_ID,
    _build_burn_ix,
    build_memo,
    build_message,
    MINT_ADDRESS,
    TREASURY_ATA,
)

AUTHORITY = Pubkey.from_string("2LJspFTWw5VFTZjRNo9Va1VQTEjARAjSuCH7LR6K8AZW")
BLOCKHASH = Hash.default()
AMOUNT = 500_000 * (10 ** 6)


def _message(decision, event_id, amount=AMOUNT):
    return build_message(
        decision, amount, AUTHORITY, BLOCKHASH, build_memo(decision, event_id)
    )


# ---------------------------------------------------------------------------
# Tests: memo payload
# ---------------------------------------------------------------------------

class TestBuildMemo:

    def test_memo_carries_decision_and_event_id(self):
        assert build_memo("BURN", 5558) == "CBWD:BURN:5558"
        assert build_memo("MINT", 42) == "CBWD:MINT:42"

    def test_memo_is_stable_for_the_same_event(self):
        assert build_memo("BURN", 5558) == build_memo("BURN", 5558)

    def test_memo_differs_between_events(self):
        assert build_memo("BURN", 5558) != build_memo("BURN", 5559)

    def test_memo_without_event_id_falls_back_to_a_random_nonce(self):
        first = build_memo("BURN", None)
        second = build_memo("BURN", None)
        assert first.startswith("CBWD:BURN:anon-")
        assert first != second


# ---------------------------------------------------------------------------
# Tests: transaction uniqueness (the actual bug)
# ---------------------------------------------------------------------------

class TestTransactionUniqueness:

    def test_events_5558_and_5559_no_longer_serialize_identically(self):
        """The exact pair that shared signature 4iBK37eK... on 2026-07-24."""
        a = _message("BURN", 5558)
        b = _message("BURN", 5559)
        assert bytes(a) != bytes(b)

    def test_same_event_replayed_on_same_blockhash_stays_identical(self):
        """A retry of one event must stay byte-identical, so it dedupes safely."""
        a = _message("BURN", 5558)
        b = _message("BURN", 5558)
        assert bytes(a) == bytes(b)

    def test_mint_events_with_equal_amounts_differ(self):
        assert bytes(_message("MINT", 100)) != bytes(_message("MINT", 101))

    def test_without_a_memo_the_bug_reproduces(self):
        """Control: the old single-instruction build collided by construction."""
        old_a = Message.new_with_blockhash(
            [_build_burn_ix(TREASURY_ATA, MINT_ADDRESS, AUTHORITY, AMOUNT)],
            AUTHORITY,
            BLOCKHASH,
        )
        old_b = Message.new_with_blockhash(
            [_build_burn_ix(TREASURY_ATA, MINT_ADDRESS, AUTHORITY, AMOUNT)],
            AUTHORITY,
            BLOCKHASH,
        )
        assert bytes(old_a) == bytes(old_b)


# ---------------------------------------------------------------------------
# Tests: transaction shape
# ---------------------------------------------------------------------------

class TestMessageShape:

    def test_token_instruction_comes_first_then_memo(self):
        msg = _message("BURN", 5558)
        assert len(msg.instructions) == 2
        programs = [msg.account_keys[ix.program_id_index] for ix in msg.instructions]
        assert programs[1] == MEMO_PROGRAM_ID

    def test_memo_data_is_readable_on_chain(self):
        msg = _message("MINT", 777)
        memo_ix = msg.instructions[1]
        assert bytes(memo_ix.data).decode("utf-8") == "CBWD:MINT:777"

    def test_memo_instruction_needs_no_accounts(self):
        msg = _message("BURN", 1)
        assert list(msg.instructions[1].accounts) == []
