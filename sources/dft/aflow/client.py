"""AFLOWLIB and AFLUX HTTP client."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from .config import AflowConfig

AFLUX_BASE_URL = "https://aflow.org/API/aflux/"
AFLOWLIB_HTTP_BASE = "http://aflowlib.duke.edu"


class AflowClient:
    """Access AFLOWLIB metadata and AFLUX search endpoints."""

    def __init__(self, config: AflowConfig | None = None):
        """Create an AFLOW HTTP client.

        Args:
            config (AflowConfig | None): HTTP and storage configuration.
        """
        self.config = config or AflowConfig()

    def get_bytes(self, url: str, timeout: int | None = None) -> bytes:
        """Fetch raw bytes from an AFLOW URL.

        Args:
            url (str): HTTP URL.
            timeout (int | None): Request timeout in seconds.

        Returns:
            bytes: Response body.
        """
        request = urllib.request.Request(url, headers={"User-Agent": self.config.user_agent})
        with urllib.request.urlopen(request, timeout=timeout or self.config.request_timeout) as response:
            return response.read()

    def get_json(self, url: str, timeout: int | None = None) -> Any:
        """Fetch and decode a JSON AFLOW response.

        Args:
            url (str): HTTP URL.
            timeout (int | None): Request timeout in seconds.

        Returns:
            Any: Decoded JSON response.
        """
        return json.loads(self.get_bytes(url, timeout=timeout).decode("utf-8"))

    def fetch_metadata(self, identifier: str, timeout: int | None = None) -> dict[str, Any]:
        """Fetch one AFLOWLIB metadata document.

        Args:
            identifier (str): AFLOW AURL, path, or material directory URL.
            timeout (int | None): Request timeout in seconds.

        Returns:
            dict[str, Any]: Raw AFLOWLIB metadata.
        """
        return self.get_json(self.metadata_url(identifier), timeout=timeout)

    def metadata_url(self, identifier: str) -> str:
        """Build the AFLOWLIB metadata URL for an identifier.

        Args:
            identifier (str): AFLOW AURL, path, or material directory URL.

        Returns:
            str: URL ending in ``aflowlib.json``.
        """
        return f"{self.directory_url(identifier).rstrip('/')}/aflowlib.json"

    @staticmethod
    def directory_url(identifier: str) -> str:
        """Normalize an AFLOW identifier to its material directory URL.

        Args:
            identifier (str): AFLOW AURL, path, or material directory URL.

        Returns:
            str: Normalized AFLOWLIB directory URL.
        """
        value = identifier.strip().strip('"').strip("'")
        if value.endswith("/aflowlib.json"):
            value = value[: -len("/aflowlib.json")]
        if value.startswith(("http://", "https://")):
            return value.rstrip("/")
        if value.startswith("aflowlib.duke.edu:"):
            return f"{AFLOWLIB_HTTP_BASE}/{value.split(':', 1)[1].strip('/')}"
        if value.startswith("AFLOWDATA/"):
            return f"{AFLOWLIB_HTTP_BASE}/{value.strip('/')}"
        raise ValueError("Identifier must be an AFLOW aurl/path or material directory URL")

    @staticmethod
    def aflux_url(query: str) -> str:
        """Build an AFLUX query URL.

        Args:
            query (str): AFLUX filter, fields, and paging expression.

        Returns:
            str: Encoded AFLUX URL.
        """
        return AFLUX_BASE_URL + "?" + urllib.parse.quote(query, safe="(),*$':!._-")
