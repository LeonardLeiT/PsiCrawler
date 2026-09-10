"""Configuration for the AFLOW source adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AflowConfig:
    """Runtime paths and HTTP settings for one AFLOW extraction task."""

    data_root: Path = Path("data/dft/aflow")
    request_timeout: int = 60
    sleep_seconds: float = 1.0
    user_agent: str = "aflow-python-extractor/0.2 (academic non-commercial use)"

    @property
    def raw_dir(self) -> Path:
        """Return the directory for source AFLOW files."""
        return self.data_root / "raw"

    @property
    def normalized_dir(self) -> Path:
        """Return the directory for unified AFLOW records."""
        return self.data_root / "normalized"

    @property
    def database_path(self) -> Path:
        """Return the SQLite search index path."""
        return self.data_root / "database" / "aflow.sqlite"

    @property
    def logs_dir(self) -> Path:
        """Return the directory for crawler logs."""
        return self.data_root / "logs"

    @property
    def manifest_dir(self) -> Path:
        """Return the directory for crawl manifests."""
        return self.data_root / "manifests"

    @property
    def status_path(self) -> Path:
        """Return the structured status file path."""
        return self.manifest_dir / "status.json"
