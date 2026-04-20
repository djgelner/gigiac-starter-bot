"""Colored console logger matching the TypeScript version's output format."""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone


class _ColorFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[90m",    # gray
        "INFO": "\033[36m",     # cyan
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        tag = record.levelname.ljust(5)
        msg = record.getMessage()
        return f"{color}[{ts}] {tag}{self.RESET} {msg}"


def _setup_logger() -> logging.Logger:
    log = logging.getLogger("gigiac_bot")
    log.setLevel(getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO))

    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_ColorFormatter())
        log.addHandler(handler)

    return log


logger = _setup_logger()
