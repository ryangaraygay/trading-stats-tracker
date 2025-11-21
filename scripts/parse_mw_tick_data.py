#!/usr/bin/env python3
"""
Convert MotiveWave Rithmic tick_data files into a readable CSV stream.

Adapted from shared/analyses/market-data/motivewave-rithmic/parse_tick_data.py.
"""

from __future__ import annotations

import argparse
import csv
import math
import struct
from pathlib import Path
from typing import Iterator, Tuple

HEADER_SIZE = 72
RECORD_SIZE = 72
TICK_SIZE = 0.25
SIDE_TOLERANCE = TICK_SIZE / 2.0


def _iter_ticks(
    path: Path,
) -> Iterator[Tuple[int, int, float, float, float, float, float, float, str]]:
    """
    Yield (record_idx, trade_size, trade_price, bid_price, bid_size,
    ask_price, ask_size, side) tuples for each 72-byte record.
    """

    raw = path.read_bytes()
    if len(raw) <= HEADER_SIZE:
        return

    payload = raw[HEADER_SIZE:]
    record_count = len(payload) // RECORD_SIZE
    payload = payload[: record_count * RECORD_SIZE]

    for idx in range(record_count):
        chunk = payload[idx * RECORD_SIZE : (idx + 1) * RECORD_SIZE]

        trade_size = int.from_bytes(chunk[48:52], "big")
        trade_price = struct.unpack(">f", chunk[52:56])[0]
        ask_price = struct.unpack(">f", chunk[56:60])[0]
        ask_size = int.from_bytes(chunk[60:64], "big")
        bid_price = struct.unpack(">f", chunk[64:68])[0]
        bid_size = int.from_bytes(chunk[68:72], "big")

        if math.isfinite(ask_price) and abs(trade_price - ask_price) <= SIDE_TOLERANCE:
            side = "lift"
        elif math.isfinite(bid_price) and abs(trade_price - bid_price) <= SIDE_TOLERANCE:
            side = "hit"
        else:
            side = "other"

        yield idx, trade_size, trade_price, bid_price, bid_size, ask_price, ask_size, side


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Path to <epoch>.tick_data file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output CSV path (defaults to same folder)",
    )
    args = parser.parse_args()

    file_epoch_ms = int(args.input.stem)
    rows = list(_iter_ticks(args.input))
    if not rows:
        raise SystemExit("No tick records parsed.")

    output = args.output or args.input.with_suffix(".tick.csv")
    with output.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "file_epoch_ms",
                "record_index",
                "sequence_hint",
                "trade_price",
                "trade_size",
                "bid_price",
                "bid_size",
                "ask_price",
                "ask_size",
                "side",
            ]
        )
        for (
            idx,
            trade_size,
            trade_price,
            bid_price,
            bid_size,
            ask_price,
            ask_size,
            side,
        ) in rows:
            sequence_hint = file_epoch_ms + idx
            writer.writerow(
                [
                    file_epoch_ms,
                    idx,
                    sequence_hint,
                    trade_price,
                    trade_size,
                    bid_price,
                    bid_size,
                    ask_price,
                    ask_size,
                    side,
                ]
            )

    print(f"Wrote {len(rows)} ticks to {output}")


if __name__ == "__main__":
    main()

