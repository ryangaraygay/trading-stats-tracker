import re
import os
import glob
import datetime
import my_utils

from concern_level import ConcernLevel
from trade import Trade
from collections import defaultdict
from streak import Streak
from datetime import timedelta, datetime
from constants import CONST
from metrics_names import MetricNames
from alert_message import AlertMessage
from config import Config

class TradeStatsProcessor:

    def __init__(self, config: Config):
        self.config = config
        self.account_trading_stats = {}
        self.account_trading_alerts = {}
        self.account_names_loaded = list()

    def load_account_names(self, file_paths):
        account_names = set()
        pattern = r"ACCOUNT:\s*(\S+)\s+fcmId:"
        for file_path in file_paths:
            with open(file_path, 'r') as file:
                for line in file:
                    match = re.search(pattern, line)
                    if match:
                        account_name = match.group(1)
                        account_names.add(account_name)
        account_names.add("simulated")
        account_names.add(CONST.SELECT_ACCOUNT)
        self.account_names_loaded = sorted(list(account_names))
        
    def get_fills(self, file_paths, contract_symbol):
        unique_trades_dict = {}
        for file_path in file_paths:
            pattern = rf'OrderDirectory::orderFilled\(\) order: ID: (\S+) (\S+) {contract_symbol}\.CME.*(Filled BUY|Filled SELL).*Qty:(\d+\.\d+).*Last Fill Time:\s*(\d{{2}}/\d{{2}}/\d{{4}} \d{{1,2}}:\d{{2}} [AP]M).*fill price: (\d+\.\d+)'
            with open(file_path, 'r') as file:
                for line in file:
                    match = re.search(pattern, line)
                    if match:
                        order_id = int(re.sub(r"[^0-9]", "", match.group(1))) #SIM-dd (we need this for ordering since fill_time has no second value and so inaccurate)
                        account_name = match.group(2)
                        order_type = match.group(3)
                        quantity = float(match.group(4))
                        fill_time_str = match.group(5)
                        fill_price = float(match.group(6))
                        fill_time = datetime.strptime(fill_time_str, "%m/%d/%Y %I:%M %p")
                        unique_trades_dict[account_name, order_id] = Trade(account_name, order_id, order_type, quantity, fill_price, fill_time)

        fill_data = list(unique_trades_dict.values())
        if len(fill_data) == 0:
            print('No Fills Found')
        
        return fill_data

    def compute_trade_stats(self, fill_data, es_contract_value):
        account_names_with_fills = set()
        if fill_data:
            # get list of AccountNames in fill
            for item in fill_data:
                account_names_with_fills.add(item.account_name)

            # test specific accounts only
            # account_names_with_fills.clear()
            # account_names_with_fills.add("simulated")

            for account_name in account_names_with_fills:
                grouped_trades = defaultdict(list)
                completed_trades = 0
                total_long_trades = 0
                total_buys = 0
                total_buy_contracts = 0
                total_short_trades = 0
                total_sells = 0
                total_sell_contracts = 0
                total_profit_or_loss = 0.0
                total_wins = 0
                gains = 0
                losses = 0
                max_realized_drawdown = 0
                max_realized_profit = 0
                loss_max_size = 0 # not individual orders but within a trade (group)
                win_max_size = 0 # not individual orders but within a trade (group)
                loss_max_value = 0 # not individual orders but within a trade (group)
                win_max_value = 0 # not individual orders but within a trade (group)
                loss_scaled_count = 0 # losses that involved multiple entries
                win_scaled_count = 0 # wins that involved multiple entries

                streak_tracker = Streak()

                filtered_list = my_utils.filter_namedtuples(fill_data, "account_name", account_name)
                sorted_fill = sorted(filtered_list, key=lambda record: record.order_id, reverse=False) # keeping only digits for SIM-ID orders

                max_time = datetime.min
                last_exit_time = datetime.max
                loss_duration = list()
                win_duration = list()
                entry_is_long = True
                time_between_trades = list()
                entry_time = datetime.max
                first_entry_time = datetime.max

                for fill in sorted_fill:
                    if len(grouped_trades) == 0:
                        entry_is_long = "BUY" in fill.order_type
                        entry_time = fill.fill_time
                        first_entry_time = min(first_entry_time, entry_time)
                        if completed_trades > 0: # start only when there is at least one
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
                    if len(grouped_trades) >=2 and position_size == 0: # trade completed
                        completed_trades += 1
                        completed_profit_loss = (sell_total_value - buy_total_value) * es_contract_value
                        total_profit_or_loss += completed_profit_loss
                        is_win = completed_profit_loss > 0
                        total_wins += is_win

                        gains += completed_profit_loss if is_win else 0
                        losses += 0 if is_win else abs(completed_profit_loss)

                        max_realized_drawdown = min(total_profit_or_loss, max_realized_drawdown)
                        max_realized_profit = max(total_profit_or_loss, max_realized_profit)
                        last_exit_time = max_time
                        duration = last_exit_time - entry_time

                        trade_size = int(buy_qty) # can be sell_qty since completed trades have equal sell and buy qty
                        entries_in_trade_count = len(grouped_trades["Filled BUY" if entry_is_long else "Filled SELL"])
                        
                        if not is_win:
                            loss_max_size = max(loss_max_size, trade_size) 
                            loss_max_value = min(loss_max_value, completed_profit_loss)
                            loss_duration.append(duration)
                            loss_scaled_count += 1 if entries_in_trade_count > 1 else 0
                        else:
                            win_max_size = max(win_max_size, trade_size) 
                            win_max_value = max(win_max_value, completed_profit_loss)
                            win_duration.append(duration)
                            win_scaled_count += 1 if entries_in_trade_count > 1 else 0
                        
                        total_long_trades += 1 if entry_is_long else 0
                        total_short_trades += 1 if not entry_is_long else 0

                        streak_tracker.process(is_win, entry_is_long, entry_time, last_exit_time, trade_size)

                        grouped_trades.clear()
                        max_time = datetime.min
                        entry_time = datetime.max

                win_rate = 50 if completed_trades == 0 else total_wins/completed_trades * 100
                profit_factor = 1 if losses == 0 else gains/losses
                loss_avg_secs = my_utils.average_timedelta(loss_duration)
                loss_max_secs = my_utils.max_timedelta(loss_duration)
                win_avg_secs = my_utils.average_timedelta(win_duration)
                win_max_secs = my_utils.max_timedelta(win_duration)
                time_between_trades_avg_secs = my_utils.average_timedelta(time_between_trades)
                time_between_trades_max_secs = my_utils.max_timedelta(time_between_trades)
                current_drawdown = -1 * int(max_realized_profit - total_profit_or_loss)

                directional_bias = ""
                long_bias_percentage = 0 if completed_trades == 0 else (total_long_trades / completed_trades) * 100
                short_bias_percentage = 0 if completed_trades == 0 else (total_short_trades / completed_trades) * 100

                if long_bias_percentage == 100:
                    directional_bias = f"100% long."
                elif short_bias_percentage == 100:
                    directional_bias = f"100% short."
                else:
                    if long_bias_percentage > short_bias_percentage:
                        directional_bias = f"{long_bias_percentage:.0f}% long"
                    else:
                        directional_bias = f"{short_bias_percentage:.0f}% short"

                directional_bias_extramsg = "Join the SHORT." if long_bias_percentage >= 90 else "Join the LONG." if long_bias_percentage <= 10 else directional_bias

                # alert conditions, color change only if msg is empty
                trade_conditions = [
                    {"expr": lambda x: x >= 30, "level": ConcernLevel.CRITICAL, "msg": "Stop. Maximum trades for the day reached.", "extra_msg": f"{completed_trades}"},
                    {"expr": lambda x: x >= 20 and total_profit_or_loss > 0, "level": ConcernLevel.OK, "msg": "Wind down. You've reached your trade count goal.", "extra_msg": f"{completed_trades}"},
                    {"expr": lambda x: x >= 20, "level": ConcernLevel.WARNING, "msg": "Wind down. You've reached your trade count goal.", "extra_msg": f"{completed_trades}"},
                    {"expr": lambda x: x >= 10, "level": ConcernLevel.CAUTION, "msg": "Slow down. Take quality trades only.", "extra_msg": f"{completed_trades}"}
                ]

                pnl_conditions = [
                    {"expr": lambda x: x < -2100, "level": ConcernLevel.CRITICAL, "msg": "Stop. Protect your capital.", "extra_msg": f'{int(total_profit_or_loss):+,}'},
                    {"expr": lambda x: x < -1400, "level": ConcernLevel.WARNING, "msg": "Pause. Reset first, then recover.", "extra_msg": f'{int(total_profit_or_loss):+,}'},
                    {"expr": lambda x: x < -700, "level": ConcernLevel.CAUTION, "msg": "Slow down. Manage loss by managing risk.", "extra_msg": f'{int(total_profit_or_loss):+,}'},
                    {"expr": lambda x: x >= 1000, "level": ConcernLevel.OK, "msg": "Wind down. Protect gains.", "extra_msg": f'{int(total_profit_or_loss):+,}'}
                ]

                winrate_conditions = [
                    {"expr": lambda x: x <= 25 and profit_factor < 1.0 and completed_trades >= 10, "level": ConcernLevel.WARNING, "msg": "Reset. Win Rate very low.", "extra_msg": f"{directional_bias_extramsg}"},
                    {"expr": lambda x: x <= 40 and profit_factor < 1.5 and completed_trades >= 5, "level": ConcernLevel.CAUTION, "msg": "Slow down. Win Rate low.", "extra_msg": f"{directional_bias_extramsg}"},
                ]

                profitfactor_conditions = [
                    {"expr": lambda x: x < 1.0 and completed_trades >= 10, "level": ConcernLevel.WARNING, "msg": "Reset. Profit Factor very low.", "extra_msg": f"{directional_bias_extramsg}"},
                    {"expr": lambda x: x < 1.5 and completed_trades >= 5, "level": ConcernLevel.CAUTION, "msg": "Slow down. Profit Factor low.", "extra_msg": f"{directional_bias_extramsg}"},
                    {"expr": lambda x: x >= 1.5, "level": ConcernLevel.OK, "msg": ""},
                ]

                losingstreak_conditions = [
                    {"expr": lambda x: x <= -7, "level": ConcernLevel.CRITICAL, "msg": f"Stop Now. Protect the version of YOU that will trade well tomorrow."},
                    {"expr": lambda x: x <= -5, "level": ConcernLevel.WARNING, "msg": f"Stop. Follow Reset plan."},
                    {"expr": lambda x: x <= -3, "level": ConcernLevel.CAUTION, "msg": f"Slow down. Consecutive losses. {streak_tracker.get_extra_msg()}"},
                ]

                loss_max_size_conditions = [
                    {"expr": lambda x: x >= 10, "level": ConcernLevel.WARNING, "msg": "Reset. Size down."},
                    {"expr": lambda x: x >= 6, "level": ConcernLevel.CAUTION, "msg": "Size down."},
                    {"expr": lambda x: x >= 4 and profit_factor < 1.0 and completed_trades >= 3, "level": ConcernLevel.CAUTION, "msg": "Size down."},
                ]
                
                loss_scaled_count_conditions = [
                    {"expr": lambda x: x >= 5, "level": ConcernLevel.WARNING, "msg": "Reset. Scale up winners only."},
                    {"expr": lambda x: x >= 3, "level": ConcernLevel.CAUTION, "msg": "Scale up winners only."},
                ]

                drawdown_conditions = [
                    {"expr": lambda x: x < -3000, "level": ConcernLevel.CRITICAL, "msg": "Stop Now. Maximum drawdown.", "extra_msg": f'{current_drawdown:+,}'},
                    {"expr": lambda x: x < -2000, "level": ConcernLevel.WARNING, "msg": "Reset. Large drawdown.", "extra_msg": f'{current_drawdown:+,}'},
                    {"expr": lambda x: x < -1000, "level": ConcernLevel.CAUTION, "msg": "Slow down. Notable drawdown.", "extra_msg": f'{current_drawdown:+,}'},
                ]

                winrate_color, winrate_msg, winrate_level, winrate_extramsg = self.evaluate_conditions(win_rate, winrate_conditions)
                overtrade_color, overtrade_msg, overtrade_level, overtrade_extramsg = self.evaluate_conditions(completed_trades, trade_conditions)
                pnl_color, pnl_msg, pnl_level, pnl_extramsg = self.evaluate_conditions(total_profit_or_loss, pnl_conditions)
                profitfactor_color, profitfactor_msg, profitfactor_level, profitfactor_extramsg = self.evaluate_conditions(profit_factor, profitfactor_conditions)
                losing_streak_color, losing_streak_msg, losingstreak_level, _ = self.evaluate_conditions(streak_tracker.streak, losingstreak_conditions)
                loss_max_size_color, loss_max_size_msg, loss_max_size_level, loss_max_size_extramsg = self.evaluate_conditions(loss_max_size, loss_max_size_conditions)
                loss_scaled_count_color, loss_scaled_count_msg, loss_scaled_count_level, _ = self.evaluate_conditions(loss_scaled_count, loss_scaled_count_conditions)
                drawdown_color, drawdown_msg, drawdown_critical, drawdown_extramsg = self.evaluate_conditions(current_drawdown, drawdown_conditions)
                
                # color change only (can be converted to above approach too with resulting empty msg but only if there's benefit)  
                open_size_color = (ConcernLevel.CAUTION if abs(position_size) > 3 else ConcernLevel.DEFAULT).get_color()
                avg_duration_color = (ConcernLevel.WARNING if win_avg_secs < loss_avg_secs else ConcernLevel.DEFAULT).get_color()
                max_duration_color = (ConcernLevel.WARNING if win_max_secs < loss_max_secs else ConcernLevel.DEFAULT).get_color()
                intertrade_time_avg_color = (ConcernLevel.WARNING if time_between_trades_avg_secs < timedelta(seconds=60) else ConcernLevel.DEFAULT).get_color()
                win_scaled_count_color = (ConcernLevel.OK if win_scaled_count >= 2 else ConcernLevel.DEFAULT).get_color()

                open_entry_time_i = entry_time.strftime(CONST.DAY_TIME_FORMAT) if position_size != 0 else ''
                open_entry_duration = my_utils.calculate_mins(open_entry_time_i, datetime.now())
                open_entry_duration_str = "" if open_entry_duration == 0 else open_entry_duration

                avg_orders_per_trade = 0 if completed_trades == 0 else (total_buys + total_sells) / (completed_trades * 2)
                
                trading_stats = [
                    {MetricNames.TRADES: [f'{completed_trades}', f'{overtrade_color}']},
                    {"Win Rate": [f'{win_rate:.0f}%', f'{winrate_color}']},
                    {"Profit Factor": [f'{profit_factor:.01f}', f'{profitfactor_color}']},
                    {"Bias": [f'{directional_bias}']},
                    {"Scaled Losses": [f'{int(loss_scaled_count):,}', f'{loss_scaled_count_color}']},
                    {"Max Loss Size": [f'{int(loss_max_size)}', f'{loss_max_size_color}']},
                    {"": [f'']},
                    {"Consecutive W/L": [f'{streak_tracker.streak:+}', f'{losing_streak_color}']},
                    {"Mix": [f'{streak_tracker.get_loss_mix()}']},
                    {"Duration": [f'{streak_tracker.get_loss_elapsed_time_mins_str()}']},
                    {MetricNames.AVG_SIZE: [f'{streak_tracker.get_avg_size_of_current_streak_str()}']},
                    # {"Max Size": [f'{streak_tracker.get_max_size_of_current_streak_str()}']},
                    {"Best/Worst": [f'{streak_tracker.best_streak:+} / {streak_tracker.worst_streak:+}']},
                    {"": [f'']},
                    {"Profit/Loss": [f'{int(total_profit_or_loss):+,}', f'{pnl_color}']},
                    {"Drawdown": [f'{int(current_drawdown):+,}', f'{drawdown_color}']},
                    {"Peak P/L": [f'{int(max_realized_profit):+,} / {int(max_realized_drawdown):+,}']},
                    {"Max Trade P/L": [f'{int(win_max_value):+,} / {int(loss_max_value):+,}']},
                    {"": [f'']},
                    {"Open Size": [f'{int(position_size)}', f'{open_size_color}']},
                    {MetricNames.OPEN_DURATION: [f'{open_entry_duration_str}']},
                    {MetricNames.OPEN_ENTRY: [f'{open_entry_time_i}']},
                    {MetricNames.FIRST_ENTRY: [f'{first_entry_time.strftime("%m/%d %H:%M")}']},
                    {MetricNames.LAST_EXIT: [f'{last_exit_time.strftime("%m/%d %H:%M")}']},
                    {"": [f'']},
                    {MetricNames.INTERTRADE_AVG: [f'{my_utils.format_timedelta(time_between_trades_avg_secs)}', f'{intertrade_time_avg_color}']},
                    {MetricNames.INTERTRADE_MAX: [f'{my_utils.format_timedelta(time_between_trades_max_secs)}']},
                    {MetricNames.DURATION_AVG: [f'{my_utils.format_timedelta(win_avg_secs)} / {my_utils.format_timedelta(loss_avg_secs)}', f'{avg_duration_color}']},
                    {MetricNames.DURATION_MAX: [f'{my_utils.format_timedelta(win_max_secs)} / {my_utils.format_timedelta(loss_max_secs)}', f'{max_duration_color}']},
                    # {"": [f'']},
                    # {"Trades L/S": [f'{total_long_trades} / {total_short_trades}']},
                    {MetricNames.AVG_ORDERS_PER_TRADE: [f'{avg_orders_per_trade:.01f}']},
                    {MetricNames.ORDERS_LONG_SHORT: [f'{total_buys} / {total_sells}']},
                    {MetricNames.CONTRACTS_LONG_SHORT: [f'{total_buy_contracts} / {total_sell_contracts}']},
                    {MetricNames.SCALED_WINS: [f'{int(win_scaled_count):,}', f'{win_scaled_count_color}']},
                    {MetricNames.MAX_WIN_SZE: [f'{int(win_max_size)}']},
                    # {"": [f'']},
                    {MetricNames.LAST_UPDATED: [f'{datetime.now().strftime("%m/%d %H:%M")}']},
                    # {"Account": f'{account_name}'}
                ]

                self.account_trading_stats[account_name] = trading_stats

                alert_extramsg_default = ""
                alerts_data = [
                    (losing_streak_msg, losingstreak_level, alert_extramsg_default),
                    (drawdown_msg, drawdown_critical, drawdown_extramsg),
                    (pnl_msg, pnl_level, pnl_extramsg),
                    (overtrade_msg, overtrade_level, overtrade_extramsg),
                    (winrate_msg, winrate_level, winrate_extramsg),
                    (profitfactor_msg, profitfactor_level, profitfactor_extramsg),
                    (loss_max_size_msg, loss_max_size_level, loss_max_size_extramsg),
                    (loss_scaled_count_msg, loss_scaled_count_level, alert_extramsg_default),
                ]

                trading_alerts = []

                for msg, level, extra_msg in alerts_data:
                    if msg:
                        alert = AlertMessage(
                            msg, 
                            account_name, 
                            self.config.get_alert_duration(level),
                            self.config.get_min_interval_secs(level),
                            level,
                            extra_msg
                            )
                        trading_alerts.append(alert)
                        
                self.account_trading_alerts[account_name] = sorted(trading_alerts, key=lambda record: record.level, reverse=True)
        else:
            self.account_trading_stats.clear()
            self.account_trading_alerts.clear()

        account_names_no_fills = [item for item in self.account_names_loaded if item not in account_names_with_fills]
        trading_stats = [
            {"Trades": [f'0']},
            {"Last Updated": [f'{datetime.now().strftime(CONST.DATE_TIME_FORMAT)}']},
        ]
        for no_fill_account in account_names_no_fills:
            self.account_trading_stats[no_fill_account] = trading_stats

        self.account_trading_stats[CONST.SELECT_ACCOUNT] = trading_stats

        # print(self.account_trading_stats)

    def evaluate_conditions(self, value, conditions):
        for cond in conditions:
            if isinstance(cond, dict):
                if cond["expr"](value):
                    return cond["level"].get_color(), cond["msg"], cond["level"], cond.get("extra_msg", "")
        return ConcernLevel.DEFAULT.get_color(), "", ConcernLevel.DEFAULT, ""