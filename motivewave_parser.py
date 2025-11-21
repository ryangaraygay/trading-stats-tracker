"""
Helpers for parsing MotiveWave session logs into Trade records.
"""

import re
from datetime import datetime
from typing import Iterable, List, Optional

from trade import Trade

# Regex matches OrderDirectory::orderFilled lines with expected fields.
FILL_PATTERN = re.compile(
    r"OrderDirectory::orderFilled\(\) order: ID: (\S+) (\S+) (\S+)\.CME.*"
    r"(Filled BUY|Filled SELL).*Qty:(\d+\.\d+).*"
    r"Last Fill Time:\s*(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}\s[AP]M).*"
    r"fill price: (\d+\.\d+)"
)


def _parse_fill_line(line: str) -> Optional[Trade]:
    """
    Parse a single log line for a fill. Returns None if the line does not match.
    """
    match = FILL_PATTERN.search(line)
    if not match:
        return None

    order_id = int(re.sub(r"[^0-9]", "", match.group(1)))
    account_name = match.group(2)
    contract_symbol = match.group(3)
    order_type = match.group(4)
    quantity = float(match.group(5))
    fill_time_str = match.group(6)
    fill_price = float(match.group(7))
    fill_time = datetime.strptime(fill_time_str.strip(), "%m/%d/%Y %I:%M %p")

    return Trade(
        account_name,
        order_id,
        order_type,
        contract_symbol,
        quantity,
        fill_price,
        fill_time,
    )


def parse_fills_from_file(file_path: str) -> List[Trade]:
    """
    Parse fills from a single MotiveWave log file.
    """
    fills: List[Trade] = []
    for trade, _ in iter_fill_matches(file_path):
        fills.append(trade)
    return fills


def parse_fills(file_paths: Iterable[str]) -> List[Trade]:
    """
    Parse fills across multiple MotiveWave log files.

    Duplicates (by account_name + order_id) are suppressed to mirror the
    existing GUI behavior.
    """
    unique_trades = {}
    for file_path in file_paths:
        for trade in parse_fills_from_file(file_path):
            unique_trades[(trade.account_name, trade.order_id)] = trade

    return list(unique_trades.values())


def iter_fill_matches(file_path: str):
    """
    Yield (Trade, raw_line) pairs for each fill in the given log file.
    """
    with open(file_path, "r") as file:
        for line in file:
            trade = _parse_fill_line(line)
            if trade:
                yield trade, line.rstrip("\n")
