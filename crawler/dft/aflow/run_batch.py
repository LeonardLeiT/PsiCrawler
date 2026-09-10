"""
Batch material data extractor for AFLOW.

Workflow:
1. Query AFLUX for matching entries and their aurl values.
2. Extract each entry through aflow_extract_single.extract_single().
3. Store selected scalar properties in SQLite and full metadata/files on disk.

Usage:
    python aflow_extract_batch.py --max 10
    python aflow_extract_batch.py --species Li --egap-min 1 --egap-max 2 --max 50
    python aflow_extract_batch.py --query "Egap(1*,*2),catalog('ICSD')" --max 100
    python aflow_extract_batch.py --aurls-file aurls.txt
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from core.manifest import append_manifest_item, finish_manifest, start_manifest

from sources.dft.aflow.extractor import (
    DEFAULT_DATA_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_PROFILE,
    DEFAULT_SLEEP_SECONDS,
    DEFAULT_STATUS_JSON,
    DEFAULT_TIMEOUT_SECONDS,
    aflux_url,
    extract_single,
    http_get_json,
    init_database,
    load_status_json,
    save_json_atomic,
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(log_dir: str = "data/dft/aflow/logs") -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(log_dir) / f"aflow_batch_{timestamp}.log"

    logger = logging.getLogger("aflow_batch_extractor")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    ))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ---------------------------------------------------------------------------
# AFLUX query helpers
# ---------------------------------------------------------------------------

def quote_aflow_string(value: str) -> str:
    return "'" + value.replace("'", "\\'") + "'"


def build_aflux_filter_query(args: argparse.Namespace) -> str:
    """
    Build the AFLUX filter portion before field selection and paging.

    AFLUX uses:
    - comma for AND
    - N* for >= N
    - *N for <= N
    - quoted strings for string matching
    """
    if args.query:
        return args.query.strip().strip(",")

    filters: list[str] = []

    if args.species:
        for species in [s.strip() for s in args.species.split(",") if s.strip()]:
            filters.append(f"species({quote_aflow_string(species)})")

    if args.catalog:
        filters.append(f"catalog({quote_aflow_string(args.catalog.strip())})")

    if args.compound_contains:
        filters.append(f"compound(*{quote_aflow_string(args.compound_contains.strip())}*)")

    if args.egap_min is not None or args.egap_max is not None:
        lower = f"{args.egap_min}*" if args.egap_min is not None else "*"
        upper = f"*{args.egap_max}" if args.egap_max is not None else "*"
        if args.egap_min is not None and args.egap_max is not None:
            filters.append(f"Egap({lower},{upper})")
        elif args.egap_min is not None:
            filters.append(f"Egap({lower})")
        else:
            filters.append(f"Egap({upper})")

    if args.spacegroup is not None:
        filters.append(f"spacegroup_relax({args.spacegroup})")

    if args.ael:
        filters.append("ael_bulk_modulus_vrh(*)")

    if args.agl:
        filters.append("agl_debye(*)")

    if not filters:
        # A conservative default that returns a small, meaningful semiconductor set.
        filters.append("Egap(1*,*2)")

    return ",".join(filters)


def make_search_query(filter_query: str, page: int, page_size: int) -> str:
    fields = [
        "aurl",
        "auid",
        "compound",
        "species",
        "catalog",
        "Egap",
        "Egap_type",
        "spacegroup_relax",
        "Pearson_symbol_relax",
    ]
    return ",".join([filter_query, *fields, f"paging({page},{page_size})"])


def parse_total_count(result: dict[str, Any]) -> int | None:
    if not result:
        return 0
    first_key = next(iter(result.keys()))
    if " of " not in first_key:
        return None
    try:
        return int(first_key.split(" of ", 1)[1])
    except ValueError:
        return None


def fetch_aflux_page(filter_query: str, page: int, page_size: int, timeout: int) -> dict[str, Any]:
    query = make_search_query(filter_query, page=page, page_size=page_size)
    return http_get_json(aflux_url(query), timeout=timeout)


def fetch_aurl_list(
    filter_query: str,
    max_materials: int,
    page_size: int,
    timeout: int,
    logger: logging.Logger,
) -> list[dict[str, Any]]:
    """Fetch matching AFLUX entries containing at least aurl/auid."""
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    page = 1
    total_count: int | None = None

    while len(entries) < max_materials:
        result = fetch_aflux_page(filter_query, page=page, page_size=page_size, timeout=timeout)
        if total_count is None:
            total_count = parse_total_count(result)
            logger.info(f"  AFLUX total matches: {total_count if total_count is not None else 'unknown'}")

        if not result:
            break

        page_entries = list(result.values())
        if not page_entries:
            break

        for item in page_entries:
            if isinstance(item, dict) and item.get("aurl"):
                dedupe_key = item.get("auid") or item.get("aurl")
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                entries.append(item)
                if len(entries) >= max_materials:
                    break

        logger.info(f"  Fetched page {page}: {len(page_entries)} entries, selected {len(entries)}")

        if len(page_entries) < page_size:
            break
        if total_count is not None and page * page_size >= total_count:
            break
        page += 1

    return entries[:max_materials]


def read_aurls_file(path: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            value = line.strip()
            if not value or value.startswith("#"):
                continue
            entries.append({"aurl": value})
    return entries


def get_completed_auids(db_path: str) -> set[str]:
    if not Path(db_path).exists():
        return set()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT DISTINCT auid FROM extraction_log WHERE status IN ('success', 'partial')")
        values = {row[0] for row in cur.fetchall() if row[0]}
    except sqlite3.OperationalError:
        values = set()
    finally:
        conn.close()
    return values


def update_batch_metadata(
    db_path: str,
    status_path: str,
    stats: dict[str, int],
    batch_id: str,
    elapsed_s: float,
) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ("last_batch_id", batch_id))
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ("last_batch_time", datetime.now().isoformat()))
    cur.execute("SELECT COUNT(*) FROM materials")
    total_materials = cur.fetchone()[0]
    cur.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", ("total_materials", str(total_materials)))
    conn.commit()
    conn.close()

    all_status = load_status_json(status_path)
    all_status["_meta"] = {
        "last_batch_id": batch_id,
        "last_updated": datetime.now().isoformat(timespec="seconds"),
        "elapsed_s": round(elapsed_s, 2),
        "total_materials_in_db": total_materials,
        **stats,
    }
    save_json_atomic(Path(status_path), all_status)


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

def run_batch_extraction(
    entries: list[dict[str, Any]],
    db_path: str = DEFAULT_DB_PATH,
    data_dir: str = DEFAULT_DATA_DIR,
    status_path: str = DEFAULT_STATUS_JSON,
    profile: str = DEFAULT_PROFILE,
    extra_patterns: list[str] | None = None,
    sleep_between: float = DEFAULT_SLEEP_SECONDS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = 2,
    retry_delay: float = 5.0,
    resume: bool = True,
    logger: logging.Logger | None = None,
) -> dict[str, int]:
    logger = logger or setup_logging()
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    requested_entries = list(entries)
    manifest = start_manifest(Path(status_path).parent, "aflow", {"mode": "batch", "profile": profile, "sleep_between": sleep_between, "timeout": timeout, "max_retries": max_retries, "resume": resume}, [str(entry.get("auid") or entry.get("aurl") or "unknown") for entry in requested_entries])

    init_database(db_path)

    if resume:
        completed = get_completed_auids(db_path)
        original_count = len(entries)
        original_entries = entries
        entries = [entry for entry in entries if not entry.get("auid") or entry.get("auid") not in completed]
        skipped = original_count - len(entries)
        for entry in original_entries:
            if entry not in entries:
                append_manifest_item(manifest, {"source_id": entry.get("auid") or entry.get("aurl"), "status": "skipped", "attempts": 0})
    else:
        skipped = 0

    total = len(entries)
    stats = {"total": total + skipped, "success": 0, "partial": 0, "error": 0, "skipped": skipped}

    logger.info(f"{'=' * 60}")
    logger.info("  AFLOW Batch Extraction Started")
    logger.info(f"  Batch ID: {batch_id}")
    logger.info(f"  Materials to extract: {total}")
    logger.info(f"  Skipped by resume: {skipped}")
    logger.info(f"  Database: {os.path.abspath(db_path)}")
    logger.info(f"  Data directory: {os.path.abspath(data_dir)}")
    logger.info(f"  Download profile: {profile}")
    logger.info(f"{'=' * 60}\n")

    batch_start = time.time()
    for idx, entry in enumerate(entries, start=1):
        identifier = entry.get("aurl")
        label = entry.get("compound") or entry.get("auid") or identifier
        if not identifier:
            stats["error"] += 1
            logger.error(f"[{idx}/{total}] Missing aurl for entry: {entry}")
            continue

        logger.info(f"[{idx}/{total}] {label}")

        report = None
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                report = extract_single(
                    identifier=identifier,
                    db_path=db_path,
                    data_dir=data_dir,
                    status_path=status_path,
                    profile=profile,
                    file_patterns=extra_patterns,
                    timeout=timeout,
                    sleep_seconds=0.0,
                    dry_run=False,
                    batch_id=batch_id,
                    query_hit=entry,
                )
                if report.metadata and not report.errors:
                    stats["success"] += 1
                    append_manifest_item(manifest, {"source_id": report.auid or identifier, "status": "success", "attempts": attempt, "errors": [], "files_downloaded": len(report.files_downloaded)})
                    logger.info(f"         [OK] {report.auid} files={len(report.files_downloaded)}")
                    break
                if report.metadata:
                    stats["partial"] += 1
                    append_manifest_item(manifest, {"source_id": report.auid or identifier, "status": "partial", "attempts": attempt, "errors": report.errors, "files_downloaded": len(report.files_downloaded)})
                    logger.info(f"         [PARTIAL] {report.auid}: {'; '.join(report.errors)}")
                    break
                last_error = "; ".join(report.errors) if report.errors else "metadata not fetched"
            except Exception as exc:
                last_error = str(exc)

            logger.warning(f"         [FAIL] attempt {attempt}/{max_retries}: {last_error}")
            if attempt < max_retries:
                time.sleep(retry_delay * (2 ** (attempt - 1)))
        else:
            stats["error"] += 1
            append_manifest_item(manifest, {"source_id": identifier, "status": "failed", "attempts": max_retries, "error": last_error})
            logger.error(f"         [ERROR] {last_error}")

        if idx < total and sleep_between > 0:
            time.sleep(sleep_between)

    elapsed_s = time.time() - batch_start
    update_batch_metadata(db_path, status_path, stats, batch_id, elapsed_s)
    finish_manifest(manifest, {"requested": stats["total"], "success": stats["success"], "partial": stats["partial"], "failed": stats["error"], "skipped": stats["skipped"], "elapsed_s": round(elapsed_s, 2), "batch_id": batch_id})

    logger.info(f"\n{'=' * 60}")
    logger.info("  AFLOW Batch Extraction Complete")
    logger.info(f"  Total time: {elapsed_s:.1f}s")
    logger.info(f"  Success: {stats['success']}")
    logger.info(f"  Partial: {stats['partial']}")
    logger.info(f"  Error: {stats['error']}")
    logger.info(f"  Skipped: {stats['skipped']}")
    logger.info(f"{'=' * 60}")

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def selected_profile(args: argparse.Namespace) -> str:
    if args.include_vasp:
        return "vasp_raw"
    if args.include_electronic:
        return "electronic"
    return args.profile


def extra_patterns(args: argparse.Namespace) -> list[str] | None:
    if not args.extra_patterns:
        return None
    return [p.strip() for p in args.extra_patterns.split(",") if p.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch extract AFLOW material data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python aflow_extract_batch.py --max 10
  python aflow_extract_batch.py --species Li --egap-min 1 --egap-max 2 --max 20
  python aflow_extract_batch.py --query "Egap(1*,*2),catalog('ICSD')" --max 50
  python aflow_extract_batch.py --aurls-file aurls.txt --max 10
        """,
    )

    filter_group = parser.add_argument_group("AFLUX filters")
    filter_group.add_argument("--query", default=None, help="Raw AFLUX filter query without fields/paging")
    filter_group.add_argument("--species", default=None, help="Comma-separated required species, e.g. Li,N")
    filter_group.add_argument("--catalog", default=None, help="Catalog filter, e.g. ICSD")
    filter_group.add_argument("--compound-contains", default=None, help="Substring match against compound")
    filter_group.add_argument("--egap-min", type=float, default=None)
    filter_group.add_argument("--egap-max", type=float, default=None)
    filter_group.add_argument("--spacegroup", type=int, default=None)
    filter_group.add_argument("--ael", action="store_true", help="Require AEL bulk modulus data")
    filter_group.add_argument("--agl", action="store_true", help="Require AGL Debye data")
    filter_group.add_argument("--aurls-file", default=None, help="Text file with one AFLOW aurl/path per line")

    extract_group = parser.add_argument_group("Extraction")
    extract_group.add_argument("--max", type=int, default=10)
    extract_group.add_argument("--page-size", type=int, default=10)
    extract_group.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS)
    extract_group.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    extract_group.add_argument("--retries", type=int, default=2)
    extract_group.add_argument("--retry-delay", type=float, default=5.0)
    extract_group.add_argument("--no-resume", action="store_true")
    extract_group.add_argument(
        "--profile",
        choices=["core", "plots", "electronic", "symmetry", "bader", "vasp_raw", "all"],
        default=DEFAULT_PROFILE,
        help="Download profile. Default 'plots' stores structures plus existing PNG plots.",
    )
    extract_group.add_argument("--include-electronic", action="store_true", help="Shortcut for --profile electronic")
    extract_group.add_argument("--include-vasp", action="store_true", help="Shortcut for --profile vasp_raw")
    extract_group.add_argument("--extra-patterns", default=None)

    path_group = parser.add_argument_group("Paths")
    path_group.add_argument("--db-path", default=DEFAULT_DB_PATH)
    path_group.add_argument("--data-dir", default=DEFAULT_DATA_DIR)
    path_group.add_argument("--status-path", default=DEFAULT_STATUS_JSON)
    path_group.add_argument("--log-dir", default="data/dft/aflow/logs")

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    logger = setup_logging(args.log_dir)

    if args.aurls_file:
        material_entries = read_aurls_file(args.aurls_file)
        if args.max:
            material_entries = material_entries[: args.max]
        logger.info(f"Loaded {len(material_entries)} aurl entries from {args.aurls_file}")
    else:
        filter_query = build_aflux_filter_query(args)
        logger.info(f"AFLUX filter query: {filter_query}")
        material_entries = fetch_aurl_list(
            filter_query=filter_query,
            max_materials=args.max,
            page_size=args.page_size,
            timeout=args.timeout,
            logger=logger,
        )
        logger.info(f"Selected {len(material_entries)} entries for extraction")

    if not material_entries:
        logger.info("No AFLOW entries to extract. Exiting.")
        sys.exit(0)

    result_stats = run_batch_extraction(
        entries=material_entries,
        db_path=args.db_path,
        data_dir=args.data_dir,
        status_path=args.status_path,
        profile=selected_profile(args),
        extra_patterns=extra_patterns(args),
        sleep_between=args.sleep,
        timeout=args.timeout,
        max_retries=args.retries,
        retry_delay=args.retry_delay,
        resume=not args.no_resume,
        logger=logger,
    )

    sys.exit(0 if result_stats["error"] == 0 else 1)









