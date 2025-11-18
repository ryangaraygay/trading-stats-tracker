
class MetricNames:
    TRADES = "Trades"
    OPEN_ENTRY = "Open Entry"
    OPEN_DURATION = "Open Duration"
    AVG_SIZE = "Avg Size"
    FIRST_ENTRY = "First Entry"
    LAST_EXIT = "Last Exit"
    INTERTRADE_AVG = "InterTrade Avg"
    INTERTRADE_MAX = "InterTrade Max"
    DURATION_AVG = "Duration Avg W/L"
    DURATION_MAX = "Duration Max W/L"
    AVG_ORDERS_PER_TRADE = "Avg Order per Trade"
    ORDERS_LONG_SHORT = "Orders L/S"
    CONTRACTS_LONG_SHORT = "Contracts L/S"
    SCALED_WINS = "Scaled Wins"
    MAX_WIN_SZE = "Max Win Size"
    LAST_UPDATED = "Last Updated"
    GAINS_LOSSES = "Gains/Losses"
    WIN_LOSS = "Win/Loss"
    AVG_GAIN_LOSS = "Avg Trade P/L"
    AVG_POINTS = "Avg Points"
    MAX_POINTS = "Max Points"
    PEAK_TIME_PNL = "Peak Time P/L"
    PEAK_PL = "Peak P/L"
    MAX_TRADE_PL = "Max Trade P/L"
    BEST_WORST = "Best/Worst"
    SCALED_LOSSES = "Scaled Losses"
    MAX_LOSS_SIZE = "Max Loss Size"
    WIN_RATE_LONG_SHORT = "Win Rate (L/S)"

    @staticmethod
    def get_extra_metric_names():
        return [
            MetricNames.AVG_SIZE,
            MetricNames.BEST_WORST,
            MetricNames.PEAK_PL,
            MetricNames.MAX_TRADE_PL,
            MetricNames.MAX_POINTS,
            MetricNames.SCALED_LOSSES,
            MetricNames.MAX_LOSS_SIZE,
            MetricNames.FIRST_ENTRY,
            MetricNames.LAST_EXIT,
            MetricNames.INTERTRADE_AVG,
            MetricNames.INTERTRADE_MAX,
            MetricNames.AVG_ORDERS_PER_TRADE,
            MetricNames.ORDERS_LONG_SHORT,
            MetricNames.CONTRACTS_LONG_SHORT,
            MetricNames.SCALED_WINS,
            MetricNames.MAX_WIN_SZE,
            MetricNames.LAST_UPDATED,
            MetricNames.WIN_LOSS,
            MetricNames.AVG_GAIN_LOSS,
            MetricNames.AVG_POINTS,
            MetricNames.PEAK_TIME_PNL,
            MetricNames.DURATION_AVG,
            MetricNames.DURATION_MAX
        ] # Define keys to exclude if extra metrics is unchecked.
