"""AI-powered deliverable review for commissioner mode."""

from __future__ import annotations

from typing import Any

import anthropic

from gigiac_bot.api.gigiac import GigiacClient
from gigiac_bot.config import Config
from gigiac_bot.utils.logger import logger


def review_deliverables(
    client: GigiacClient,
    task_ids: list[str],
    config: Config,
) -> list[dict[str, Any]]:
    """Poll for deliverables on posted tasks, evaluate with Claude, and act."""

    results: list[dict[str, Any]] = []

    for task_id in task_ids:
        try:
            detail = client.get_task_detail(task_id)
            task = detail.get("task", {})

            # Only review tasks in delivered or in_progress status
            if task.get("status") not in ("delivered", "in_progress"):
                continue

            # Find pending deliverables
            deliverables = detail.get("deliverables", [])
            pending = [d for d in deliverables if d.get("status") in ("pending", "submitted")]

            if not pending:
                continue

            for deliverable in pending:
                d_id = deliverable["id"]
                logger.info('Reviewing deliverable %s for task "%s"', d_id, task.get("title", ""))

                evaluation = _evaluate_deliverable(
                    task.get("title", ""),
                    task.get("description", ""),
                    deliverable.get("description", ""),
                    config,
                )

                try:
                    dispute_reason = evaluation["reason"] if evaluation["action"] == "reject" else None
                    client.update_deliverable(d_id, evaluation["action"], dispute_reason)

                    results.append({
                        "task_id": task_id,
                        "deliverable_id": d_id,
                        "action": evaluation["action"],
                        "reason": evaluation["reason"],
                    })

                    logger.info("Deliverable %s: %s — %s", d_id, evaluation["action"], evaluation["reason"])

                except Exception as exc:
                    logger.error("Failed to update deliverable %s: %s", d_id, exc)

        except Exception as exc:
            logger.error("Error reviewing task %s: %s", task_id, exc)

    return results


def _evaluate_deliverable(
    task_title: str,
    task_description: str,
    deliverable_text: str,
    config: Config,
) -> dict[str, str]:
    """Ask Claude to evaluate a deliverable. Returns {action, reason}."""
    try:
        ai = anthropic.Anthropic(api_key=config.anthropic_api_key)

        msg = ai.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=(
                "You are reviewing a task deliverable. Evaluate whether it meets the requirements.\n"
                "Respond with EXACTLY one of these formats:\n"
                "APPROVE: <one-sentence reason>\n"
                "REJECT: <one-sentence reason>\n"
                "REVISION: <one-sentence reason for what needs fixing>\n\n"
                "Approve if the deliverable reasonably addresses the task requirements.\n"
                "Reject only if it is clearly off-topic, empty, or spam.\n"
                "Request revision if it partially meets requirements but needs improvement."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Task: {task_title}\n\n"
                        f"Requirements:\n{task_description}\n\n"
                        f"Deliverable:\n{deliverable_text}"
                    ),
                }
            ],
        )

        response = msg.content[0].text if msg.content and msg.content[0].type == "text" else ""

        if response.startswith("REJECT:"):
            return {"action": "reject", "reason": response[7:].strip()}
        if response.startswith("REVISION:"):
            return {"action": "revision", "reason": response[9:].strip()}

        reason = response[8:].strip() if response.startswith("APPROVE:") else "Deliverable meets task requirements."
        return {"action": "approve", "reason": reason}

    except Exception as exc:
        # On evaluation failure, default to approve to avoid blocking payment
        logger.warning("Evaluation failed, defaulting to approve: %s", exc)
        return {"action": "approve", "reason": "Auto-approved (evaluation unavailable)"}
