import datetime
from collections import defaultdict
from typing import List, Dict, Any
from interval_stats import IntervalStats
from trade_group import TradeGroup

class TradeAnalyzer:
    """
    Analyzes a list of TradeGroup objects to calculate statistics grouped by
    5-minute time-of-day intervals based on the entry time (ignores date).

    Args:
        trades (List[TradeGroup]): A list of TradeGroup dataclass objects.
    """
    
    # Updated type hint here
    def __init__(self, trades: List[TradeGroup]):
        if not isinstance(trades, list) or not all(isinstance(t, TradeGroup) for t in trades):
            raise TypeError("Input 'trades' must be a list of TradeGroup objects.")
        self.trades = trades
        # Potential Improvement: Consider handling timezones here if necessary
        # e.g., convert all trade.entry_time to UTC before analysis.

    # Modified to return datetime.time
    def _get_interval_start_time(self, dt: datetime.datetime) -> datetime.time:
        """Calculates the start of the 5-minute time interval for a given datetime."""
        interval_minute = (dt.minute // 5) * 5
        # Return only the time component
        return datetime.time(hour=dt.hour, minute=interval_minute, second=0)

    # Updated return type hint Dict[datetime.time, IntervalStats]
    def analyze_by_time_interval(self) -> Dict[datetime.time, IntervalStats]:
        """
        Performs the analysis, grouping TradeGroups by 5-minute time-of-day
        entry intervals (ignores date).

        Returns:
            Dict[datetime.time, IntervalStats]: A dictionary where keys are
                  datetime.time objects representing the start of each 5-minute
                  time interval, and values are IntervalStats objects containing
                  the aggregated statistics for that interval across all dates.
                  Returns an empty dictionary if no TradeGroups are provided.
                  Results are sorted by time.
        """
        # Accumulator keys are now datetime.time objects
        interval_accumulator = defaultdict(lambda: {
            'trade_points_list': [], 'count': 0, 'win_count': 0, 'loss_count': 0,
            'breakeven_count': 0, 'long_count': 0, 'short_count': 0,
            'gross_profit': 0.0, 'gross_loss': 0.0,
        })

        for trade in self.trades:
            try:
                # Use the new method to get the time-only interval key
                interval_key_time = self._get_interval_start_time(trade.entry_time)
                accumulator = interval_accumulator[interval_key_time]

                # --- Accumulation logic remains the same ---
                accumulator['trade_points_list'].append(trade.trade_point)
                accumulator['count'] += 1
                if trade.entry_is_long: accumulator['long_count'] += 1
                else: accumulator['short_count'] += 1
                if trade.trade_point > 0:
                    accumulator['win_count'] += 1; accumulator['gross_profit'] += trade.trade_point
                elif trade.trade_point < 0:
                    accumulator['loss_count'] += 1; accumulator['gross_loss'] += abs(trade.trade_point)
                else: accumulator['breakeven_count'] += 1
                # --- End Accumulation logic ---

            except Exception as e:
                print(f"Warning: Error processing TradeGroup entered at {trade.entry_time}. Error: {e}")
                continue

        # Results dictionary keys are datetime.time
        results: Dict[datetime.time, IntervalStats] = {}
        # Iterate through the time-based accumulator
        for interval_key_time, accumulator in interval_accumulator.items():
            total_trades = accumulator['count']; gross_profit = accumulator['gross_profit']; gross_loss = accumulator['gross_loss']
            win_rate = (accumulator['win_count'] / total_trades) if total_trades > 0 else 0.0
            if gross_loss > 0: profit_factor = gross_profit / gross_loss
            elif gross_profit > 0: profit_factor = float('inf')
            else: profit_factor = 0.0
            total_profit_loss_points = gross_profit - gross_loss
            avg_points = (total_profit_loss_points / total_trades) if total_trades > 0 else 0.0

            # Create IntervalStats with the datetime.time key
            stats = IntervalStats(
                interval_start_time=interval_key_time, # Use the time object
                total_trades=total_trades,
                winning_trades=accumulator['win_count'], losing_trades=accumulator['loss_count'],
                breakeven_trades=accumulator['breakeven_count'], long_trades=accumulator['long_count'],
                short_trades=accumulator['short_count'], win_rate=win_rate, profit_factor=profit_factor,
                total_profit_loss_points=total_profit_loss_points, gross_profit_points=gross_profit,
                gross_loss_points=gross_loss, avg_points_per_trade=avg_points)
            results[interval_key_time] = stats # Store using time key

        # Sort results by time of day (datetime.time keys are comparable)
        sorted_results = dict(sorted(results.items()))
        return sorted_results
    
    def print_table(self, interval_stats):
        print("\n--- TradeGroup Analysis by 5-Minute Time-of-Day Interval (All Dates Aggregated) ---")
        if not interval_stats:
            print("\nNo TradeGroups to analyze.")
        else:
            # Define column headers and widths (Adjust Interval width/header)
            headers = ["Time", "Count", "Win Rate", "Profit Factor", "Total Pts", "Avg Pts"]
            # Widths: Time(8), Count(7), WinRate(10), PF(15), TotalPts(11), AvgPts(10)
            widths = [ 8, 7, 10, 15, 11, 10 ]

            # Create header string with padding
            header_line = f"{headers[0]:<{widths[0]}} | {headers[1]:>{widths[1]}} | {headers[2]:>{widths[2]}} | {headers[3]:>{widths[3]}} | {headers[4]:>{widths[4]}} | {headers[5]:>{widths[5]}}"

            # Create separator line based on header length
            separator = '-' * len(header_line)

            # Print table header
            print(separator)
            print(header_line)
            print(separator)

            # Print data rows
            # Iterate through the values of the time-keyed dictionary
            for stats in interval_stats.values():
                # Format data for printing
                interval_str = stats.interval_start_time.strftime('%H:%M') # Format time only
                count_str = str(stats.total_trades)
                win_rate_str = f"{stats.win_rate:.1%}"
                pf_str = f"{stats.profit_factor:.2f}" if stats.profit_factor != float('inf') else "inf"
                total_points_str = f"{stats.total_profit_loss_points:.2f}"
                avg_points_str = f"{stats.avg_points_per_trade:.2f}"

                # Create data row string with padding
                data_line = f"{interval_str:<{widths[0]}} | {count_str:>{widths[1]}} | {win_rate_str:>{widths[2]}} | {pf_str:>{widths[3]}} | {total_points_str:>{widths[4]}} | {avg_points_str:>{widths[5]}}"
                print(data_line)

            # Print bottom separator
            print(separator)

# --- Example Usage ---
if __name__ == "__main__":
    # Create sample trades using the TradeGroup dataclass
    # Updated type hint and constructor calls here
    sample_trades_typed: List[TradeGroup] = [
        TradeGroup(entry_is_long=True, entry_time=datetime.datetime(2025, 4, 12, 9, 31, 15), exit_time=datetime.datetime(2025, 4, 12, 9, 35, 0), max_trade_size=2, trade_point=5.25),
        TradeGroup(entry_is_long=False, entry_time=datetime.datetime(2025, 4, 12, 9, 33, 40), exit_time=datetime.datetime(2025, 4, 12, 9, 38, 0), max_trade_size=1, trade_point=-2.75),
        TradeGroup(entry_is_long=True, entry_time=datetime.datetime(2025, 4, 12, 9, 34, 55), exit_time=datetime.datetime(2025, 4, 12, 9, 40, 0), max_trade_size=3, trade_point=8.00),
        TradeGroup(entry_is_long=True, entry_time=datetime.datetime(2025, 4, 12, 9, 38, 10), exit_time=datetime.datetime(2025, 4, 12, 9, 42, 0), max_trade_size=1, trade_point=1.50),
        TradeGroup(entry_is_long=False, entry_time=datetime.datetime(2025, 4, 12, 9, 41, 5), exit_time=datetime.datetime(2025, 4, 12, 9, 45, 0), max_trade_size=2, trade_point=-3.00),
        TradeGroup(entry_is_long=False, entry_time=datetime.datetime(2025, 4, 12, 9, 42, 30), exit_time=datetime.datetime(2025, 4, 12, 9, 48, 0), max_trade_size=1, trade_point=4.50),
        TradeGroup(entry_is_long=True, entry_time=datetime.datetime(2025, 4, 12, 9, 44, 0), exit_time=datetime.datetime(2025, 4, 12, 9, 49, 0), max_trade_size=2, trade_point=0.0), # Breakeven
    ]

    # Instantiate the analyzer with the list of TradeGroup objects
    analyzer = TradeAnalyzer(sample_trades_typed)

    # Perform the analysis
    interval_stats: Dict[datetime.datetime, IntervalStats] = analyzer.analyze_by_time_interval()

    analyzer.print_table(interval_stats)