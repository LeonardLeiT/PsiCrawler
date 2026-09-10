"""Small Materials Project API adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import requests

from core.schema import load_yaml
from .config import MPConfig


MAPPING_PATH = Path(__file__).resolve().parents[3] / "schemas" / "dft" / "mp.yaml"
MP_MAPPING = load_yaml(MAPPING_PATH)
SUMMARY_FIELDS = MP_MAPPING["summary_fields"]
PROPERTY_ENDPOINTS = tuple(MP_MAPPING["property_endpoints"])


def normalize_mp_id(mp_id: int | str) -> str:
    """Normalize an integer or string to the ``mp-XXXXX`` format.

    Args:
        mp_id (int | str): Materials Project identifier.

    Returns:
        str: Normalized material identifier.
    """
    value = str(mp_id).strip()
    if value.lower().startswith("mp-"):
        return f"mp-{value[3:]}"
    if value.isdigit():
        return f"mp-{value}"
    return value


class MPClient:
    """Access Materials Project summary and detail endpoints."""

    def __init__(self, config: MPConfig):
        """Create an API client.

        Args:
            config (MPConfig): MP API and storage configuration.
        """
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({"X-API-KEY": config.api_key})
        self.base_url = "https://api.materialsproject.org"

    def fetch_ids(self, *, chemsys: str | None = None, elements: list[str] | None = None,
                  is_stable: bool | None = None, max_materials: int | None = None,
                  page_size: int = 1000) -> list[str]:
        """Fetch material IDs with optional filters.

        Args:
            chemsys (str | None): Chemical system filter.
            elements (list[str] | None): Required element symbols.
            is_stable (bool | None): Stability filter.
            max_materials (int | None): Maximum number of IDs to return.
            page_size (int): Number of IDs requested per page.

        Returns:
            list[str]: Normalized MP material IDs.
        """
        params: dict[str, Any] = {"_fields": "material_id", "_limit": page_size, "_skip": 0}
        if chemsys:
            params["chemsys"] = chemsys
        if elements:
            params["elements"] = ",".join(elements)
        if is_stable is not None:
            params["is_stable"] = str(is_stable).lower()
        material_ids: list[str] = []
        while max_materials is None or len(material_ids) < max_materials:
            response = self.session.get(f"{self.base_url}/materials/summary/", params=params,
                                        timeout=self.config.request_timeout)
            response.raise_for_status()
            docs = response.json().get("data", [])
            if not docs:
                break
            material_ids.extend(normalize_mp_id(doc["material_id"]) for doc in docs if doc.get("material_id"))
            if len(docs) < page_size:
                break
            params["_skip"] += page_size
        return material_ids[:max_materials] if max_materials else material_ids

    def fetch_summary(self, mp_id: int | str) -> dict[str, Any] | None:
        """Fetch one material summary from the MP REST API.

        Args:
            mp_id (int | str): Material identifier.

        Returns:
            dict[str, Any] | None: Raw summary document, or ``None`` if absent.
        """
        response = self.session.get(f"{self.base_url}/materials/summary/",
                                    params={"material_ids": normalize_mp_id(mp_id),
                                            "_all_fields": "true"},
                                    timeout=self.config.request_timeout)
        response.raise_for_status()
        docs = response.json().get("data", [])
        return docs[0] if docs else None

    def fetch_property(self, route: dict[str, str], mp_id: int | str, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch one source-specific property endpoint.

        Args:
            route (dict[str, str]): Route name and API path from the MP mapping.
            mp_id (int | str): Material identifier.

        Returns:
            list[dict[str, Any]]: Raw property documents.
        """
        if route.get("strategy") == "summary_field":
            value = (context or {}).get(route.get("summary_field", ""))
            return [value] if value else []
        query_field = route.get("query_field", "material_ids")
        query_value: Any = normalize_mp_id(mp_id)
        if route.get("context_field"):
            query_value = (context or {}).get(route["context_field"])
        if query_field == "task_ids":
            query_value = (context or {}).get("task_ids", [])
        if query_field == "identifiers":
            phonon_ids = (context or {}).get("phonon_IDs") or {}
            query_value = [identifier for values in phonon_ids.values() for identifier in (values or [])]
        params: dict[str, Any] = {query_field: query_value}
        response = self.session.get(
            f"{self.base_url}/materials/{route['path']}/",
            params=params,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        return response.json().get("data", [])











