"""AFLOW filesystem and SQLite storage facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import extractor as legacy
from .config import AflowConfig


class AflowStorage:
    """Coordinate AFLOW directories, files, and SQLite storage."""

    def __init__(self, config: AflowConfig | None = None):
        """Create AFLOW storage using the configured data root.

        Args:
            config (AflowConfig | None): AFLOW storage configuration.
        """
        self.config = config or AflowConfig()
        self.dirs = legacy.ensure_data_dirs(str(self.config.data_root))

    def ensure(self) -> None:
        """Create directories and initialize the AFLOW SQLite index."""
        self.config.data_root.mkdir(parents=True, exist_ok=True)
        legacy.init_database(str(self.config.database_path))

    def material_dir(self, category: str, item: dict[str, Any]) -> Path:
        """Return one material category directory.

        Args:
            category (str): Category such as ``metadata`` or ``normalized``.
            item (dict[str, Any]): Raw AFLOW metadata document.

        Returns:
            Path: Material-local storage directory.
        """
        return legacy.material_category_dir(self.dirs, category, item)

    def save_metadata(self, item: dict[str, Any], query_hit: dict[str, Any] | None = None) -> list[Path]:
        """Save AFLOWLIB metadata and the source file manifest.

        Args:
            item (dict[str, Any]): Raw AFLOWLIB metadata.
            query_hit (dict[str, Any] | None): Optional AFLUX result.

        Returns:
            list[Path]: Written metadata paths.
        """
        return legacy.save_metadata_files(item, self.dirs, query_hit=query_hit)

    def download_files(
        self,
        item: dict[str, Any],
        profile: str,
        timeout: int,
        extra_patterns: list[str] | None = None,
        errors: list[str] | None = None,
    ) -> list[Path]:
        """Download the files allowed by an AFLOW profile.

        Args:
            item (dict[str, Any]): Raw AFLOWLIB metadata.
            profile (str): AFLOW download profile.
            timeout (int): HTTP request timeout in seconds.
            extra_patterns (list[str] | None): Additional filename patterns.
            errors (list[str] | None): Mutable list receiving failures.

        Returns:
            list[Path]: Successfully downloaded paths.
        """
        return legacy.download_profile_files(item, self.dirs, profile, timeout, extra_patterns, errors)
