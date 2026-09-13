"""OpenAlex raw download placeholder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OpenalexConfig:
    """Runtime settings for one OpenAlex download task."""

    data_root: Path = Path("data/papers/openalex")
    request_timeout: float = 30.0


def download_one(*args: Any, **kwargs: Any) -> Any:
    """Download and persist one OpenAlex record exactly as returned upstream."""
    raise NotImplementedError("OpenAlex download is not implemented yet")
