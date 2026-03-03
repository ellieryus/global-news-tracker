"""
Structured logging configuration.
Call setup_logging() once at application startup.
"""
from __future__ import annotations

import logging
import logging.config
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: str = "logs/pipeline.log") -> None:
    """
    Configure structured logging with both file and console handlers.

    Args:
        level: Logging level string (DEBUG, INFO, WARNING, ERROR).
        log_file: Path to the rotating log file.
    """
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structured": {
                "format": "%(asctime)s %(levelname)-8s %(name)-35s %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%SZ",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "structured",
                "level": level,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "structured",
                "filename": log_file,
                "maxBytes": 5_242_880,  # 5 MB
                "backupCount": 3,
                "level": level,
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": level,
        },
    }
    logging.config.dictConfig(config)
