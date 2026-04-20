"""Task discovery and filtering for worker mode."""

from __future__ import annotations

from typing import Any

from gigiac_bot.api.gigiac import GigiacClient
from gigiac_bot.utils.logger import logger

MAX_BUDGET = 50
MIN_BUDGET = 10


def browse_and_filter_tasks(client: GigiacClient) -> list[dict[str, Any]]:
    """Fetch tasks matched to the bot's skills, falling back to open browse."""

    # Try matched tasks first (uses bot skill profile)
    try:
        matched = client.get_matched_tasks()
        if matched:
            filtered = [t for t in matched if t.get("budget_amount", 0) <= MAX_BUDGET]
            logger.info("Matched tasks after budget filter: %d/%d", len(filtered), len(matched))
            return filtered
    except Exception as exc:
        logger.warning("Failed to fetch matched tasks, falling back to browse: %s", exc)

    # Fallback: browse all open tasks
    all_tasks = client.list_tasks(status="open", limit=20)
    filtered = [
        t for t in all_tasks
        if MIN_BUDGET <= t.get("budget_amount", 0) <= MAX_BUDGET
    ]
    logger.info("Open tasks after budget filter: %d/%d", len(filtered), len(all_tasks))
    return filtered
