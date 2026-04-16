"""
reporter.py — Agent: generates a structured summary of each pipeline run.
Pure Python, no LLM required.
"""

import logging

logger = logging.getLogger("agent.reporter")


def report(
    total_collected: int,
    total_new: int,
    total_classified: int,
    valid_count: int,
    invalid_count: int,
    analyzed_count: int,
    neutral_count: int,
    scored_count: int,
    saved_count: int,
    events: list[dict],
) -> str:
    """
    Generate and log a human-readable run summary.
    Returns the summary string.
    """
    lines = [
        "",
        "=" * 60,
        "  CARBON WORLD — Run Summary",
        "=" * 60,
        f"  Collected:    {total_collected} articles from RSS",
        f"  New:          {total_new} (after dedup with DB)",
        f"  Classified:   {total_classified} (capped by MAX_ARTICLES_PER_RUN)",
        f"    Valid:      {valid_count}",
        f"    Invalid:    {invalid_count}",
        f"  Analyzed:     {analyzed_count} (deep 4D ethical)",
        f"    Neutral:    {neutral_count}",
        f"    Actionable: {scored_count}",
        f"  Saved to DB:  {saved_count}",
    ]

    if events:
        lines.append("")
        lines.append("  Decisions:")
        for ev in events:
            art = ev["article"]
            ana = ev["analysis"]
            lines.append(
                f"    [{ana.get('decision', '?'):4s}] "
                f"{ana.get('amount_cbwd', 0):>10,} CBWD | "
                f"score={ana.get('final_score', 0):+.2f} | "
                f"conf={ana.get('confidence', '?')}/10 | "
                f"{art.get('title', '')[:55]}"
            )

    lines.append("=" * 60)
    summary = "\n".join(lines)

    # Log each line
    for line in lines:
        if line.strip():
            logger.info(line)

    return summary
