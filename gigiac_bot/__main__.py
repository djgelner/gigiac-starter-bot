"""Main entry point — run with `python -m gigiac_bot`."""

from __future__ import annotations

import argparse
import signal
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from gigiac_bot.config import load_config, Config  # noqa: E402
from gigiac_bot.api.gigiac import GigiacClient  # noqa: E402
from gigiac_bot.utils.logger import logger  # noqa: E402
from gigiac_bot.worker.browse import browse_and_filter_tasks  # noqa: E402
from gigiac_bot.worker.propose import generate_and_submit_proposal  # noqa: E402
from gigiac_bot.worker.deliver import check_and_deliver  # noqa: E402
from gigiac_bot.commissioner.post import post_task  # noqa: E402
from gigiac_bot.commissioner.review import review_deliverables  # noqa: E402
from gigiac_bot.commissioner.manage import check_balance_status  # noqa: E402

running = True

# Track task IDs we've proposed on (worker) or posted (commissioner)
proposed_task_ids: set[str] = set()
posted_task_ids: set[str] = set()


def worker_loop(client: GigiacClient, config: Config) -> None:
    logger.info("=== Worker cycle starting ===")

    # 1. Browse for tasks
    tasks = browse_and_filter_tasks(client)

    if not tasks:
        logger.info("No suitable tasks found this cycle")
    else:
        # 2. Propose on new tasks (skip ones we already proposed on)
        for task in tasks:
            if task["id"] in proposed_task_ids:
                logger.debug("Already proposed on task %s, skipping", task["id"])
                continue

            proposal = generate_and_submit_proposal(client, task, config)
            if proposal:
                proposed_task_ids.add(task["id"])

            # Only propose on one task per cycle to avoid spam
            break

    # 3. Check for accepted proposals and deliver
    if proposed_task_ids:
        delivered = check_and_deliver(client, list(proposed_task_ids), config)
        if delivered:
            logger.info("Delivered work on %d task(s)", len(delivered))


def commissioner_loop(client: GigiacClient, config: Config) -> None:
    logger.info("=== Commissioner cycle starting ===")

    # 1. Check balance
    status = check_balance_status(client)
    if not status or status.get("is_critical"):
        logger.warning("Skipping commissioner cycle due to balance issues")
        return

    # 2. Post a task if we haven't posted any yet this session
    if not posted_task_ids:
        result = post_task(client)
        if result and result.get("data"):
            posted_task_ids.add(result["data"]["id"])

    # 3. Review deliverables on our posted tasks
    if posted_task_ids:
        reviews = review_deliverables(client, list(posted_task_ids), config)
        if reviews:
            logger.info("Reviewed %d deliverable(s)", len(reviews))


def main_loop(client: GigiacClient, config: Config) -> None:
    global running

    while running:
        try:
            if config.bot_mode in ("worker", "both"):
                worker_loop(client, config)

            if config.bot_mode in ("commissioner", "both"):
                commissioner_loop(client, config)
        except Exception as exc:
            logger.error("Unhandled error in main loop: %s", exc)

        if running:
            logger.info("Sleeping %ds until next cycle...", config.poll_interval_seconds)
            time.sleep(config.poll_interval_seconds)


def main() -> None:
    global running

    parser = argparse.ArgumentParser(description="Gigiac Starter Bot")
    parser.add_argument(
        "--mode",
        choices=["worker", "commissioner", "both"],
        help="Override BOT_MODE from .env",
    )
    args = parser.parse_args()

    config = load_config()

    # CLI --mode overrides .env
    if args.mode:
        config = Config(
            api_url=config.api_url,
            api_key=config.api_key,
            anthropic_api_key=config.anthropic_api_key,
            bot_mode=args.mode,
            poll_interval_seconds=config.poll_interval_seconds,
        )

    logger.info(
        "Gigiac Starter Bot — mode=%s, api=%s, poll=%ds",
        config.bot_mode,
        config.api_url,
        config.poll_interval_seconds,
    )

    client = GigiacClient(config.api_url, config.api_key)

    # Verify auth
    try:
        skills = client.get_my_skills()
        logger.info("Authenticated successfully: %s", skills)
    except Exception as exc:
        logger.error("Failed to authenticate. Check your GIGIAC_API_KEY. %s", exc)
        sys.exit(1)

    # Graceful shutdown
    def shutdown(signum: int, frame: object) -> None:
        nonlocal running  # noqa: F841 — actually modifies global
        global running
        logger.info("Shutting down gracefully...")
        running = False

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    main_loop(client, config)
    logger.info("Bot stopped.")


if __name__ == "__main__":
    main()
