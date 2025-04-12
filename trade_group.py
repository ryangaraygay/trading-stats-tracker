import datetime
from collections import defaultdict
import math
from dataclasses import dataclass

# --- Define the strongly-typed TradeGroup structure ---
@dataclass
class TradeGroup:
    """
    Represents a single logical trade (which might involve multiple orders)
    with strongly typed attributes. Renamed from Trade to avoid conflicts.
    """
    entry_is_long: bool
    entry_time: datetime.datetime  # Typically the time of the first entry order
    exit_time: datetime.datetime   # Typically the time of the final exit order
    max_trade_size: float # Max contracts/lots held at any point during the trade
    trade_point: float    # Net profit/loss in points for the entire trade group
