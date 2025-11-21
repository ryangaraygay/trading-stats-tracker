"""
Aggregate MotiveWave Rithmic tick_data files into approximate 1-minute bars.

This is a best-effort bridge: we use the file epoch (from the filename) and
record index to approximate timestamps within each tick_data block, then bucket
ticks into local 1-minute bars. Where bar_data1 backfill is present, that
remains the preferred source; this module is intended as a fallback.
"""

from __future__ import annotations

import math
import struct
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from market_data.rithmic_bar_data import Bar1m

HEADER_SIZE = 72
RECORD_SIZE = 72


@dataclass
class TickRecord:
    """
    Minimal tick record with an approximate timestamp and trade price/size.
    """

    timestamp_utc: datetime
    trade_price: float
    trade_size: int

    @property
    def timestamp_local_naive(self) -> datetime:
        local = self.timestamp_utc.astimezone()
        return local.replace(tzinfo=None)


def _iter_ticks_with_time(path: Path) -> Iterable[TickRecord]:
    """
    Decode tick_data into TickRecord entries with approximate timestamps.

    We treat each tick_data file as roughly a one-hour block and distribute
    records evenly across that hour based on record index. This preserves
    ordering and approximate minute placement, but is not millisecond-accurate.
    """
    raw = path.read_bytes()
    if len(raw) <= HEADER_SIZE:
        return

    payload = raw[HEADER_SIZE:]
    record_count = len(payload) // RECORD_SIZE
    if record_count == 0:
        return

    payload = payload[: record_count * RECORD_SIZE]

    try:
        file_epoch_ms = int(path.stem)
    except ValueError:
        return

    # Assume ~1 hour of data per file.
    block_ms = 60 * 60 * 1000
    step_ms = block_ms / max(record_count - 1, 1)

    local_tz = datetime.now().astimezone().tzinfo

    for idx in range(record_count):
        chunk = payload[idx * RECORD_SIZE : (idx + 1) * RECORD_SIZE]
        trade_price = struct.unpack(">f", chunk[52:56])[0]
        trade_size = int.from_bytes(chunk[48:52], "big")

        if not math.isfinite(trade_price) or trade_size <= 0:
            continue

        # Filter to plausible ES/MES ranges to avoid corrupt floats.
        if not (4000 <= trade_price <= 8000):
            continue

        ts_ms = file_epoch_ms + int(idx * step_ms)
        # Treat file epoch as UTC.
        ts_utc = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        yield TickRecord(timestamp_utc=ts_utc, trade_price=trade_price, trade_size=trade_size)


def aggregate_ticks_to_1m_bars(
    instrument_dir: Path, start_date: date, end_date: date
) -> List[Bar1m]:
    """
    Aggregate ESZ5/MESZ5 tick_data under instrument_dir into approximate
    1-minute bars for the given local date range.
    """
    minute_buckets: Dict[datetime, Dict[str, float]] = defaultdict(
        lambda: {
            "open": 0.0,
            "high": float("-inf"),
            "low": float("inf"),
            "close": 0.0,
            "volume": 0.0,
            "count": 0.0,
        }
    )

    if not instrument_dir.exists():
        return []

    local_tz = datetime.now().astimezone().tzinfo

    for path in instrument_dir.glob("*.tick_data"):
        # Quick file-level filter using epoch from filename to avoid decoding
        # the entire file when it is far outside the requested date range.
        try:
            file_epoch_ms = int(path.stem)
        except ValueError:
            file_epoch_ms = None

        if file_epoch_ms is not None:
            file_start_utc = datetime.fromtimestamp(file_epoch_ms / 1000, tz=timezone.utc)
            file_start_local_date = file_start_utc.astimezone(local_tz).date()
            # Assume roughly a 1-hour block. Skip if the whole block is
            # clearly outside the requested window (with a one-day guard).
            if file_start_local_date < (start_date - date.resolution) and file_start_local_date < start_date:
                if file_start_local_date < start_date - date.resolution:
                    pass
            # Simpler and safer: only decode ticks and filter inside the loop;
            # the filename check is best-effort and not strictly required.

        for tick in _iter_ticks_with_time(path):
            local_dt = tick.timestamp_utc.astimezone(local_tz).replace(tzinfo=None)
            if not (start_date <= local_dt.date() <= end_date):
                continue
            minute_key = local_dt.replace(second=0, microsecond=0)
            bucket = minute_buckets[minute_key]

            price = tick.trade_price
            if bucket["count"] == 0:
                bucket["open"] = price
                bucket["high"] = price
                bucket["low"] = price
                bucket["close"] = price
            else:
                bucket["high"] = max(bucket["high"], price)
                bucket["low"] = min(bucket["low"], price)
                bucket["close"] = price
            bucket["volume"] += tick.trade_size
            bucket["count"] += 1

    bars: List[Bar1m] = []
    for minute_key, agg in minute_buckets.items():
        if agg["count"] == 0:
            continue
        local_aware = minute_key.replace(tzinfo=local_tz)
        ts_utc = local_aware.astimezone(timezone.utc)
        ts_ms = int(ts_utc.timestamp() * 1000)
        bars.append(
            Bar1m(
                timestamp_utc=ts_utc,
                timestamp_ms=ts_ms,
                minute_index=0,
                open=agg["open"],
                high=agg["high"],
                low=agg["low"],
                close=agg["close"],
                volume=agg["volume"],
                meta_prefix_hex="",
            )
        )

    bars.sort(key=lambda b: b.timestamp_utc)
    return bars
