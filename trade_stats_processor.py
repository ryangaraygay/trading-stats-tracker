import datetime
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta

import my_utils

from alert_config_manager import AlertConfigManager, ConditionEvaluator
from alert_message import AlertMessage
from concern_level import ConcernLevel
from config import Config
from constants import CONST
from metrics_names import MetricNames
from trade import Trade
from trade_analyzer import TradeAnalyzer
from trade_group import TradeGroup
from streak import Streak

LOGGER = logging.getLogger(__name__)


class TradeStatsProcessor:

    def __init__(self, config: Config):
        self.config = config
        self.account_trading_stats = {}
        self.account_trading_alerts = {}
        self.account_names_loaded = list()
        self.streak_stopper_list = []
        self.streak_continuer_list = []
        self.account_trade_groups = {}
        self.alert_profile_status = {
            "mode": "fallback",
            "profile": "legacy",
            "source": "hardcoded",
            "path": None,
            "error": None,
        }
        self.alert_config_manager = self._initialize_alert_config_manager()

    def _initialize_alert_config_manager(self):
        try:
            manager = AlertConfigManager()
            config = manager.load_config()
            active_profile = manager.get_active_profile_name()
            profile_path = manager.get_profile_path(active_profile)
            metadata = config.get("metadata", {})
            self.alert_profile_status = {
                "mode": "json",
                "profile": active_profile,
                "source": metadata.get("source", "unknown"),
                "path": str(profile_path) if profile_path else None,
                "error": None,
            }
            return manager
        except Exception as exc:
            LOGGER.warning("Alert config manager unavailable: %s", exc)
            self.alert_profile_status = {
                "mode": "fallback",
                "profile": "legacy",
                "source": "hardcoded",
                "path": None,
                "error": str(exc),
            }
            return None

    def load_account_names(self, file_paths):
        account_names = set()
        pattern = r"ACCOUNT:\s*(\S+)\s+fcmId:"
        for file_path in file_paths:
            with open(file_path, "r") as file:
                for line in file:
                    match = re.search(pattern, line)
                    if match:
                        account_name = match.group(1)
                        account_names.add(account_name)
        account_names.add("simulated")
        account_names.add(CONST.SELECT_ACCOUNT)
        account_names.add(CONST.ALL_ACCOUNTS)
        self.account_names_loaded = sorted(list(account_names))

    def get_fills(self, file_paths):
        unique_trades_dict = {}
        for file_path in file_paths:
            pattern = rf"OrderDirectory::orderFilled\(\) order: ID: (\S+) (\S+) (\S+)\.CME.*(Filled BUY|Filled SELL).*Qty:(\d+\.\d+).*Last Fill Time:\s*(\d{{2}}/\d{{2}}/\d{{4}} \d{{1,2}}:\d{{2}} [AP]M).*fill price: (\d+\.\d+)"
            with open(file_path, "r") as file:
                for line in file:
                    match = re.search(pattern, line)
                    if match:
                        order_id = int(
                            re.sub(r"[^0-9]", "", match.group(1))
                        )  # SIM-dd (we need this for ordering since fill_time has no second value and so inaccurate)
                        account_name = match.group(2)
                        contract_symbol = match.group(3)
                        order_type = match.group(4)
                        quantity = float(match.group(5))
                        fill_time_str = match.group(6)
                        fill_price = float(match.group(7))
                        fill_time = datetime.strptime(
                            fill_time_str, "%m/%d/%Y %I:%M %p"
                        )
                        unique_trades_dict[account_name, order_id] = Trade(
                            account_name,
                            order_id,
                            order_type,
                            contract_symbol,
                            quantity,
                            fill_price,
                            fill_time,
                        )

        fill_data = list(unique_trades_dict.values())
        if len(fill_data) == 0:
            print("No Fills Found")

        return fill_data

    def compute_trade_stats(self, fill_data):
        account_names_with_fills = set()
        trade_groups_consolidated = []
        if fill_data:
            # get list of AccountNames in fill
            for item in fill_data:
                account_names_with_fills.add(item.account_name)

            # test specific accounts only
            # account_names_with_fills.clear()
            # account_names_with_fills.add("simulated")

            self.streak_stopper_list.clear()
            self.streak_continuer_list.clear()

            for account_name in account_names_with_fills:
                filtered_list = my_utils.filter_namedtuples(
                    fill_data, "account_name", account_name
                )

                trading_stats, alert_context, trade_groups = self.get_stats(
                    filtered_list
                )

                self.account_trading_stats[account_name] = trading_stats

                alert_matches = self._evaluate_alerts(alert_context)
                self.account_trading_alerts[account_name] = self._build_alert_messages(
                    account_name, alert_matches
                )

                self.account_trade_groups[account_name] = trade_groups

                trade_groups_consolidated.extend(trade_groups)

            if self.config.print_streak_followtrade_stats:
                self.print_streak_followtrade_statistics(
                    "streak_stopper_list", self.streak_stopper_list
                )
                self.print_streak_followtrade_statistics(
                    "streak_continuer_list", self.streak_continuer_list
                )

            if self.config.interval_stats_print:
                analyzer = TradeAnalyzer(trade_groups_consolidated)
                interval_stats = analyzer.analyze_by_time_interval(
                    self.config.interval_stats_min
                )
                analyzer.print_table(interval_stats)

            self.compute_all_account_stats(fill_data)
        else:
            self.account_trading_stats.clear()
            self.account_trading_alerts.clear()

        account_names_no_fills = [
            item
            for item in self.account_names_loaded
            if item not in self.account_trading_stats.keys()
        ]
        for no_fill_account in account_names_no_fills:
            self.account_trading_stats[no_fill_account] = [
                {"Trades": [f"0"]},
                {
                    "Last Updated": [
                        f"{datetime.now().strftime(CONST.DATE_TIME_FORMAT)}"
                    ]
                },
            ]

    def get_stats(self, filtered_list):
        sorted_fill = sorted(
            filtered_list, key=lambda record: record.order_id, reverse=False
        )  # keeping only digits for SIM-ID orders

        trade_groups = []
        grouped_trades = defaultdict(list)
        completed_trades = 0
        total_long_trades = 0
        total_buys = 0
        total_buy_contracts = 0
        total_short_trades = 0
        total_sells = 0
        total_sell_contracts = 0
        total_profit_or_loss = 0.0
        total_winning_trades = 0
        total_wins_long = 0
        gains = defaultdict(list)
        losses = defaultdict(list)
        max_realized_drawdown = 0
        max_realized_profit = 0
        loss_max_size = 0
        win_max_size = 0
        loss_points = []
        win_points = []
        loss_scaled_count = 0  # losses that involved multiple entries
        win_scaled_count = 0  # wins that involved multiple entries

        streak_tracker = Streak()
        max_time = datetime.min
        last_exit_time = datetime.max
        loss_duration = list()
        win_duration = list()
        entry_is_long = True
        time_between_trades = list()
        entry_time = datetime.max
        first_entry_time = datetime.max

        max_realized_drawdown_time = datetime.max
        max_realized_profit_time = datetime.max

        for fill in sorted_fill:
            if len(grouped_trades) == 0:
                entry_is_long = "BUY" in fill.order_type
                entry_time = fill.fill_time
                first_entry_time = min(first_entry_time, entry_time)
                if completed_trades > 0:  # start only when there is at least one
                    duration_since_last_trade = entry_time - last_exit_time
                    time_between_trades.append(duration_since_last_trade)

            grouped_trades[fill.order_type].append(fill)

            if "BUY" in fill.order_type:
                total_buys += 1
                total_buy_contracts += int(fill.quantity)
            else:
                total_sells += 1
                total_sell_contracts += int(fill.quantity)

            buy_total_value = 0
            buy_qty = 0
            sell_total_value = 0
            sell_qty = 0

            for trade in grouped_trades["Filled BUY"]:
                buy_qty += trade.quantity
                buy_total_value += trade.quantity * trade.fill_price
                max_time = max(max_time, trade.fill_time)

            for trade in grouped_trades["Filled SELL"]:
                sell_qty += trade.quantity
                sell_total_value += trade.quantity * trade.fill_price
                max_time = max(max_time, trade.fill_time)

            position_size = buy_qty - sell_qty
            if len(grouped_trades) >= 2 and position_size == 0:  # trade completed
                completed_trades += 1
                contract_value = self.config.get_contract_value(fill.contract_symbol)
                completed_profit_loss = (
                    sell_total_value - buy_total_value
                ) * contract_value
                total_profit_or_loss += completed_profit_loss
                is_win = completed_profit_loss > 0
                total_winning_trades += is_win
                total_wins_long += 1 if (is_win and entry_is_long) else 0

                last_exit_time = max_time
                duration = last_exit_time - entry_time
                if total_profit_or_loss < max_realized_drawdown:
                    max_realized_drawdown = total_profit_or_loss
                    max_realized_drawdown_time = last_exit_time
                if total_profit_or_loss > max_realized_profit:
                    max_realized_profit = total_profit_or_loss
                    max_realized_profit_time = last_exit_time

                trade_size = self.calculate_max_quantity(grouped_trades)
                trade_points = completed_profit_loss / (trade_size * contract_value)
                entries_in_trade_count = len(
                    grouped_trades["Filled BUY" if entry_is_long else "Filled SELL"]
                )

                if not is_win:
                    loss_max_size = max(loss_max_size, trade_size)
                    losses[entry_is_long].append(completed_profit_loss)
                    loss_points.append(trade_points)
                    loss_duration.append(duration)
                    loss_scaled_count += 1 if entries_in_trade_count > 1 else 0
                else:
                    win_max_size = max(win_max_size, trade_size)
                    gains[entry_is_long].append(completed_profit_loss)
                    win_points.append(trade_points)
                    win_duration.append(duration)
                    win_scaled_count += 1 if entries_in_trade_count > 1 else 0

                total_long_trades += 1 if entry_is_long else 0
                total_short_trades += 1 if not entry_is_long else 0

                streak_tracker.process(
                    is_win,
                    entry_is_long,
                    entry_time,
                    last_exit_time,
                    trade_size,
                    trade_points,
                )
                trade_groups.append(
                    TradeGroup(
                        entry_is_long,
                        entry_time,
                        last_exit_time,
                        trade_size,
                        trade_points,
                        completed_profit_loss,
                    )
                )

                grouped_trades.clear()
                max_time = datetime.min
                entry_time = datetime.max

        get_sum = lambda data: sum(data) if data else 0
        get_average = lambda data: sum(data) / len(data) if data else 0
        get_max = lambda data: max(data) if data else 0
        get_min = lambda data: min(data) if data else 0

        self.streak_stopper_list.extend(streak_tracker.losing_streak_stopper)
        self.streak_continuer_list.extend(streak_tracker.losing_streak_continuer)

        all_gains = gains[True] + gains[False]
        all_losses = losses[True] + losses[False]

        total_gains = get_sum(all_gains)
        total_losses = get_sum(all_losses)

        win_rate = (
            50
            if completed_trades == 0
            else total_winning_trades / completed_trades * 100
        )
        long_win_rate = (
            0 if total_long_trades == 0 else total_wins_long / total_long_trades * 100
        )
        short_win_rate = (
            0
            if total_short_trades == 0
            else (total_winning_trades - total_wins_long) / total_short_trades * 100
        )
        profit_factor = 1 if total_losses == 0 else total_gains / abs(total_losses)

        long_gains = get_sum(gains[True])
        long_losses = get_sum(losses[True])
        short_gains = get_sum(gains[False])
        short_losses = get_sum(losses[False])
        long_profit_factor = 1 if long_losses == 0 else long_gains / abs(long_losses)
        short_profit_factor = (
            1 if short_losses == 0 else short_gains / abs(short_losses)
        )

        loss_avg_secs = my_utils.average_timedelta(loss_duration)
        loss_max_secs = my_utils.max_timedelta(loss_duration)
        win_avg_secs = my_utils.average_timedelta(win_duration)
        win_max_secs = my_utils.max_timedelta(win_duration)
        time_between_trades_avg_secs = my_utils.average_timedelta(time_between_trades)
        time_between_trades_max_secs = my_utils.max_timedelta(time_between_trades)
        current_drawdown = -1 * int(max_realized_profit - total_profit_or_loss)

        avg_gain = get_average(all_gains)
        avg_loss = get_average(all_losses)
        total_losing_trades = completed_trades - total_winning_trades
        win_max_value = get_max(all_gains)
        loss_max_value = get_min(all_losses)

        loss_max_points = get_min(loss_points)
        win_max_points = get_max(win_points)
        loss_avg_points = get_average(loss_points)
        win_avg_points = get_average(win_points)
        total_points = get_sum(win_points) + get_sum(loss_points)

        directional_bias = ""
        long_bias_percentage = (
            0 if completed_trades == 0 else (total_long_trades / completed_trades) * 100
        )
        short_bias_percentage = (
            0
            if completed_trades == 0
            else (total_short_trades / completed_trades) * 100
        )

        if long_bias_percentage == 100:
            directional_bias = f"100% long."
        elif short_bias_percentage == 100:
            directional_bias = f"100% short."
        else:
            if long_bias_percentage > short_bias_percentage:
                directional_bias = f"{long_bias_percentage:.0f}% long"
            else:
                directional_bias = f"{short_bias_percentage:.0f}% short"

        directional_bias_extramsg = (
            "Join the SHORT."
            if long_bias_percentage >= 90
            else "Join the LONG." if long_bias_percentage <= 10 else directional_bias
        )

        trade_conditions = [
            {
                "expr": lambda x: x >= 30,
                "level": ConcernLevel.CRITICAL,
                "msg": "Stop. Maximum trades for the day reached.",
            },
            {
                "expr": lambda x: x >= 20 and total_profit_or_loss > 0,
                "level": ConcernLevel.OK,
                "msg": "Wind down. You've reached your trade count goal.",
            },
            {
                "expr": lambda x: x >= 20,
                "level": ConcernLevel.WARNING,
                "msg": "Wind down. You've reached your trade count goal.",
            },
            {
                "expr": lambda x: x >= 10,
                "level": ConcernLevel.CAUTION,
                "msg": "Slow down. Take quality trades only.",
            },
        ]

        pnl_conditions = [
            {
                "expr": lambda x: x < -2100,
                "level": ConcernLevel.CRITICAL,
                "msg": "Stop. Protect your capital.",
            },
            {
                "expr": lambda x: x < -1400,
                "level": ConcernLevel.WARNING,
                "msg": "Pause. Reset first, then recover.",
            },
            {
                "expr": lambda x: x < -700,
                "level": ConcernLevel.CAUTION,
                "msg": "Slow down. Manage loss by managing risk.",
            },
            {
                "expr": lambda x: x >= 1000,
                "level": ConcernLevel.OK,
                "msg": "Wind down. Protect gains.",
            },
        ]

        winrate_conditions = [
            {
                "expr": lambda x: x <= 25
                and profit_factor < 1.0
                and completed_trades >= 10,
                "level": ConcernLevel.WARNING,
                "msg": "Reset. Win Rate very low.",
            },
            {
                "expr": lambda x: x <= 40
                and profit_factor < 1.5
                and completed_trades >= 5,
                "level": ConcernLevel.CAUTION,
                "msg": "Slow down. Win Rate low.",
            },
        ]

        profitfactor_conditions = [
            {
                "expr": lambda x: x < 1.0 and completed_trades >= 10,
                "level": ConcernLevel.WARNING,
                "msg": "Reset. Profit Factor very low.",
            },
            {
                "expr": lambda x: x < 1.5 and completed_trades >= 5,
                "level": ConcernLevel.CAUTION,
                "msg": "Slow down. Profit Factor low.",
            },
            {"expr": lambda x: x >= 1.5, "level": ConcernLevel.OK, "msg": ""},
        ]

        losingstreak_conditions = [
            {
                "expr": lambda x: x <= -7,
                "level": ConcernLevel.CRITICAL,
                "msg": "Stop Now. Protect the version of YOU that will trade well tomorrow.",
            },
            {
                "expr": lambda x: x <= -4,
                "level": ConcernLevel.WARNING,
                "msg": "Stop. Follow Reset plan.",
            },
            {
                "expr": lambda x: x <= -2,
                "level": ConcernLevel.CAUTION,
                "msg": f"Slow down. Consecutive losses. {streak_tracker.get_extra_msg()}",
            },
        ]

        loss_max_size_conditions = [
            {
                "expr": lambda x: x >= 10,
                "level": ConcernLevel.WARNING,
                "msg": "Reset. Size down.",
            },
            {
                "expr": lambda x: x >= 6,
                "level": ConcernLevel.CAUTION,
                "msg": "Size down.",
            },
            {
                "expr": lambda x: x >= 4
                and profit_factor < 1.0
                and completed_trades >= 3,
                "level": ConcernLevel.CAUTION,
                "msg": "Size down.",
            },
        ]

        loss_scaled_count_conditions = [
            {
                "expr": lambda x: x >= 5,
                "level": ConcernLevel.WARNING,
                "msg": "Reset. Scale up winners only.",
            },
            {
                "expr": lambda x: x >= 3,
                "level": ConcernLevel.CAUTION,
                "msg": "Scale up winners only.",
            },
        ]

        drawdown_conditions = [
            {
                "expr": lambda x: x < -3000,
                "level": ConcernLevel.CRITICAL,
                "msg": "Stop Now. Maximum drawdown.",
            },
            {
                "expr": lambda x: x < -2000,
                "level": ConcernLevel.WARNING,
                "msg": "Reset. Large drawdown.",
            },
            {
                "expr": lambda x: x < -1000,
                "level": ConcernLevel.CAUTION,
                "msg": "Slow down. Notable drawdown.",
            },
        ]

        winrate_color, _, _, _ = self.evaluate_conditions(win_rate, winrate_conditions)
        overtrade_color, _, _, _ = self.evaluate_conditions(
            completed_trades, trade_conditions
        )
        pnl_color, _, _, _ = self.evaluate_conditions(
            total_profit_or_loss, pnl_conditions
        )
        profitfactor_color, _, _, _ = self.evaluate_conditions(
            profit_factor, profitfactor_conditions
        )
        losing_streak_color, _, _, _ = self.evaluate_conditions(
            streak_tracker.streak, losingstreak_conditions
        )
        loss_max_size_color, _, _, _ = self.evaluate_conditions(
            loss_max_size, loss_max_size_conditions
        )
        loss_scaled_count_color, _, _, _ = self.evaluate_conditions(
            loss_scaled_count, loss_scaled_count_conditions
        )
        drawdown_color, _, _, _ = self.evaluate_conditions(
            current_drawdown, drawdown_conditions
        )

        open_size_color = (
            ConcernLevel.CAUTION if abs(position_size) >= 3 else ConcernLevel.DEFAULT
        ).get_color()
        avg_duration_color = (
            ConcernLevel.WARNING
            if win_avg_secs < loss_avg_secs
            else ConcernLevel.DEFAULT
        ).get_color()
        max_duration_color = (
            ConcernLevel.WARNING
            if win_max_secs < loss_max_secs
            else ConcernLevel.DEFAULT
        ).get_color()
        intertrade_time_avg_color = (
            ConcernLevel.WARNING
            if time_between_trades_avg_secs < timedelta(seconds=60)
            else ConcernLevel.DEFAULT
        ).get_color()
        win_scaled_count_color = (
            ConcernLevel.OK if win_scaled_count >= 2 else ConcernLevel.DEFAULT
        ).get_color()
        total_points_color = (
            ConcernLevel.OK if total_points > 0 else ConcernLevel.WARNING
        ).get_color()

        open_entry_time_i = (
            entry_time.strftime(CONST.DAY_TIME_FORMAT) if position_size != 0 else ""
        )
        open_entry_duration = my_utils.calculate_mins(open_entry_time_i, datetime.now())
        open_entry_duration_str = (
            "" if open_entry_duration == 0 else open_entry_duration
        )

        avg_orders_per_trade = (
            0
            if completed_trades == 0
            else (total_buys + total_sells) / (completed_trades * 2)
        )

        peak_profit_time = (
            max_realized_profit_time.strftime(CONST.DAY_TIME_FORMAT)
            if max_realized_profit_time != datetime.max
            else "N/A"
        )
        peak_drawdown_time = (
            max_realized_drawdown_time.strftime(CONST.DAY_TIME_FORMAT)
            if max_realized_drawdown_time != datetime.max
            else "N/A"
        )

        trading_stats = [
            {MetricNames.TRADES: [f"{completed_trades}", overtrade_color]},
            {"Bias": [f"{directional_bias}"]},
            {"": [""]},
            {"Win Rate": [f"{win_rate:.0f}%", winrate_color]},
            {
                MetricNames.WIN_RATE_LONG_SHORT: [
                    f"{long_win_rate:.0f}% / {short_win_rate:.0f}%"
                ]
            },
            {"": [""]},
            {
                "Consecutive W/L": [
                    f"{streak_tracker.streak:+}",
                    losing_streak_color,
                ]
            },
            {"Mix": [f"{streak_tracker.get_loss_mix()}"]},
            {"Duration": [f"{streak_tracker.get_loss_elapsed_time_mins_str()}"]},
            {
                MetricNames.BEST_WORST: [
                    f"{streak_tracker.best_streak:+} / {streak_tracker.worst_streak:+}"
                ]
            },
            {"": [""]},
            {"Profit Factor": [f"{profit_factor:.01f}", profitfactor_color]},
            {
                "Profit Factor L/S": [
                    f"{long_profit_factor:.1f} / {short_profit_factor:.1f}"
                ]
            },
            {"": [""]},
            {"Total Points": [f"{total_points:.02f}", total_points_color]},
            {
                MetricNames.GAINS_LOSSES: [
                    f"{int(total_gains):+,} / {int(total_losses):+,}"
                ]
            },
            {"Profit/Loss": [f"{int(total_profit_or_loss):+,}", pnl_color]},
            {"Drawdown": [f"{int(current_drawdown):+,}", drawdown_color]},
            {
                MetricNames.PEAK_PL: [
                    f"{int(max_realized_profit):+,} / {int(max_realized_drawdown):+,}"
                ]
            },
            {MetricNames.PEAK_TIME_PNL: [f"{peak_profit_time} | {peak_drawdown_time}"]},
            {MetricNames.AVG_GAIN_LOSS: [f"{int(avg_gain):+,} / {int(avg_loss):+,}"]},
            {MetricNames.MAX_TRADE_PL: [f"{int(win_max_value):+,} / {int(loss_max_value):+,}"]},
            {
                MetricNames.AVG_POINTS: [
                    f"{int(win_avg_points):+,} / {int(loss_avg_points):+,}"
                ]
            },
            {
                MetricNames.MAX_POINTS: [
                    f"{int(win_max_points):+,} / {int(loss_max_points):+,}"
                ]
            },
            {"": [""]},
            {
                MetricNames.SCALED_LOSSES: [
                    f"{int(loss_scaled_count):,}",
                    loss_scaled_count_color,
                ]
            },
            {
                MetricNames.MAX_LOSS_SIZE: [
                    f"{int(loss_max_size)}",
                    loss_max_size_color,
                ]
            },
            {"": [""]},
            {"Open Size": [f"{int(position_size)}", open_size_color]},
            {MetricNames.OPEN_DURATION: [f"{open_entry_duration_str}"]},
            {MetricNames.OPEN_ENTRY: [f"{open_entry_time_i}"]},
            {
                MetricNames.FIRST_ENTRY: [
                    f"{first_entry_time.strftime(CONST.DAY_TIME_FORMAT)}"
                ]
            },
            {
                MetricNames.LAST_EXIT: [
                    f"{last_exit_time.strftime(CONST.DAY_TIME_FORMAT)}"
                ]
            },
            {"": [""]},
            {
                MetricNames.INTERTRADE_AVG: [
                    f"{my_utils.format_timedelta(time_between_trades_avg_secs)}",
                    intertrade_time_avg_color,
                ]
            },
            {
                MetricNames.INTERTRADE_MAX: [
                    f"{my_utils.format_timedelta(time_between_trades_max_secs)}"
                ]
            },
            {
                MetricNames.DURATION_AVG: [
                    f"{my_utils.format_timedelta(win_avg_secs)} / {my_utils.format_timedelta(loss_avg_secs)}",
                    avg_duration_color,
                ]
            },
            {
                MetricNames.DURATION_MAX: [
                    f"{my_utils.format_timedelta(win_max_secs)} / {my_utils.format_timedelta(loss_max_secs)}",
                    max_duration_color,
                ]
            },
            {MetricNames.AVG_ORDERS_PER_TRADE: [f"{avg_orders_per_trade:.01f}"]},
            {MetricNames.ORDERS_LONG_SHORT: [f"{total_buys} / {total_sells}"]},
            {
                MetricNames.CONTRACTS_LONG_SHORT: [
                    f"{total_buy_contracts} / {total_sell_contracts}"
                ]
            },
            {
                MetricNames.SCALED_WINS: [
                    f"{int(win_scaled_count):,}",
                    win_scaled_count_color,
                ]
            },
            {MetricNames.MAX_WIN_SZE: [f"{int(win_max_size)}"]},
            {
                MetricNames.LAST_UPDATED: [
                    f"{datetime.now().strftime(CONST.DAY_TIME_FORMAT)}"
                ]
            },
        ]

        win_avg_secs_seconds = win_avg_secs.total_seconds()
        loss_avg_secs_seconds = loss_avg_secs.total_seconds()
        duration_ratio = (
            win_avg_secs_seconds / loss_avg_secs_seconds
            if loss_avg_secs_seconds > 0
            else float("inf")
        )

        alert_context = {
            "completed_trades": completed_trades,
            "total_profit_or_loss": total_profit_or_loss,
            "profit_factor": profit_factor,
            "win_rate": win_rate,
            "directional_bias": directional_bias,
            "directional_bias_extramsg": directional_bias_extramsg,
            "streak_tracker": streak_tracker,
            "streak_tracker.streak": streak_tracker.streak,
            "loss_max_size": loss_max_size,
            "loss_scaled_count": loss_scaled_count,
            "current_drawdown": current_drawdown,
            "open_position_size": abs(total_buy_contracts - total_sell_contracts),
            "win_avg_secs_seconds": win_avg_secs_seconds,
            "loss_avg_secs_seconds": loss_avg_secs_seconds,
            "win_avg_secs_vs_loss_avg_secs": duration_ratio,
        }

        return trading_stats, alert_context, trade_groups

    def compute_all_account_stats(self, fill_data):
        # for analysis only so we don't need alerts
        # although some metrics are additive/derivable from collection of individual account stats
        # there are some that are not (e.g. streak) - although they can be handled, choosing to simply for now
        # and just recompute for unfiltered fill data
        if fill_data:
            trading_stats, alert_context, trade_groups = self.get_stats(fill_data)
            self.account_trading_stats[CONST.ALL_ACCOUNTS] = trading_stats
            self.account_trade_groups[CONST.ALL_ACCOUNTS] = trade_groups
            self.account_trading_alerts[CONST.ALL_ACCOUNTS] = (
                self._build_alert_messages(
                    CONST.ALL_ACCOUNTS, self._evaluate_alerts(alert_context)
                )
            )

    def _evaluate_alerts(self, context: dict):
        if self.alert_config_manager:
            try:
                config = self.alert_config_manager.get_active_config()
                evaluator = ConditionEvaluator(config)
                template_context = self._build_template_context(context)
                formatted_results = []
                for match in evaluator.evaluate(context):
                    formatted_results.append(
                        {
                            **match,
                            "message": self._format_template(
                                match.get("message", ""), template_context
                            ),
                            "extra_message": self._format_template(
                                match.get("extra_message", ""), template_context
                            ),
                        }
                    )
                return formatted_results
            except Exception as exc:
                LOGGER.warning("Custom alert evaluation failed: %s", exc)
        return self._legacy_alerts(context)

    def _build_template_context(self, context: dict) -> dict:
        safe_context = {}
        for key, value in context.items():
            if isinstance(value, (int, float, str)):
                safe_context[key] = value
        return safe_context

    def _format_template(self, template: str, context: dict) -> str:
        if not template:
            return template

        class SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"

        safe_map = SafeDict(context)
        try:
            return template.format_map(safe_map)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to format template '%s': %s", template, exc)
            return template

    def _build_alert_messages(self, account_name: str, matches) -> list:
        alerts = []
        for match in matches:
            message = match.get("message", "")
            level = match.get("level", ConcernLevel.DEFAULT)
            extra = match.get("extra_message", "")
            if not message:
                continue
            alerts.append(
                AlertMessage(
                    message,
                    account_name,
                    self.config.get_alert_duration(level),
                    self.config.get_min_interval_secs(level),
                    level,
                    extra,
                )
            )
        return sorted(alerts, key=lambda alert: alert.level, reverse=True)

    def get_alert_profile_status(self):
        return self.alert_profile_status

    def _legacy_alerts(self, context: dict):
        completed_trades = context.get("completed_trades", 0)
        total_profit_or_loss = context.get("total_profit_or_loss", 0)
        profit_factor = context.get("profit_factor", 1)
        win_rate = context.get("win_rate", 0)
        loss_scaled_count = context.get("loss_scaled_count", 0)
        loss_max_size = context.get("loss_max_size", 0)
        current_drawdown = context.get("current_drawdown", 0)
        directional_bias_extramsg = context.get("directional_bias_extramsg", "")
        streak_tracker = context.get("streak_tracker")

        alert_extramsg_default = ""

        trade_conditions = [
            {
                "expr": lambda x: x >= 30,
                "level": ConcernLevel.CRITICAL,
                "msg": "Stop. Maximum trades for the day reached.",
                "extra_msg": f"{completed_trades}",
            },
            {
                "expr": lambda x: x >= 20 and total_profit_or_loss > 0,
                "level": ConcernLevel.OK,
                "msg": "Wind down. You've reached your trade count goal.",
                "extra_msg": f"{completed_trades}",
            },
            {
                "expr": lambda x: x >= 20,
                "level": ConcernLevel.WARNING,
                "msg": "Wind down. You've reached your trade count goal.",
                "extra_msg": f"{completed_trades}",
            },
            {
                "expr": lambda x: x >= 10,
                "level": ConcernLevel.CAUTION,
                "msg": "Slow down. Take quality trades only.",
                "extra_msg": f"{completed_trades}",
            },
        ]

        pnl_conditions = [
            {
                "expr": lambda x: x < -2100,
                "level": ConcernLevel.CRITICAL,
                "msg": "Stop. Protect your capital.",
                "extra_msg": f"{int(total_profit_or_loss):+,}",
            },
            {
                "expr": lambda x: x < -1400,
                "level": ConcernLevel.WARNING,
                "msg": "Pause. Reset first, then recover.",
                "extra_msg": f"{int(total_profit_or_loss):+,}",
            },
            {
                "expr": lambda x: x < -700,
                "level": ConcernLevel.CAUTION,
                "msg": "Slow down. Manage loss by managing risk.",
                "extra_msg": f"{int(total_profit_or_loss):+,}",
            },
            {
                "expr": lambda x: x >= 1000,
                "level": ConcernLevel.OK,
                "msg": "Wind down. Protect gains.",
                "extra_msg": f"{int(total_profit_or_loss):+,}",
            },
        ]

        winrate_conditions = [
            {
                "expr": lambda x: x <= 25
                and profit_factor < 1.0
                and completed_trades >= 10,
                "level": ConcernLevel.WARNING,
                "msg": "Reset. Win Rate very low.",
                "extra_msg": f"{directional_bias_extramsg}",
            },
            {
                "expr": lambda x: x <= 40
                and profit_factor < 1.5
                and completed_trades >= 5,
                "level": ConcernLevel.CAUTION,
                "msg": "Slow down. Win Rate low.",
                "extra_msg": f"{directional_bias_extramsg}",
            },
        ]

        profitfactor_conditions = [
            {
                "expr": lambda x: x < 1.0 and completed_trades >= 10,
                "level": ConcernLevel.WARNING,
                "msg": "Reset. Profit Factor very low.",
                "extra_msg": f"{directional_bias_extramsg}",
            },
            {
                "expr": lambda x: x < 1.5 and completed_trades >= 5,
                "level": ConcernLevel.CAUTION,
                "msg": "Slow down. Profit Factor low.",
                "extra_msg": f"{directional_bias_extramsg}",
            },
            {"expr": lambda x: x >= 1.5, "level": ConcernLevel.OK, "msg": ""},
        ]

        losingstreak_conditions = [
            {
                "expr": lambda x: x <= -7,
                "level": ConcernLevel.CRITICAL,
                "msg": f"Stop Now. Protect the version of YOU that will trade well tomorrow.",
            },
            {
                "expr": lambda x: x <= -4,
                "level": ConcernLevel.WARNING,
                "msg": f"Stop. Follow Reset plan.",
            },
            {
                "expr": lambda x: x <= -2,
                "level": ConcernLevel.CAUTION,
                "msg": f"Slow down. Consecutive losses. {streak_tracker.get_extra_msg() if streak_tracker else ''}",
            },
        ]

        loss_max_size_conditions = [
            {
                "expr": lambda x: x >= 10,
                "level": ConcernLevel.WARNING,
                "msg": "Reset. Size down.",
            },
            {
                "expr": lambda x: x >= 6,
                "level": ConcernLevel.CAUTION,
                "msg": "Size down.",
            },
            {
                "expr": lambda x: x >= 4
                and profit_factor < 1.0
                and completed_trades >= 3,
                "level": ConcernLevel.CAUTION,
                "msg": "Size down.",
            },
        ]

        loss_scaled_count_conditions = [
            {
                "expr": lambda x: x >= 5,
                "level": ConcernLevel.WARNING,
                "msg": "Reset. Scale up winners only.",
            },
            {
                "expr": lambda x: x >= 3,
                "level": ConcernLevel.CAUTION,
                "msg": "Scale up winners only.",
            },
        ]

        drawdown_conditions = [
            {
                "expr": lambda x: x < -3000,
                "level": ConcernLevel.CRITICAL,
                "msg": "Stop Now. Maximum drawdown.",
                "extra_msg": f"{current_drawdown:+,}",
            },
            {
                "expr": lambda x: x < -2000,
                "level": ConcernLevel.WARNING,
                "msg": "Reset. Large drawdown.",
                "extra_msg": f"{current_drawdown:+,}",
            },
            {
                "expr": lambda x: x < -1000,
                "level": ConcernLevel.CAUTION,
                "msg": "Slow down. Notable drawdown.",
                "extra_msg": f"{current_drawdown:+,}",
            },
        ]

        _, winrate_msg, winrate_level, winrate_extramsg = self.evaluate_conditions(
            win_rate, winrate_conditions
        )
        _, overtrade_msg, overtrade_level, overtrade_extramsg = (
            self.evaluate_conditions(completed_trades, trade_conditions)
        )
        _, pnl_msg, pnl_level, pnl_extramsg = self.evaluate_conditions(
            total_profit_or_loss, pnl_conditions
        )
        _, profitfactor_msg, profitfactor_level, profitfactor_extramsg = (
            self.evaluate_conditions(profit_factor, profitfactor_conditions)
        )
        _, losing_streak_msg, losingstreak_level, _ = self.evaluate_conditions(
            streak_tracker.streak if streak_tracker else 0, losingstreak_conditions
        )
        _, loss_max_size_msg, loss_max_size_level, loss_max_size_extramsg = (
            self.evaluate_conditions(loss_max_size, loss_max_size_conditions)
        )
        _, loss_scaled_count_msg, loss_scaled_count_level, _ = self.evaluate_conditions(
            loss_scaled_count, loss_scaled_count_conditions
        )
        _, drawdown_msg, drawdown_critical, drawdown_extramsg = (
            self.evaluate_conditions(current_drawdown, drawdown_conditions)
        )

        alerts = [
            (losing_streak_msg, losingstreak_level, alert_extramsg_default),
            (drawdown_msg, drawdown_critical, drawdown_extramsg),
            (pnl_msg, pnl_level, pnl_extramsg),
            (overtrade_msg, overtrade_level, overtrade_extramsg),
            (winrate_msg, winrate_level, winrate_extramsg),
            (profitfactor_msg, profitfactor_level, profitfactor_extramsg),
            (loss_max_size_msg, loss_max_size_level, loss_max_size_extramsg),
            (loss_scaled_count_msg, loss_scaled_count_level, alert_extramsg_default),
        ]

        return [
            {"message": msg, "level": level, "extra_message": extra}
            for msg, level, extra in alerts
            if msg
        ]

    def evaluate_conditions(self, value, conditions):
        for cond in conditions:
            if isinstance(cond, dict):
                if cond["expr"](value):
                    return (
                        cond["level"].get_color(),
                        cond["msg"],
                        cond["level"],
                        cond.get("extra_msg", ""),
                    )
        return ConcernLevel.DEFAULT.get_color(), "", ConcernLevel.DEFAULT, ""

    def get_total_trades_across_all(self):
        total_trade_count = 0
        for _, stats in self.account_trading_stats.items():
            for item in stats:
                if MetricNames.TRADES in item:
                    total_trade_count += int(item[MetricNames.TRADES][0])
        return total_trade_count

    def calculate_max_quantity(self, trades_dict: defaultdict) -> float:
        all_trades = []
        for trade_list in trades_dict.values():
            all_trades.extend(trade_list)

        all_trades.sort(key=lambda trade: trade.order_id)

        current_quantity = 0.0
        max_quantity = 0.0
        min_quantity = 0.0

        for trade in all_trades:
            if trade.order_type == "Filled BUY":
                current_quantity += trade.quantity
            elif trade.order_type == "Filled SELL":
                current_quantity -= trade.quantity
            else:
                continue

            max_quantity = max(max_quantity, current_quantity)
            min_quantity = min(min_quantity, current_quantity)

        return max(abs(max_quantity), abs(min_quantity))

    def print_streak_followtrade_statistics(self, list_name: str, data: list):
        print(f"--- {list_name} ---")
        sum_by_first_element = defaultdict(int)
        count_by_first_element = defaultdict(int)
        for first, second in data:
            sum_by_first_element[first] += second
            count_by_first_element[first] += 1
        total_items = len(data)
        sorted_first_elements = sorted(sum_by_first_element.keys())
        for first_element in sorted_first_elements:
            count = count_by_first_element[first_element]
            total_sum = sum_by_first_element[first_element]
            percentage = (count / total_items) * 100
            print(
                f"InterTradeTime: {first_element}, Count: {count}, Points: {total_sum:.2f}, %: {percentage:.2f}%"
            )
        total_count = sum(count_by_first_element.values())
        print(f"Count of InterTradeTime: {total_count}")
        total_sum_second_elements = sum(sum_by_first_element.values())
        print(f"Sum of Points: {total_sum_second_elements:.2f}")
