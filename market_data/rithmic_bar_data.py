"""
Helpers for parsing MotiveWave RITHMIC bar_data1 files into 1-minute bars.

Adapted from the standalone script at
`shared/analyses/market-data/motivewave-rithmic/parse_bar_data.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, List

import struct

REC_SIZE = 71
HEADER_SIZE = 80
GUARD_MINUTES = 360  # allow minor marker drift


@dataclass
class Bar1m:
    """
    Single 1-minute bar decoded from a bar_data1 file.
    """

    timestamp_utc: datetime
    timestamp_ms: int
    minute_index: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    meta_prefix_hex: str

    @property
    def timestamp_local_naive(self) -> datetime:
        """
        Timestamp converted to local timezone and made naive.
        Useful for aligning with MotiveWave log times stored without tz.
        """
        return self.timestamp_utc.astimezone().replace(tzinfo=None)


def _extract_rows(path: Path) -> Iterable[Bar1m]:
    """
    Internal: decode all bar rows from a single bar_data1 file.
    """
    raw = path.read_bytes()
    if len(raw) < HEADER_SIZE:
        raise ValueError(f"{path} is too small to be a MotiveWave bar file")

    try:
        epoch_ms = int(path.stem)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"File name {path.name} does not start with an epoch") from exc

    start_minute = int.from_bytes(raw[76:80], "big", signed=False)
    payload = raw[HEADER_SIZE:]
    record_count = len(payload) // REC_SIZE
    payload = payload[: record_count * REC_SIZE]

    prev_marker = start_minute - 1
    for idx in range(record_count):
        chunk = payload[idx * REC_SIZE : (idx + 1) * REC_SIZE]
        marker = None
        marker_offset = None
        for pos in range(20, REC_SIZE - 3):
            if chunk[pos] == 0 and chunk[pos + 1] == 0:
                candidate = int.from_bytes(chunk[pos : pos + 4], "big")
                if start_minute <= candidate <= prev_marker + GUARD_MINUTES:
                    marker = candidate
                    marker_offset = pos
                    break
        if marker is None:
            marker = prev_marker + 1
        if marker_offset is None or marker_offset + 24 > REC_SIZE:
            prev_marker = marker
            continue

        o, h, l, c = (
            struct.unpack(">f", chunk[marker_offset + 4 + j : marker_offset + 8 + j])[0]
            for j in range(0, 16, 4)
        )
        bar_volume = struct.unpack(">f", chunk[marker_offset + 20 : marker_offset + 24])[0]
        meta_prefix = chunk[:marker_offset].hex()
        ts_ms = epoch_ms + marker * 60_000
        ts_utc = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
        prev_marker = marker
        yield Bar1m(
            timestamp_utc=ts_utc,
            timestamp_ms=ts_ms,
            minute_index=marker,
            open=o,
            high=h,
            low=l,
            close=c,
            volume=bar_volume,
            meta_prefix_hex=meta_prefix,
        )


def load_bars_for_range(
    instrument_dir: Path, start_date: date, end_date: date
) -> List[Bar1m]:
    """
    Load all 1-minute bars for the given instrument directory and
    [start_date, end_date] (inclusive), where dates are datetime.date.
    """
    bars: List[Bar1m] = []
    for path in sorted(instrument_dir.glob("*.bar_data1")):
        for bar in _extract_rows(path):
            local_date = bar.timestamp_local_naive.date()
            if start_date <= local_date <= end_date:
                bars.append(bar)
    return bars
