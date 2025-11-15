from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from typing import Optional

try:  # Optional dependency for colored output
    from colorama import Fore, Style  # pylint: disable=import-error
    from colorama import init as colorama_init  # pylint: disable=import-error

    colorama_init(autoreset=True)
except Exception:  # pragma: no cover - graceful degradation

    class _Dummy:
        RESET_ALL = ""

    class _DummyFore(_Dummy):
        BLACK = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = ""

    class _DummyStyle(_Dummy):
        BRIGHT = DIM = NORMAL = ""

    Fore = _DummyFore()
    Style = _DummyStyle()


class ColorFormatter(logging.Formatter):
    """Colorize log records based on level using colorama when available."""

    LOG_COLORS: dict[int, str] = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA + Style.BRIGHT,
    }

    def format(self, record: logging.LogRecord) -> str:  # pragma: no cover - formatting logic
        """Format a record with color.

        Args:
            record (logging.LogRecord): Log record.

        Returns:
            str: Formatted message string.
        """
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
        result: int = getattr(logging, str(level).upper())
        return result
    except Exception:
        return logging.INFO


def __logger_setup(  # noqa: D401 - simple setup function
    *,
    level: Optional[str | int] = None,
    include: Optional[Iterable[str]] = None,
    fmt: str = "%(asctime)s - %(levelname)s - %(name)s - %(filename)s:%(lineno)d - %(message)s",
) -> None:
    """Configure root and third-party loggers with a colored formatter.

    Args:
        level (str | int | None): Root log level or name; defaults to ``LOG_LEVEL`` env var or INFO.
        include (Iterable[str] | None): Additional logger names to configure.
        fmt (str): Log format string for the ColorFormatter.
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


def logger_setup(**kwargs: Optional[str | int | Iterable[str]]) -> None:
    """Public alias for ``__logger_setup``.

    Args:
        **kwargs: Forwarded keyword arguments; see ``__logger_setup``.
    """
    __logger_setup(**kwargs)  # type: ignore[arg-type]


__all__ = ["ColorFormatter", "__logger_setup", "logger_setup"]
