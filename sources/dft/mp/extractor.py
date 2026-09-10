"""Single-record extraction orchestration for Materials Project."""

from __future__ import annotations

from typing import Any

from .client import MPClient, PROPERTY_ENDPOINTS, normalize_mp_id
from .config import MPConfig
from .normalize import normalize_summary
from .storage import ensure_storage, save_property, save_record


def extract_one(
    client: MPClient,
    mp_id: int | str,
    config: MPConfig,
    include_properties: bool = True,
) -> dict[str, Any]:
    """Download and store one MP material.

    Args:
        client (MPClient): Configured Materials Project API client.
        mp_id (int | str): Material identifier.
        config (MPConfig): MP storage configuration.
        include_properties (bool): Whether to fetch additional property endpoints.

    Returns:
        dict[str, Any]: Extraction result with IDs, paths, and property status.
    """
    ensure_storage(config)
    material_id = normalize_mp_id(mp_id)
    summary = client.fetch_summary(material_id)
    if summary is None:
        raise LookupError(f"Materials Project record not found: {material_id}")

    mapping_document = dict(summary)
    mapping_document["_requested_id"] = material_id
    normalized = normalize_summary(mapping_document)
    properties: dict[str, int] = {}
    property_paths: dict[str, str] = {}
    source_properties: dict[str, list[dict[str, Any]]] = {}
    property_errors: dict[str, str] = {}
    if include_properties:
        for route in PROPERTY_ENDPOINTS:
            endpoint = route["name"]
            try:
                documents = client.fetch_property(route, material_id, summary)
                property_path = save_property(config, material_id, endpoint, documents)
                properties[endpoint] = len(documents)
                source_properties[endpoint] = documents
                if property_path:
                    property_paths[endpoint] = str(property_path)
            except Exception as error:
                properties[endpoint] = 0
                property_errors[endpoint] = str(error)

    normalized["property_paths"] = property_paths
    normalized["source_documents"] = {"properties": property_paths}
    normalized["source_properties"] = source_properties
    normalized["source_property_paths"] = property_paths
    normalized["property_errors"] = property_errors
    normalized["download_status"] = "partial" if property_errors else "success"
    normalized["properties_requested"] = include_properties
    normalized["has_structure"] = normalized.get("structure") is not None
    normalized["has_elasticity"] = properties.get("elasticity", 0) > 0
    normalized["has_dielectric"] = properties.get("dielectric", 0) > 0
    normalized["has_piezoelectric"] = properties.get("piezoelectric", 0) > 0
    normalized["has_magnetism"] = properties.get("magnetism", 0) > 0
    normalized["has_xas"] = properties.get("xas", 0) > 0
    normalized_path = save_record(config, summary, normalized)
    return {
        "requested_id": material_id,
        "source_id": normalized["source_id"],
        "normalized_path": str(normalized_path),
        "properties": properties,
        "property_errors": property_errors,
    }










