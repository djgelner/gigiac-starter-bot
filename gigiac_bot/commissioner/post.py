"""Task posting for commissioner mode."""

from __future__ import annotations

from typing import Any

from gigiac_bot.api.gigiac import GigiacClient
from gigiac_bot.utils.logger import logger

MIN_BALANCE_CENTS = 1500  # Need at least $15 (task + platform fee)

DEFAULT_TASK = {
    "title": "Summarize this article in 3 bullet points",
    "description": (
        "Read the following article and provide a concise 3-bullet summary "
        "capturing the key points, main argument, and any actionable takeaways. "
        "Each bullet should be 1-2 sentences.\n\n"
        "Article: [Paste article text here or provide URL]"
    ),
    "category": "Content & Copy",
    "budget_type": "fixed",
    "budget_amount": 10,
}


def post_task(
    client: GigiacClient,
    template: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Check balance, then post a task from a template."""

    # Check credit balance first
    try:
        balance = client.get_credit_balance()
        cents = balance.get("balance_cents", 0)
        logger.info("Credit balance: $%.2f", cents / 100)

        if cents < MIN_BALANCE_CENTS:
            logger.warning(
                "Insufficient credits ($%.2f). Need at least $%.2f to post a task.",
                cents / 100,
                MIN_BALANCE_CENTS / 100,
            )
            return None
    except Exception as exc:
        logger.error("Failed to check credit balance: %s", exc)
        return None

    task = template or DEFAULT_TASK

    try:
        result = client.post_task(
            title=task["title"],
            description=task["description"],
            category=task["category"],
            budget_type=task.get("budget_type", "fixed"),
            budget_amount=task.get("budget_amount", 10),
        )

        if result.get("data"):
            logger.info('Task posted successfully: "%s" (id=%s)', task["title"], result["data"]["id"])
        elif result.get("status") == "pending_approval":
            logger.info("Task posted but pending approval (approval_id=%s)", result.get("approval_id"))

        return result

    except Exception as exc:
        logger.error('Failed to post task: "%s": %s', task["title"], exc)
        return None
