"""
CLI to export MotiveWave fills into partitioned JSONL with manifest/dedupe.
"""

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from motivewave_parser import iter_fill_matches

PARSER_VERSION = "1.0"
DEFAULT_INPUT = (
    Path.home()
    / "Library"
    / "Mobile Documents"
    / "com~apple~CloudDocs"
    / "MyFiles"
    / "backups"
    / "MotiveWave Logs"
)
DEFAULT_OUTPUT = Path("data/mw_fills")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export MotiveWave fills to JSONL partitions."
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="inputs_single",
        action="append",
        type=Path,
        help="Path to a MotiveWave session log or directory (repeatable). Defaults to the standard iCloud path if not provided.",
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        type=Path,
        help="Paths to MotiveWave session logs or directories (alternative to --input).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output directory for JSONL partitions and state (default: data/mw_fills).",
    )
    parser.add_argument(
        "--since",
        type=str,
        help="Only process session files with mtime on/after this date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--accounts",
        nargs="+",
        help="Optional list of account ids to include (others skipped).",
    )
    parser.add_argument(
        "--file-glob",
        type=str,
        default="*",
        help="Glob pattern for session files (default: *).",
    )
    parser.add_argument(
        "--latest",
        action="store_true",
        help="Process only the latest session file (by mtime) from the discovered inputs.",
    )
    parser.add_argument(
        "--force-reparse",
        action="store_true",
        help="Reprocess all sessions regardless of manifest.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report counts without writing output or updating state.",
    )
    parser.add_argument(
        "--raw-line",
        action="store_true",
        help="Include raw log line in output records (for debugging).",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Stream JSONL to stdout instead of writing partition files.",
    )
    return parser.parse_args(argv)


def load_state(path: Path) -> Dict:
    if not path.exists():
        return {"parser_version": PARSER_VERSION, "sessions": {}, "runs": []}
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_state(path: Path, state: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(state, file, indent=2)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_file_signature(path: Path) -> Dict:
    stat_result = path.stat()
    return {
        "size": stat_result.st_size,
        "mtime": stat_result.st_mtime,
        "sha256": sha256_file(path),
    }


def parse_since(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(value)


def discover_sessions(input_dir: Path, glob_pattern: str) -> List[Path]:
    if not input_dir.exists():
        return []
    return [
        path for path in sorted(input_dir.rglob(glob_pattern)) if path.is_file()
    ]


def sanitize_component(value: str) -> str:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in value.strip())
    return safe or "unknown"


def partition_path(output_dir: Path, account_id: str, exec_date: date) -> Path:
    account_component = f"account={sanitize_component(account_id)}"
    date_component = f"date={exec_date.isoformat()}"
    return output_dir / account_component / date_component / "fills.jsonl"


def load_partition_digests(path: Path) -> Set[str]:
    digests: Set[str] = set()
    if not path.exists():
        return digests
    with path.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                record = json.loads(line)
                digest = record.get("digest")
                if digest:
                    digests.add(digest)
            except json.JSONDecodeError:
                continue
    return digests


def compute_digest(account_id: str, instrument: str, exec_time: str, qty: float, price: float, order_id: int) -> str:
    key = f"{account_id}|{instrument}|{exec_time}|{qty}|{price}|{order_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def build_record(
    trade,
    session_file: Path,
    session_signature: Dict,
    ingested_at: str,
    include_raw_line: bool,
    raw_line: Optional[str],
) -> Dict:
    exec_time = trade.fill_time
    exec_time_iso = exec_time.isoformat()
    order_side = "BUY" if "BUY" in trade.order_type.upper() else "SELL"
    record = {
        "account_id": trade.account_name,
        "order_id": trade.order_id,
        "order_side": order_side,
        "order_type": trade.order_type,
        "instrument": trade.contract_symbol,
        "qty": trade.quantity,
        "price": trade.fill_price,
        "exec_time": exec_time_iso,
        "session_file": session_file.name,
        "session_mtime": datetime.fromtimestamp(
            session_signature["mtime"], tz=timezone.utc
        ).isoformat(),
        "ingested_at": ingested_at,
        "parser_version": PARSER_VERSION,
    }
    record["digest"] = compute_digest(
        record["account_id"],
        record["instrument"],
        exec_time_iso,
        record["qty"],
        record["price"],
        record["order_id"],
    )
    if include_raw_line and raw_line is not None:
        record["raw_line"] = raw_line
    return record


def save_records(path: Path, records: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record) + "\n")


def gather_input_paths(args: argparse.Namespace) -> List[Path]:
    paths: List[Path] = []
    if args.inputs:
        paths.extend(args.inputs)
    if args.inputs_single:
        paths.extend(args.inputs_single)
    if not paths:
        paths.append(DEFAULT_INPUT)
    return [path.expanduser() for path in paths]


def resolve_sessions(
    inputs: List[Path], glob_pattern: str, since_date: Optional[date], latest_only: bool
) -> List[Path]:
    sessions: List[Path] = []
    for path in inputs:
        if path.is_file():
            sessions.append(path)
            continue
        sessions.extend(discover_sessions(path, glob_pattern))

    if since_date:
        sessions = [
            session
            for session in sessions
            if datetime.fromtimestamp(session.stat().st_mtime).date() >= since_date
        ]

    if not sessions:
        return []

    sessions = sorted(set(sessions))

    if latest_only:
        latest = max(sessions, key=lambda p: p.stat().st_mtime)
        return [latest]

    return sessions


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    allowed_accounts = set(args.accounts) if args.accounts else None
    since_date = parse_since(args.since)
    ingest_time = datetime.now(timezone.utc).isoformat()
    output_dir = args.output.expanduser()
    state_path = output_dir / "state.json"
    errors_path = output_dir / "errors.jsonl"

    state = load_state(state_path)
    force_reparse = args.force_reparse
    if state.get("parser_version") != PARSER_VERSION:
        print(
            f"[info] manifest parser_version {state.get('parser_version')} differs; reprocessing all sessions",
            file=sys.stderr,
        )
        force_reparse = True
        state["parser_version"] = PARSER_VERSION

    input_paths = gather_input_paths(args)
    sessions = resolve_sessions(
        input_paths, args.file_glob, since_date, latest_only=args.latest
    )
    if not sessions:
        print("[info] no session files found")
        return 0

    partition_cache: Dict[Path, Set[str]] = {}
    metrics = {
        "processed_sessions": 0,
        "skipped_sessions": 0,
        "parsed_fills": 0,
        "written_fills": 0,
        "duplicates": 0,
    }

    def get_partition_digests(path: Path) -> Set[str]:
        if path not in partition_cache:
            partition_cache[path] = load_partition_digests(path)
        return partition_cache[path]

    def log_error(payload: Dict) -> None:
        if args.dry_run:
            return
        errors_path.parent.mkdir(parents=True, exist_ok=True)
        with errors_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload) + "\n")

    for session_file in sessions:
        try:
            signature = get_file_signature(session_file)
        except FileNotFoundError:
            metrics["skipped_sessions"] += 1
            continue

        if since_date:
            mtime_date = datetime.fromtimestamp(signature["mtime"]).date()
            if mtime_date < since_date:
                metrics["skipped_sessions"] += 1
                continue

        prior = state.get("sessions", {}).get(str(session_file))
        if prior and not force_reparse:
            if (
                prior.get("sha256") == signature["sha256"]
                and prior.get("size") == signature["size"]
            ):
                metrics["skipped_sessions"] += 1
                continue

        metrics["processed_sessions"] += 1

        try:
            matches = list(iter_fill_matches(session_file))
        except Exception as exc:  # pragma: no cover - defensive
            log_error(
                {
                    "session_file": str(session_file),
                    "error": str(exc),
                    "context": "read_failure",
                }
            )
            continue

        session_records_by_partition: Dict[Path, List[Dict]] = {}
        session_duplicates = 0
        session_parsed = 0

        for trade, raw_line in matches:
            if allowed_accounts and trade.account_name not in allowed_accounts:
                continue

            session_parsed += 1
            record = build_record(
                trade,
                session_file,
                signature,
                ingest_time,
                args.raw_line,
                raw_line,
            )
            partition = partition_path(
                output_dir, record["account_id"], trade.fill_time.date()
            )
            digests = get_partition_digests(partition)
            if record["digest"] in digests:
                session_duplicates += 1
                continue

            digests.add(record["digest"])
            session_records_by_partition.setdefault(partition, []).append(record)

        metrics["parsed_fills"] += session_parsed
        metrics["duplicates"] += session_duplicates

        if args.dry_run:
            continue

        if not args.stdout:
            for partition, records in session_records_by_partition.items():
                save_records(partition, records)

        if args.stdout:
            for records in session_records_by_partition.values():
                for record in records:
                    print(json.dumps(record))

        written = sum(len(records) for records in session_records_by_partition.values())
        metrics["written_fills"] += written
        state.setdefault("sessions", {})[str(session_file)] = signature

    if not args.dry_run:
        state.setdefault("runs", []).append(
            {
                "ingested_at": ingest_time,
                "parser_version": PARSER_VERSION,
                "processed_sessions": metrics["processed_sessions"],
                "skipped_sessions": metrics["skipped_sessions"],
                "parsed_fills": metrics["parsed_fills"],
                "written_fills": metrics["written_fills"],
                "duplicates": metrics["duplicates"],
            }
        )
        save_state(state_path, state)

    print(
        json.dumps(
            {
                "processed_sessions": metrics["processed_sessions"],
                "skipped_sessions": metrics["skipped_sessions"],
                "parsed_fills": metrics["parsed_fills"],
                "written_fills": metrics["written_fills"],
                "duplicates": metrics["duplicates"],
                "output": str(output_dir),
                "dry_run": args.dry_run,
                "stdout": args.stdout,
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
