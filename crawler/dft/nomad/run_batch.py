"""Pipeline entrypoint: batch download, normalize, and index NOMAD Archive.

Entries are enumerated through ``POST /entries/query`` and each processed
archive document is fetched through ``POST /entries/{id}/archive/query``. The
default scope is ``dft`` (``domain: dft``); ``--scope all`` targets every public
entry and is intended only for deliberate full-archive runs.

A bulk mode is also available: ``--mode bulk`` streams
``POST /entries/archive/download/query`` into a zip with one ``<entry-id>.json``
per entry and then normalizes each member.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.logging import create_logger
from core.manifest import append_manifest_item, finish_manifest, start_manifest
from core import storage
from normalizers.dft import field_names
from normalizers.dft.nomad.normalize import normalize_nomad_archive
from sources.dft.nomad.download import (
    MAX_PAGE_SIZE,
    CompletionIndex,
    NomadClient,
    NomadConfig,
    default_data_root,
    entry_url,
    iter_bulk_zip_documents,
    save_json_atomic,
    source_id_for,
    token_from_env,
)

SOURCE = "nomad"
INDEX_FIELDS = ("formula", "chemical_system", "band_gap", "spacegroup_number", "energy_per_atom")


def parse_page_size(value: str) -> int:
    """Parse and bound the entries-query page size."""
    try:
        number = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("page size must be an integer") from error
    if not 1 <= number <= MAX_PAGE_SIZE:
        raise argparse.ArgumentTypeError(f"page size must be between 1 and {MAX_PAGE_SIZE}")
    return number


def build_query(scope: str, query_json: str | None) -> dict:
    """Return the NOMAD search query for the requested scope."""
    if query_json:
        text = query_json
        if text.startswith("@"):
            text = Path(text[1:]).read_text(encoding="utf-8")
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("--query-json must decode to a JSON object")
        return parsed
    if scope == "dft":
        return {"domain": "dft"}
    return {}


def _normalize_and_save(config: NomadConfig, item: dict, args: argparse.Namespace,
                        logger, manifest, stats: dict, *, persist_raw: bool) -> None:
    """Normalize one archive document and insert it into the index."""
    document = item["document"]
    entry_id = item["entry_id"]
    upload_id = item.get("upload_id") or "unknown"
    raw_path = item.get("raw_path")
    if persist_raw and not raw_path:
        raw_path = str(save_json_atomic(config.raw_dir / str(upload_id) / f"{entry_id}.json", document))
    standard = normalize_nomad_archive(
        document,
        structure_root=config.data_root / "structure",
        raw_path=raw_path,
        requested_id=entry_id,
        derive_symmetry=not args.no_symmetry,
    )
    standard["raw_path"] = raw_path
    standard["source_documents"] = {
        "nomad": item.get("url") or entry_url(entry_id),
        "raw": raw_path,
        "entry_id": entry_id,
        "upload_id": upload_id,
        "mode": args.mode,
    }
    standard["download_status"] = "success"
    standard["properties_requested"] = True
    storage.save(config.database_path, standard, document, columns=field_names(), index_fields=INDEX_FIELDS)
    stats["success"] += 1
    append_manifest_item(manifest, {
        "source_id": source_id_for(entry_id), "entry_id": entry_id,
        "upload_id": upload_id, "status": "success",
    })
    if args.progress and stats["success"] % args.progress == 0:
        logger.info("[PROGRESS] success=%d failed=%d skipped=%d", stats["success"], stats["failed"], stats["skipped"])


def _run_per_entry(config: NomadConfig, args: argparse.Namespace, query: dict, logger,
                   manifest, completion_index: CompletionIndex) -> dict:
    """Enumerate entries and fetch each archive document individually."""
    client = NomadClient(config)
    stats = {"records": 0, "success": 0, "failed": 0, "skipped": 0}
    for meta in client.iter_entries(
        query, page_size=args.page_size, max_records=args.max_records, after=args.after,
    ):
        entry_id = meta.get("entry_id")
        if not entry_id:
            continue
        stats["records"] += 1
        if not args.no_resume and completion_index.is_completed(entry_id):
            stats["skipped"] += 1
            continue
        try:
            document = client.fetch_archive(entry_id)
            data = document.get("data") or {}
            item = {
                "entry_id": entry_id,
                "upload_id": data.get("upload_id") or meta.get("upload_id") or "unknown",
                "document": document,
                "url": entry_url(entry_id),
                "raw_path": None,
            }
            _normalize_and_save(config, item, args, logger, manifest, stats, persist_raw=True)
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "source_id": source_id_for(entry_id), "entry_id": entry_id,
                "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s", entry_id)
    logger.info("[BATCH] %s", stats)
    return stats


def _run_entry_id_file(config: NomadConfig, args: argparse.Namespace, logger,
                       manifest, completion_index: CompletionIndex, path: str) -> dict:
    """Fetch a fixed list of entry identifiers from a text file."""
    client = NomadClient(config)
    ids = [line.strip() for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    stats = {"records": 0, "success": 0, "failed": 0, "skipped": 0}
    for entry_id in ids:
        stats["records"] += 1
        if not args.no_resume and completion_index.is_completed(entry_id):
            stats["skipped"] += 1
            continue
        try:
            document = client.fetch_archive(entry_id)
            data = document.get("data") or {}
            item = {
                "entry_id": entry_id,
                "upload_id": data.get("upload_id") or "unknown",
                "document": document,
                "url": entry_url(entry_id),
                "raw_path": None,
            }
            _normalize_and_save(config, item, args, logger, manifest, stats, persist_raw=True)
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "source_id": source_id_for(entry_id), "entry_id": entry_id,
                "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s", entry_id)
    logger.info("[BATCH-FILE] %s", stats)
    return stats


def _run_bulk(config: NomadConfig, args: argparse.Namespace, query: dict, logger,
              manifest, completion_index: CompletionIndex) -> dict:
    """Stream one bulk archive zip and normalize each member."""
    client = NomadClient(config)
    zip_path = config.bulk_dir / f"nomad_{args.scope}_{manifest['run_id']}.zip"
    client.download_archive_bulk(query, zip_path, logger=logger)
    stats = {"records": 0, "success": 0, "failed": 0, "skipped": 0, "zip": str(zip_path)}
    for item in iter_bulk_zip_documents(zip_path):
        entry_id = item["entry_id"]
        stats["records"] += 1
        if not args.no_resume and completion_index.is_completed(entry_id):
            stats["skipped"] += 1
            continue
        try:
            _normalize_and_save(config, item, args, logger, manifest, stats, persist_raw=True)
        except Exception as error:
            stats["failed"] += 1
            append_manifest_item(manifest, {
                "source_id": source_id_for(entry_id), "entry_id": entry_id,
                "status": "failed", "error": str(error),
            })
            logger.exception("[ERROR] %s", entry_id)
        if args.max_records is not None and stats["records"] >= args.max_records:
            break
    logger.info("[BATCH-BULK] %s", stats)
    return stats


def parse_args() -> argparse.Namespace:
    """Parse batch crawler arguments."""
    parser = argparse.ArgumentParser(description="Batch download and normalize the NOMAD Archive.")
    parser.add_argument("--scope", choices=("dft", "all"), default="dft",
                        help="'dft' filters domain=dft; 'all' targets every public entry.")
    parser.add_argument("--query-json", default=None,
                        help="Explicit NOMAD search query as a JSON object, or '@path' to read a file "
                             "(overrides --scope).")
    parser.add_argument("--mode", choices=("per-entry", "bulk"), default="per-entry",
                        help="per-entry fetches archive/query per id; bulk streams download/query.")
    parser.add_argument("--entry-id-file", default=None,
                        help="Text file with one entry_id per line; skips enumeration.")
    parser.add_argument("--max-records", type=int, default=None,
                        help="Process at most this many entries in this run.")
    parser.add_argument("--page-size", type=parse_page_size, default=100,
                        help=f"Entries-query page size, 1-{MAX_PAGE_SIZE} (default 100).")
    parser.add_argument("--after", default=None, help="Resume enumeration after this page value.")
    parser.add_argument("--data-root", default=None,
                        help="Output directory; defaults to NOMAD_DATA_ROOT or data/dft/nomad.")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--progress", type=int, default=1000,
                        help="Log a progress line every N saved records (0 disables).")
    parser.add_argument("--no-symmetry", action="store_true",
                        help="Skip spglib space-group derivation for speed.")
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Run a NOMAD batch pipeline with a manifest."""
    args = parse_args()
    query = build_query(args.scope, args.query_json)
    data_root = Path(args.data_root) if args.data_root else default_data_root()
    config = NomadConfig(
        data_root=data_root, request_timeout=args.timeout,
        sleep_seconds=args.sleep, page_size=args.page_size, token=token_from_env(),
    )
    if args.entry_id_file:
        requested = [line.strip() for line in Path(args.entry_id_file).read_text(encoding="utf-8").splitlines() if line.strip()]
    else:
        requested = [f"scope:{args.scope}"]
    manifest = start_manifest(
        config.data_root / "manifests",
        SOURCE,
        {"scope": args.scope, "query": query, "mode": args.mode, "max_records": args.max_records,
         "page_size": args.page_size, "after": args.after, "entry_id_file": args.entry_id_file,
         "resume": not args.no_resume, "derive_symmetry": not args.no_symmetry},
        requested,
    )
    logger = create_logger("crawler.nomad.batch", config.data_root / "logs", run_id=manifest["run_id"])
    logger.info("[START] scope=%s mode=%s query=%s", args.scope, args.mode,
                json.dumps(query, ensure_ascii=False))
    try:
        with CompletionIndex(config.database_path) as completion_index:
            if args.entry_id_file:
                stats = _run_entry_id_file(config, args, logger, manifest, completion_index, args.entry_id_file)
            elif args.mode == "bulk":
                stats = _run_bulk(config, args, query, logger, manifest, completion_index)
            else:
                stats = _run_per_entry(config, args, query, logger, manifest, completion_index)
    except Exception as error:
        logger.exception("[FATAL] scope=%s", args.scope)
        finish_manifest(manifest, {"status": "failed", "error": str(error)})
        raise
    finish_manifest(manifest, stats)
    logger.info("completed run_id=%s %s", manifest["run_id"], stats)


if __name__ == "__main__":
    main()
