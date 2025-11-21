"""
Bridge MotiveWave fills (TradeGroups) with 1-minute bar data for a limited
date range and account/instrument, as a first integration experiment.

For now this focuses on:
- one account (e.g., 119916)
- one futures symbol (e.g., ESZ5.CME or MESZ5.CME)
- MotiveWave Rithmic 1-minute bars reconstructed from tick_data

When analyzing MES contracts, we default to using the corresponding ES
market data (e.g., ESZ5 for MESZ5) so that we can still reason about price
and volume context even when MES tick decoding is incomplete.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from market_data.rithmic_bar_data import Bar1m
from market_data.rithmic_tick_aggregator import aggregate_ticks_to_1m_bars
from trade import Trade
from trade_stats_processor import TradeStatsProcessor
from config import Config


@dataclass
class BridgedTrade:
    """
    Single TradeGroup enriched with simple bar-context features.
    """

    account_id: str
    instrument: str
    entry_time: str
    exit_time: str
    is_long: bool
    trade_points: float
    trade_amount: float
    max_size: float
    bars_count: int
    bars_net_points: float
    bars_up_count: int
    bars_down_count: int


def parse_date(value: str) -> date:
    return date.fromisoformat(value)


def load_fills_from_jsonl(
    base_dir: Path,
    account_id: str,
    start_date: date,
    end_date: date,
    instrument_prefix: str,
) -> List[Trade]:
    """
    Load Trade objects for a given account/date range from exported fills.
    Filters instruments by prefix (e.g., 'ES' to focus on ES contracts).
    """
    trades: List[Trade] = []
    for acc_dir in base_dir.glob(f"account={account_id}"):
        for date_dir in acc_dir.glob("date=*"):
            date_str = date_dir.name.split("=", 1)[-1]
            day = date.fromisoformat(date_str)
            if not (start_date <= day <= end_date):
                continue
            fills_path = date_dir / "fills.jsonl"
            if not fills_path.exists():
                continue
            with fills_path.open("r", encoding="utf-8") as file:
                for line in file:
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if rec.get("account_id") != account_id:
                        continue
                    instrument = rec.get("instrument", "")
                    if instrument_prefix and not instrument.startswith(instrument_prefix):
                        continue
                    trades.append(
                        Trade(
                            rec["account_id"],
                            rec["order_id"],
                            rec["order_type"],
                            instrument,
                            rec["qty"],
                            rec["price"],
                            datetime.fromisoformat(rec["exec_time"]),
                        )
                    )
    return trades


def simple_bar_context_for_trade(
    entry_time: datetime, exit_time: datetime, bars: List[Bar1m]
) -> Dict:
    """
    Compute a handful of bar-based context features for a single trade window.
    """
    matching_bars = [
        b
        for b in bars
        if entry_time <= b.timestamp_local_naive <= exit_time
    ]
    if not matching_bars:
        return {
            "bars_count": 0,
            "bars_net_points": 0.0,
            "bars_up_count": 0,
            "bars_down_count": 0,
        }

    first_close = matching_bars[0].close
    last_close = matching_bars[-1].close
    net_points = last_close - first_close

    up = 0
    down = 0
    for b in matching_bars:
        if b.close > b.open:
            up += 1
        elif b.close < b.open:
            down += 1

    return {
        "bars_count": len(matching_bars),
        "bars_net_points": net_points,
        "bars_up_count": up,
        "bars_down_count": down,
    }


def bridge_trades_and_bars(
    fills_dir: Path,
    account_id: str,
    fills_prefix: str,
    market_instrument_dir: Path,
    start_date: date,
    end_date: date,
) -> List[BridgedTrade]:
    """
    Load fills and bar data, compute TradeGroups, and enrich each with bar context.
    """
    trades = load_fills_from_jsonl(
        fills_dir,
        account_id,
        start_date,
        end_date,
        instrument_prefix=fills_prefix,
    )
    if not trades:
        return []

    config = Config()
    processor = TradeStatsProcessor(config)
    _, _, trade_groups = processor.get_stats(trades)

    # For recent days we rely on tick_data to construct approximate 1-minute
    # bars. This preserves ordering and minute-level trend even when bar_data1
    # backfill is missing.
    bars = aggregate_ticks_to_1m_bars(market_instrument_dir, start_date, end_date)
    bridged: List[BridgedTrade] = []

    for tg in trade_groups:
        ctx = simple_bar_context_for_trade(tg.entry_time, tg.exit_time, bars)
        bridged.append(
            BridgedTrade(
                account_id=account_id,
                instrument=fills_prefix,
                entry_time=tg.entry_time.isoformat(),
                exit_time=tg.exit_time.isoformat(),
                is_long=tg.entry_is_long,
                trade_points=tg.trade_point,
                trade_amount=tg.trade_amount,
                max_size=tg.max_trade_size,
                bars_count=ctx["bars_count"],
                bars_net_points=ctx["bars_net_points"],
                bars_up_count=ctx["bars_up_count"],
                bars_down_count=ctx["bars_down_count"],
            )
        )
    return bridged


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bridge fills (TradeGroups) with MotiveWave Rithmic 1-minute bars."
    )
    parser.add_argument(
        "--account",
        required=True,
        help="Account id (e.g., 119916).",
    )
    parser.add_argument(
        "--instrument",
        required=True,
        help="Instrument symbol for fills (e.g., ESZ5.CME or MESZ5.CME).",
    )
    parser.add_argument(
        "--fills-dir",
        type=Path,
        default=Path("data/mw_fills"),
        help="Base directory of exported fills (default: data/mw_fills).",
    )
    parser.add_argument(
        "--hist-root",
        type=Path,
        default=(
            Path.home()
            / "Library"
            / "MotiveWave"
            / "historical_data"
            / "RITHMIC"
        ),
        help="Root directory for MotiveWave Rithmic historical data.",
    )
    parser.add_argument(
        "--no-es-for-mes",
        dest="use_es_for_mes",
        action="store_false",
        help="When set, do NOT map MESxx fills to ESxx market data (default is to use ES for MES).",
    )
    parser.set_defaults(use_es_for_mes=True)
    parser.add_argument(
        "--start",
        required=True,
        help="Start date (YYYY-MM-DD, local).",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="End date (YYYY-MM-DD, local).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/bridged_trades_bars.jsonl"),
        help="Output JSONL path for bridged trades.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    start_date = parse_date(args.start)
    end_date = parse_date(args.end)

    fills_symbol_root = args.instrument.split(".", 1)[0]
    fills_prefix = fills_symbol_root

    # Map MESxx fills to ESxx market data if requested (default).
    market_symbol = args.instrument
    if fills_symbol_root.startswith("MES") and args.use_es_for_mes:
        suffix = fills_symbol_root[3:]  # e.g., 'Z5'
        market_root = f"ES{suffix}"
        exchange = args.instrument.split(".", 1)[1] if "." in args.instrument else "CME"
        market_symbol = f"{market_root}.{exchange}"

    market_instrument_dir = args.hist_root / market_symbol
    if not market_instrument_dir.exists():
        raise SystemExit(f"Market instrument directory not found: {market_instrument_dir}")

    bridged = bridge_trades_and_bars(
        fills_dir=args.fills_dir,
        account_id=args.account,
        fills_prefix=fills_prefix,
        market_instrument_dir=market_instrument_dir,
        start_date=start_date,
        end_date=end_date,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        for bt in bridged:
            f.write(json.dumps(asdict(bt)) + "\n")

    print(
        json.dumps(
            {
                "account": args.account,
                "instrument": args.instrument,
                "start": args.start,
                "end": args.end,
                "bridged_trades": len(bridged),
                "output": str(args.output),
                "fills_prefix": fills_prefix,
                "market_instrument": market_symbol,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
