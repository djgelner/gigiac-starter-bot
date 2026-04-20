"""AI-powered deliverable generation for worker mode."""

from __future__ import annotations

from typing import Any

import anthropic

from gigiac_bot.api.gigiac import GigiacClient
from gigiac_bot.config import Config
from gigiac_bot.utils.logger import logger


def check_and_deliver(
    client: GigiacClient,
    task_ids: list[str],
    config: Config,
) -> list[str]:
    """Check tasks for accepted proposals and generate/submit deliverables.

    Returns the IDs of tasks where delivery was submitted successfully.
    """
    delivered: list[str] = []

    for task_id in task_ids:
        try:
            detail = client.get_task_detail(task_id)
            task = detail.get("task", {})

            # Only deliver if task is in_progress and we have an accepted proposal
            if task.get("status") != "in_progress":
                continue

            proposals = detail.get("proposals", [])
            accepted = [p for p in proposals if p.get("status") == "accepted"]
            if not accepted:
                continue

            # Skip if we already have a deliverable
            if detail.get("deliverables"):
                logger.debug("Task %s already has a deliverable, skipping", task_id)
                continue

            logger.info("Task %s accepted — generating deliverable", task_id)

            deliverable = _generate_deliverable(
                client,
                task_id,
                task.get("title", ""),
                task.get("description", ""),
                config,
            )
            if deliverable:
                delivered.append(task_id)

        except Exception as exc:
            logger.error("Error checking task %s: %s", task_id, exc)

    return delivered


def _generate_deliverable(
    client: GigiacClient,
    task_id: str,
    title: str,
    description: str,
    config: Config,
) -> dict[str, Any] | None:
    """Use Claude to produce the deliverable, then submit it."""
    try:
        ai = anthropic.Anthropic(api_key=config.anthropic_api_key)

        msg = ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=(
                "Complete this task professionally and thoroughly. "
                "Provide a clear, well-structured deliverable."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Task: {title}\n\nRequirements:\n{description}",
                }
            ],
        )

        text = msg.content[0].text if msg.content and msg.content[0].type == "text" else ""
        if not text:
            logger.warning("Claude returned empty deliverable")
            return None

        deliverable = client.submit_deliverable(task_id, text)
        logger.info("Deliverable submitted for task %s (id=%s)", task_id, deliverable["id"])
        return deliverable

    except Exception as exc:
        logger.error("Failed to generate/submit deliverable for task %s: %s", task_id, exc)
        return None
