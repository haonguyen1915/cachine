from __future__ import annotations

import logging
import os
from typing import Dict, Iterable, Literal, Optional

from colorama import Fore, Style


class ColorFormatter(logging.Formatter):
    """Colorize log records based on level using colorama when available."""

    LOG_COLORS: Dict[int, str] = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT,
    }

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting logic
        log_color = self.LOG_COLORS.get(record.levelno, Fore.WHITE)
        if self.usesTime():
            record.asctime = self.formatTime(record, self.datefmt)

        # Mutate fields to include color
        record.msg = f"{log_color}{record.msg}{Style.RESET_ALL}"
        record.levelname = f"{log_color}{record.levelname}{Style.RESET_ALL}"
        record.filename = f"{log_color}{record.filename}{Style.RESET_ALL}"
        record.name = f"{log_color}{record.name}{Style.RESET_ALL}"

        return super().format(record)


def _parse_level(level: Optional[str | int]) -> int:
    if level is None:
        return logging.INFO
    if isinstance(level, int):
        return level
    try:
        return getattr(logging, str(level).upper())
    except Exception:
        return logging.INFO


def logger_setup(  # noqa: D401 - simple setup function
    *,
    level: Literal["INFO", "DEBUG", "WARNING", "ERROR", "CRITICAL", "NOTSET"] | int | None = None,
    include: Optional[Iterable[str]] = None,
    fmt: str = "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s",
) -> None:
    """Configure root and common third-party loggers with a colored formatter.

    - level: overrides root log level; defaults to LOG_LEVEL env var or INFO.
    - include: extra logger names to configure; a sensible default set is applied.
    - fmt: log format string for the ColorFormatter.
    """

    resolved_level = _parse_level(level or os.getenv("LOG_LEVEL"))

    handler = logging.StreamHandler()
    handler.setFormatter(ColorFormatter(fmt))

    default_loggers = [
        "root",
        "urllib3",
        "httpcore",
        "aiokafka",
        "pymongo",
        "tzlocal",
        "apscheduler",
        "googleapiclient",
        "LiteLLM",
        "instructor",
    ]
    if include:
        default_loggers.extend(list(include))

    for name in default_loggers:
        logger = logging.getLogger(name if name != "root" else "")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(resolved_level if name == "root" else logging.WARNING)
