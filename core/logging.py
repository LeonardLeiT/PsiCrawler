"""Shared logging helpers for source crawlers."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path


def new_run_id(prefix: str = "run") -> str:
    """Create a sortable identifier for one crawler run.

    Args:
        prefix (str): Short name placed before the timestamp.

    Returns:
        str: Run identifier such as ``mp_20260909_223000``.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}"


def create_logger(
    name: str,
    log_dir: str | Path,
    *,
    run_id: str | None = None,
    level: int = logging.INFO,
) -> logging.Logger:
    """Create a console and file logger for a crawler run.

    Args:
        name (str): Logger name, normally the source and task name.
        log_dir (str | Path): Directory for crawler log files.
        run_id (str | None): Optional run identifier for the log filename.
        level (int): Logging level for the console and file handlers.

    Returns:
        logging.Logger: Configured logger with reusable handlers.
    """
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    if logger.handlers:
        return logger

    file_id = run_id or new_run_id(name.replace(".", "_"))
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler = logging.FileHandler(directory / f"{file_id}.log", encoding="utf-8")
    console_handler = logging.StreamHandler(sys.stdout)
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    file_handler.setLevel(level)
    console_handler.setLevel(level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger
