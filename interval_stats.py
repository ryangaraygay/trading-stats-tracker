import datetime
from dataclasses import dataclass, field

# --- Define a structure for the output statistics (Remains the same) ---
@dataclass
class IntervalStats:
    """Represents the calculated statistics for a single 5-minute time interval."""
    # Changed from datetime.datetime to datetime.time
    interval_start_time: datetime.time
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    breakeven_trades: int = 0
    long_trades: int = 0
    short_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_profit_loss_points: float = 0.0
    gross_profit_points: float = 0.0
    gross_loss_points: float = 0.0
    avg_points_per_trade: float = 0.0