# MotiveWave JSONL Export Design

Design for a CLI that converts MotiveWave session logs into normalized, deduped
JSONL suitable for cross-account analysis without re-parsing the GUI pipeline.

## Background
- Source: MotiveWave session logs under `~/Library/Mobile Documents/com~apple~CloudDocs/MyFiles/backups/MotiveWave Logs`.
- Volume: ~291 files, ~4.5 MB total, ~15.5 KB avg, ~8 months, potentially
  hundreds of accounts, overlapping fills across sessions on the same day.
- Current code parses on demand via `TradeStatsProcessor.get_fills(file_paths)`
  for GUI dialogs; future analysis needs a reusable, incremental export that
  preserves granular fills (no aggregation).

## Goals
- CLI to scan all available MotiveWave logs, parse fills once, and write a
  canonical JSONL dataset for downstream analysis (LLM-friendly, pandas-friendly).
- Preserve all fields surfaced by `get_fills(...)` plus provenance (session file,
  parser version, ingested_at).
- Support incremental runs, change detection, and deduping across overlapping
  sessions.
- Provide a manifest/state file for resumability and debugging.

## Non-Goals
- No GUI integration or stats computation here.
- No schema migration tooling; assume schema additions are backwards compatible.
- No aggregation or derived metrics (keep raw fills only).

## Inputs
- Required: `--input` path to MotiveWave logs (default to the iCloud path above
  if present).
- Optional filters: `--since YYYY-MM-DD` (skip older files), `--accounts` list to
  limit parsing, `--file-glob` to narrow sessions (e.g., `*.log`).

## Outputs
- Base output dir (default `data/mw_fills/`):
  - Partitioned JSONL: `account=<id>/date=YYYY-MM-DD/fills.jsonl`
  - Errors: `errors.jsonl` (parse/validation failures, non-fatal)
  - Schema doc: `schema.json` (field names, types)
  - Manifest/state: `state.json`

### Fill record (JSON object per line)
- Fields (drawn from `get_fills` and minimal extras):
  - `account_id`: string (from log)
  - `order_id`: integer (digits only, per existing regex)
  - `order_side`: `BUY` or `SELL` (from `order_type`)
  - `instrument`: string (contract symbol)
  - `qty`: float
  - `price`: float
  - `exec_time`: ISO-8601 string (with timezone if derivable; otherwise local)
  - `session_file`: basename of source log
  - `session_mtime`: ISO-8601 of file mtime
  - `ingested_at`: ISO-8601 of ingest run
  - `parser_version`: string (bumped when regex/logic changes)
  - `digest`: sha256 hash used for dedupe
  - Optional passthrough: `raw_line` for debugging (guarded by flag)

### Digest (dedupe key)
`sha256(f"{account_id}|{instrument}|{exec_time_iso}|{qty}|{price}|{order_id}")`
Keep stable when parser changes; if digest schema changes, bump parser_version
and allow `--force-reparse` to rebuild.

## Manifest / State (`state.json`)
- `parser_version`: string
- `runs`: append-only history of ingest runs (timestamp, counts)
- `sessions`: map of session file path → `{mtime, size, sha256}` used to skip
  unchanged files
- `partitions`: optional counts per `account/date` for quick sanity checks

## CLI interface
- Module: `python -m scripts.export_mw_fills` (new script).
- Flags:
  - `--input <path>` (repeatable; file or dir; default to MotiveWave logs path)
  - `--inputs <path...>` (alternative form for multiple paths)
  - `--output <dir>` (default `data/mw_fills`)
  - `--since YYYY-MM-DD`
  - `--accounts acc1 acc2`
  - `--latest` (only process the newest session file by mtime)
  - `--force-reparse` (ignore manifest, reprocess all)
  - `--dry-run` (report what would be processed)
  - `--raw-line` (include raw log line field)
  - `--stdout` (stream JSONL to stdout instead of writing files)

## Processing flow
1. Load `state.json` if it exists; validate parser_version unless
   `--force-reparse`.
2. Discover session files under `--input` (glob filter, since filter).
3. For each file:
   - Skip if unchanged vs manifest (size/mtime/hash) unless forced.
   - Parse fills using refactored `get_fills` core (shared logic to avoid
     diverging from GUI).
   - Normalize to fill records; attach session metadata.
   - Compute digests; track per-partition dedupe set.
   - Append non-duplicate fills to partitioned `fills.jsonl`.
   - Log parse errors to `errors.jsonl` (do not abort batch).
4. Update `state.json` with processed sessions and run summary.
5. Optional: emit counts to stdout for monitoring.

## Reuse of existing code
- Extract parsing logic from `TradeStatsProcessor.get_fills` into a shared helper
  (e.g., `motivewave_parser.py`) to avoid regex drift between GUI and CLI.
- Ensure the regex and time parsing remain identical to current behavior unless
  parser_version is intentionally bumped.

## Future Work: Market Data Bridging Limitations
- Current 1-minute bar bridge for ESZ5 uses MotiveWave `bar_data1` when present
  and falls back to aggregating MotiveWave `tick_data` into 1-minute buckets.
- Tick aggregation approximates per-record timestamps by distributing ticks
  evenly across each hour-long file block based on record index; this preserves
  ordering and approximate minute placement but is not millisecond-accurate.
- This is sufficient for:
  - validating that fill prices fall within daily bar ranges, and
  - coarse-grained context (e.g., whether a trade went with/against the 1-min trend).
- It is not yet sufficient for:
  - precise microstructure analysis (exact tick timing, spreads, order-flow around entry/exit), or
  - reconstructing exact Rithmic timestamps for replay-quality analytics.
- Future improvements:
  - decode the true tick timestamp fields in `tick_data` rather than relying on
    file epoch + record index,
  - store 1-minute aggregates (and possibly per-trade windows) in a columnar
    format (Parquet) for more efficient downstream analysis,
  - extend the bridge to support additional instruments (e.g., MESZ5) once their
    historical data is confirmed and decoded.

## Testing notes
- Unit test the parser helper with fixture lines (BUY/SELL, decimals, varying
  times).
- Integration test: temporary input dir with multiple session files (including
  duplicates) → assert deduped counts, manifest updates, and partition layout.
