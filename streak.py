class Streak:
    def __init__(self):
        self.streak = 0
        self.best_streak = 0
        self.worst_streak = 0
        self.is_last_trade_win = False

    def process(self, is_win):
        """
        Processes a trade result and updates the streak.

        Args:
            is_win (bool): True if the trade was a win, False otherwise.
        """
        if is_win:
            if self.is_last_trade_win:
                self.streak += 1
            else:
                self.streak = 1
            self.is_last_trade_win = True
            self.best_streak = max(self.best_streak, self.streak)
        else:
            if not self.is_last_trade_win:
                self.streak -= 1
            else:
                self.streak = -1

            self.is_last_trade_win = False
            self.worst_streak = min(self.worst_streak, self.streak)