import datetime
import my_utils

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
        self.losing_streak_stopper = []
        self.losing_streak_continuer = []

    def process(self, is_win, is_long=True, entry_time=None, exit_time=None, trade_size=1, trade_value=0):
        """
        Processes a trade result and updates the streak.

        Args:
            is_win (bool): True if the trade was a win, False otherwise.
            is_long (bool): True if the trade was a long position, False otherwise.
            entry_time (datetime.timedelta): The entry time of the trade.
            exit_time (datetime.timedelta): The exit time of the trade.
        """
        # print(f'streak {self.streak} is_win {is_win} entry_time {entry_time} exit_time {exit_time}')

        if self.streak == 0 and not is_win:
            self.streak_start_time = entry_time

        if is_win:
            if self.is_last_trade_win:
                self.streak += 1
            else:
                self.streak = 1
                if self.streak_last_trade_time is not None:
                    streak_stopper_time = (entry_time - self.streak_last_trade_time).total_seconds() 
                    self.losing_streak_stopper.append((streak_stopper_time, trade_value))

            self.is_last_trade_win = True
            self.best_streak = max(self.best_streak, self.streak)
            self.long_losses = 0
            self.short_losses = 0

            # reset streak frequency variables
            self.streak_start_time = None
            self.streak_last_trade_time = None
        else:
            if not self.is_last_trade_win:
                self.streak -= 1
                if self.streak_last_trade_time is not None:
                    streak_continuer_time = (entry_time - self.streak_last_trade_time).total_seconds() 
                    self.losing_streak_continuer.append((streak_continuer_time, trade_value))
                self.streak_last_trade_time = entry_time
            else:
                self.streak = -1
                self.streak_start_time = exit_time

            self.is_last_trade_win = False
            self.worst_streak = min(self.worst_streak, self.streak)
            if is_long:
                self.long_losses += 1
            else:
                self.short_losses += 1

        # print(f'streak_start_time {self.streak_start_time} streak_last_trade_time {self.streak_last_trade_time}')

    def get_extra_msg(self):
        if self.streak >= -1:
            return ""
        
        directional_bias = f'{self.get_loss_mix()} in {self.get_loss_elapsed_time_mins_str()}'
        
        total_losses = abs(self.streak)
        long_bias_perc = (self.long_losses / total_losses) * 100

        return "Join the SHORT." if long_bias_perc >= 90 else "Join the LONG." if long_bias_perc <= 10 else directional_bias

    def get_loss_mix(self):
        """
        Returns a string describing the composition of the losing streak.
        """
        if self.streak >= -1:
            return ""

        # note that there is some code duplication here and in get_extra_msg function
        # as well as why explicitly compute short losses instead of just total minus longs
        # this is intentional as a counter check
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

    def get_loss_elapsed_time_mins_str(self):
        if self.streak > -2 or self.streak_start_time is None or self.streak_last_trade_time is None:
            return ""
        
        elapsed_time = int((self.streak_last_trade_time - self.streak_start_time).total_seconds() / 60)
        return f'{elapsed_time} mins'