"""arXiv raw download placeholder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArxivConfig:
    """Runtime settings for one arXiv download task."""

    data_root: Path = Path("data/papers/arxiv")
    request_timeout: float = 30.0


def download_one(*args: Any, **kwargs: Any) -> Any:
    """Download and persist one arXiv record exactly as returned upstream."""
    raise NotImplementedError("arXiv download is not implemented yet")
