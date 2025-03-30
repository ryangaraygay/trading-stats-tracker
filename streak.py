import datetime

class Streak:
    def __init__(self):
        self.streak = 0
        self.best_streak = 0
        self.worst_streak = 0
        self.is_last_trade_win = False
        self.long_losses = 0
        self.short_losses = 0
        self.streak_start_time = None
        self.streak_last_trade_time = None
        self.total_trade_size = 0  # Store total trade size during the streak
        self.max_trade_size = 0  # Track max trade size

    def process(self, is_win, is_long=True, trade_time=None, trade_size=1):
        """
        Processes a trade result and updates the streak.

        Args:
            is_win (bool): True if the trade was a win, False otherwise.
            is_long (bool): True if the trade was a long position, False otherwise.
            trade_time (datetime.timedelta): The time of the trade.
        """
        # print(f'streak {self.streak} is_win {is_win} trade_time {trade_time}')

        if self.streak == 0 and not is_win:
            self.streak_start_time = trade_time
            self.total_trade_size += trade_size
            self.max_trade_size = trade_size  # Initialize max trade size

        if is_win:
            if self.is_last_trade_win:
                self.streak += 1
            else:
                self.streak = 1
            self.is_last_trade_win = True
            self.best_streak = max(self.best_streak, self.streak)
            self.long_losses = 0
            self.short_losses = 0

            # reset streak frequency variables
            self.streak_start_time = None
            self.streak_last_trade_time = None
            self.total_trade_size = 0 #reset trade size
            self.max_trade_size = 0
        else:
            if not self.is_last_trade_win:
                self.streak -= 1
                self.streak_last_trade_time = trade_time
            else:
                self.streak = -1
                self.streak_start_time = trade_time

            self.total_trade_size += trade_size
            self.max_trade_size = max(self.max_trade_size, trade_size)
            self.is_last_trade_win = False
            self.worst_streak = min(self.worst_streak, self.streak)
            if is_long:
                self.long_losses += 1
            else:
                self.short_losses += 1

        # print(f'streak_start_time {self.streak_start_time} streak_last_trade_time {self.streak_last_trade_time}')

    def get_loss_mix(self):
        """
        Returns a string describing the composition of the losing streak.
        """
        if self.streak >= 0:
            return ""

        total_losses = abs(self.streak)
        long_percentage = (self.long_losses / total_losses) * 100
        short_percentage = (self.short_losses / total_losses) * 100

        if long_percentage == 100:
            return f"100% long"
        elif short_percentage == 100:
            return f"100% short"
        else:
            if long_percentage > short_percentage:
                return f"{long_percentage:.0f}% long"
            else:
                return f"{short_percentage:.0f}% short"

    def loss_trade_interval(self):
        """Calculates and returns the average time interval (in minutes) between trades during the streak."""
        if self.streak == 0 or self.streak_start_time is None or self.streak_last_trade_time is None:
            return 0.00

        elapsed_time_secs = (self.streak_last_trade_time - self.streak_start_time).total_seconds() / 60
        if abs(self.streak) == 0:
            return 0.00

        interval = elapsed_time_secs / abs(self.streak)
        return round(interval, 2)


    def get_avg_size_of_current_streak(self):
        """
        Calculates and returns the average trade size during the current streak.
        """
        if self.streak == 0 :
            return 0.00

        return self.total_trade_size / abs(self.streak)

    def get_max_size_of_current_streak(self):
        """
        Returns the maximum trade size encountered during the current streak.
        """
        return self.max_trade_size