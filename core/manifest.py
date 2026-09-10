"""Run manifest helpers shared by source crawlers."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from .logging import new_run_id


_WRITE_LOCK = threading.Lock()


def start_manifest(
    manifest_dir: str | Path,
    source: str,
    parameters: dict[str, Any],
    requested_ids: list[str],
) -> dict[str, Any]:
    """Create a batch manifest and its append-only item file.

    Args:
        manifest_dir (str | Path): Directory for manifest files.
        source (str): Source crawler name.
        parameters (dict[str, Any]): Immutable query and runtime settings.
        requested_ids (list[str]): IDs selected for this run.

    Returns:
        dict[str, Any]: Manifest paths and run identifier.
    """
    directory = Path(manifest_dir)
    directory.mkdir(parents=True, exist_ok=True)
    run_id = new_run_id(source) + "_" + datetime.now().strftime("%f")
    manifest_path = directory / f"{run_id}.json"
    requested_path = directory / f"{run_id}.requested.jsonl"
    items_path = directory / f"{run_id}.items.jsonl"
    summary_path = directory / f"{run_id}.summary.json"
    payload = {
        "run_id": run_id,
        "source": source,
        "status": "running",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "requested_count": len(requested_ids),
        "parameters": parameters,
        "requested_path": str(requested_path),
        "items_path": str(items_path),
        "summary_path": str(summary_path),
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    requested_path.write_text("".join(json.dumps({"source_id": item}, ensure_ascii=False) + "\\n" for item in requested_ids), encoding="utf-8")
    items_path.write_text("", encoding="utf-8")
    return {"run_id": run_id, "manifest_path": manifest_path, "items_path": items_path, "summary_path": summary_path}


def append_manifest_item(manifest: dict[str, Any], item: dict[str, Any]) -> None:
    """Append one material result to a run manifest.

    Args:
        manifest (dict[str, Any]): Return value from start_manifest.
        item (dict[str, Any]): Material status record.
    """
    path = Path(manifest["items_path"])
    with _WRITE_LOCK:
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")


def finish_manifest(manifest: dict[str, Any], summary: dict[str, Any]) -> None:
    """Write the final run summary and mark the manifest complete.

    Args:
        manifest (dict[str, Any]): Return value from start_manifest.
        summary (dict[str, Any]): Final counts and timing information.
    """
    summary_payload = {
        "run_id": manifest["run_id"],
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        **summary,
    }
    Path(manifest["summary_path"]).write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    path = Path(manifest["manifest_path"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update({"status": "completed", "finished_at": summary_payload["finished_at"], "summary_path": str(manifest["summary_path"])})
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

