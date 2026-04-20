"""AI-powered proposal generation for worker mode."""

from __future__ import annotations

from typing import Any

import anthropic

from gigiac_bot.api.gigiac import GigiacClient
from gigiac_bot.config import Config
from gigiac_bot.utils.logger import logger


def generate_and_submit_proposal(
    client: GigiacClient,
    task: dict[str, Any],
    config: Config,
) -> dict[str, Any] | None:
    """Use Claude to write a cover letter, then submit a proposal."""

    task_id = task["id"]
    title = task.get("title", "Untitled")
    logger.info("Generating proposal for task: %s (id=%s)", title, task_id)

    try:
        ai = anthropic.Anthropic(api_key=config.anthropic_api_key)

        msg = ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            system=(
                "You are a bot worker on Gigiac. Write a brief, professional "
                "proposal for this task. Be specific about your approach. "
                "2-3 sentences max."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Task: {title}\n\n"
                        f"Description: {task.get('description', '')}\n\n"
                        f"Budget: ${task.get('budget_amount', 0)} ({task.get('budget_type', 'fixed')})"
                    ),
                }
            ],
        )

        cover_letter = msg.content[0].text if msg.content and msg.content[0].type == "text" else ""

        if not cover_letter:
            logger.warning("Claude returned empty cover letter, skipping proposal")
            return None

        logger.debug("Generated cover letter: %s", cover_letter)

        proposal = client.submit_proposal(
            task_id=task_id,
            proposed_amount=task.get("budget_amount", 0),
            cover_letter=cover_letter,
        )

        logger.info("Proposal submitted successfully (task=%s, proposal=%s)", task_id, proposal["id"])
        return proposal

    except Exception as exc:
        logger.error("Failed to submit proposal for task %s: %s", task_id, exc)
        return None
