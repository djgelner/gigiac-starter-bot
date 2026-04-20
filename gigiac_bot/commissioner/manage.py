"""Credit balance monitoring for commissioner mode."""

from __future__ import annotations

from typing import Any

from gigiac_bot.api.gigiac import GigiacClient
from gigiac_bot.utils.logger import logger

LOW_BALANCE_CENTS = 2000   # $20 warning threshold
EMPTY_BALANCE_CENTS = 500  # $5 critical threshold


def check_balance_status(client: GigiacClient) -> dict[str, Any] | None:
    """Check credit balance and log warnings. Returns status dict or None on error."""
    try:
        balance = client.get_credit_balance()
        cents = balance.get("balance_cents", 0)
        dollars = f"{cents / 100:.2f}"
        auto_refill = balance.get("auto_refill_enabled", False)

        is_low = cents < LOW_BALANCE_CENTS
        is_critical = cents < EMPTY_BALANCE_CENTS

        if is_critical:
            logger.error("CRITICAL: Credit balance is $%s. Bot cannot post new tasks.", dollars)
        elif is_low:
            logger.warning("Low credit balance: $%s. Consider adding credits.", dollars)
        else:
            logger.info("Credit balance: $%s", dollars)

        if not auto_refill and is_low:
            logger.warning("Auto-refill is disabled. Enable it to avoid running out of credits.")

        return {
            "balance_cents": cents,
            "balance_dollars": dollars,
            "is_low": is_low,
            "is_critical": is_critical,
            "auto_refill_enabled": auto_refill,
        }

    except Exception as exc:
        logger.error("Failed to check credit balance: %s", exc)
        return None
