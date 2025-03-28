class Streak:
    def __init__(self):
        self.streak = 0
        self.best_streak = 0
        self.worst_streak = 0
        self.is_last_trade_win = False
        self.long_losses = 0
        self.short_losses = 0

    def process(self, is_win, is_long=True):
        """
        Processes a trade result and updates the streak.

        Args:
            is_win (bool): True if the trade was a win, False otherwise.
            is_long (bool): True if the trade was a long position, False otherwise.
        """
        if is_win:
            if self.is_last_trade_win:
                self.streak += 1
            else:
                self.streak = 1
            self.is_last_trade_win = True
            self.best_streak = max(self.best_streak, self.streak)
            self.long_losses = 0 #reset losses when a win occur
            self.short_losses = 0
        else:
            if not self.is_last_trade_win:
                self.streak -= 1
            else:
                self.streak = -1

            self.is_last_trade_win = False
            self.worst_streak = min(self.worst_streak, self.streak)
            if is_long:
                self.long_losses += 1
            else:
                self.short_losses += 1

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
            return f"100% Long"
        elif short_percentage == 100:
            return f"100% Short"
        else:
            if long_percentage > short_percentage:
                return f"{long_percentage:.0f}% Long"
            else:
                return f"{short_percentage:.0f}% Short"