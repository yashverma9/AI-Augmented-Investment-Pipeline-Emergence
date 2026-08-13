from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

LOGS_DIR = Path(__file__).with_name("logs")


def configure_logging(stage: str) -> Path:
    """Set up root logger with both a per-run log file and console output. Returns the log file path."""
    LOGS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    log_path = LOGS_DIR / f"{stage}_{timestamp}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    return log_path
