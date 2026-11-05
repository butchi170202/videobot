"""Logging configuration with automatic secret masking for API keys and Bot tokens."""

import logging
import re
import sys
from app.core.config import settings


class SecretMaskingFilter(logging.Filter):
    """Filter that masks sensitive API keys and Telegram tokens in log records."""

    # Patterns for Google API Keys (AIza...) and Telegram Bot Tokens (digits:alphanumeric)
    PATTERNS = [
        re.compile(r"AIza[0-9A-Za-z\-_]{30,}"),
        re.compile(r"\b\d{8,11}:[A-Za-z0-9_-]{30,}\b"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        masked = msg
        if settings.GEMINI_API_KEY and len(settings.GEMINI_API_KEY) > 8:
            masked = masked.replace(settings.GEMINI_API_KEY, "***GEMINI_API_KEY***")
        if settings.TELEGRAM_BOT_TOKEN and len(settings.TELEGRAM_BOT_TOKEN) > 8:
            masked = masked.replace(settings.TELEGRAM_BOT_TOKEN, "***BOT_TOKEN***")

        for pattern in self.PATTERNS:
            masked = pattern.sub("***REDACTED_SECRET***", masked)

        if masked != msg:
            record.msg = masked
            record.args = ()
        return True


def setup_logging() -> None:
    """Configure root logger with secret masking filter."""
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(SecretMaskingFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiogram.event").setLevel(logging.INFO)

