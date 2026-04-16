"""
writer.py — Agent: persists scored events to the SQLite database.
Pure Python, no LLM required. Uses db.py for actual DB operations.
"""

import logging
from datetime import datetime, timezone

from db import save_event, event_exists

logger = logging.getLogger("agent.writer")


def _build_justification(analysis: dict) -> str:
    """Combine justification and ethical_synthesis, truncated to 500 chars."""
    justification = analysis.get("justification", "")
    synthesis = analysis.get("ethical_synthesis", "")
    if synthesis and justification:
        combined = f"{justification} | {synthesis}"
    else:
        combined = justification or synthesis
    return combined[:500]


def write(event: dict) -> bool:
    """
    Write a single scored event to the database.
    Returns True if saved successfully, False otherwise.
    """
    article = event["article"]
    analysis = event["analysis"]
    title = article.get("title", "")
    link = article.get("link", "")

    # Skip if already exists (double safety net)
    if event_exists(link):
        logger.info("Already in DB, skipping: '%s'", title[:60])
        return False

    event_data = {
        "event_title": title[:500],
        "event_url": link,
        "event_source": article.get("source", ""),
        "decision": analysis.get("decision", "NEUTRAL"),
        "amount_crbn": analysis.get("amount_cbwd", 0),
        "final_score": analysis.get("final_score", 0.0),
        "confidence": analysis.get("confidence", 0),
        "justification": _build_justification(analysis),
        "tx_hash": None,  # Phase 4: Solana integration
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    saved = save_event(event_data)
    if saved:
        logger.info(
            "Saved: [%s] %d CBWD | '%s' (id=%s)",
            event_data["decision"],
            event_data["amount_crbn"],
            title[:50],
            saved.get("id", "?"),
        )
        return True
    else:
        logger.warning("Failed to save: '%s'", title[:60])
        return False


def write_batch(events: list[dict]) -> int:
    """Write a batch of scored events. Returns the count of successfully saved events."""
    saved_count = 0
    for event in events:
        if write(event):
            saved_count += 1
    logger.info("Writer done: %d/%d events saved.", saved_count, len(events))
    return saved_count
