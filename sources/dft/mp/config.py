"""Configuration for the Materials Project source."""

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class MPConfig:
    """Runtime paths and API settings for one MP extraction task."""

    api_key: str
    data_root: Path = Path("data/dft/mp")
    request_timeout: float = 30.0
    retry_count: int = 3
    retry_delay: float = 10.0

    @classmethod
    def from_environment(cls, data_root: str | Path = "data/dft/mp") -> "MPConfig":
        """Build configuration from environment variables or a local .env file.

        Args:
            data_root (str | Path): Default root directory for MP output files.

        Returns:
            MPConfig: Configured MP runtime settings.

        Raises:
            RuntimeError: If ``MP_API_KEY`` is not available.
        """
        load_dotenv()
        api_key = os.getenv("MP_API_KEY")
        if not api_key or api_key.startswith("replace_with_"):
            raise RuntimeError(
                "MP_API_KEY is required; copy .env.example to .env and set your API key."
            )
        configured_root = os.getenv("MP_DATA_ROOT", str(data_root))
        return cls(api_key=api_key, data_root=Path(configured_root))

    @property
    def raw_dir(self) -> Path:
        """Return the directory for untouched API responses."""
        return self.data_root / "raw"

    @property
    def normalized_dir(self) -> Path:
        """Return the directory for unified MP records."""
        return self.data_root / "normalized"

    @property
    def database_path(self) -> Path:
        """Return the SQLite index path."""
        return self.data_root / "database" / "mp.sqlite"

    @property
    def logs_dir(self) -> Path:
        """Return the directory for MP crawler logs."""
        return self.data_root / "logs"

    @property
    def manifest_dir(self) -> Path:
        """Return the directory for crawl manifests."""
        return self.data_root / "manifests"
