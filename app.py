import sys
import re
import os
import glob
import datetime
import my_utils
from streak import Streak  # Import the Streak class
from hammerspoon_alert_manager import HammerspoonAlertManager

from collections import defaultdict, namedtuple
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QGridLayout, QPushButton, QComboBox, QCheckBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette, QFont
from pynput.keyboard import Key, Controller
from datetime import timedelta

DAY_TIME_FORMAT = "%m-%d %H:%M"
DATE_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

Trade = namedtuple("Trade", ["account_name", "order_id", "order_type", "quantity", "fill_price", "fill_time"])
AlertMessage = namedtuple("AlertMessage", ["message", "account", "duration_secs", "display_once", "min_interval_secs", "critical", "extra_msg"])
StatValue = namedtuple("Key", "Value")
class Color:
    CAUTION = "yellow"
    WARNING = "orange"
    CRITICAL = "red"
    OK = "#90EE90"
    DEFAULT = "white"
class MetricNames:
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

keys_to_exclude = [
    MetricNames.AVG_SIZE,
    MetricNames.OPEN_ENTRY,
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
] # Define keys to exclude if extra metrics is unchecked.
    
account_trading_stats = {}
account_trading_alerts = {}
existing_fill_count = 0
account_names_loaded = list()

def get_account_names(file_path):
    account_names = set()
    pattern = r"ACCOUNT:\s*(\S+)\s+fcmId:"
    with open(file_path, 'r') as file:
        for line in file:
            match = re.search(pattern, line)
            if match:
                account_name = match.group(1)
                account_names.add(account_name)
    account_names.add("simulated")
    global account_names_loaded
    account_names_loaded = sorted(list(account_names))
    
def get_fills(file_path, contract_symbol):
    fill_data = []
    pattern = rf'OrderDirectory::orderFilled\(\) order: ID: (\S+) (\S+) {contract_symbol}\.CME.*(Filled BUY|Filled SELL).*Qty:(\d+\.\d+).*Last Fill Time:\s*(\d{{2}}/\d{{2}}/\d{{4}} \d{{1,2}}:\d{{2}} [AP]M).*fill price: (\d+\.\d+)'
    with open(file_path, 'r') as file:
        for line in file:
            match = re.search(pattern, line)
            if match:
            # if match and match.group(2) == "simulated":
                order_id = int(re.sub(r"[^0-9]", "", match.group(1))) #SIM-dd (we need this for ordering since fill_time has no second value and so inaccurate)
                account_name = match.group(2)
                order_type = match.group(3)
                quantity = float(match.group(4))
                fill_time_str = match.group(5)
                fill_price = float(match.group(6))

                fill_time = None
                try:
                    # Parse the datetime string
                    fill_time = datetime.strptime(fill_time_str, "%m/%d/%Y %I:%M %p")
                except ValueError:
                    print(f"Error parsing datetime: {fill_time_str}")
                    return None

                add_unique_namedtuple(fill_data, Trade(account_name, order_id, order_type, quantity, fill_price, fill_time))
    return fill_data

def add_unique_namedtuple(data_list, new_namedtuple):
    existing_combinations = set((t.account_name, t.order_id) for t in data_list)
    new_combination = (new_namedtuple.account_name, new_namedtuple.order_id)

    if new_combination not in existing_combinations:
        data_list.append(new_namedtuple)
        return True
    else:
        return False

def compute_trade_stats(fill_data, es_contract_value):
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

            directional_bias = ""
            long_bias_percentage = 0 if completed_trades == 0 else (total_long_trades / completed_trades) * 100
            short_bias_percentage = 0 if completed_trades == 0 else (total_short_trades / completed_trades) * 100

            if long_bias_percentage == 100:
                directional_bias = f"100% long"
            elif short_bias_percentage == 100:
                directional_bias = f"100% short"
            else:
                if long_bias_percentage > short_bias_percentage:
                    directional_bias = f"{long_bias_percentage:.0f}% long"
                else:
                    directional_bias = f"{short_bias_percentage:.0f}% short"

            # alert conditions, color change only if msg is empty
            trade_conditions = [
                {"expr": lambda x: x > 20, "color": Color.CRITICAL, "msg": "Stop. Overtrading.", "extra_msg": f"{completed_trades} trades"},
                {"expr": lambda x: x > 10, "color": Color.WARNING, "msg": "Slow down. Too many trades.", "extra_msg": f"{completed_trades} trades"}
            ]

            pnl_conditions = [
                {"expr": lambda x: x < -2000, "color": Color.CRITICAL, "msg": "Stop. Too much Loss."},
                {"expr": lambda x: x < -1000, "color": Color.WARNING, "msg": "Slow down. Losing."},
                {"expr": lambda x: x >= 1000, "color": Color.OK, "msg": "Wind down. Protect gains."}
            ]

            winrate_conditions = [
                {"expr": lambda x: x < 20, "color": Color.CRITICAL, "msg": "Stop. Win Rate very low.", "extra_msg": f"{directional_bias}"},
                {"expr": lambda x: x < 40, "color": Color.WARNING, "msg": "Slow down. Win Rate low.", "extra_msg": f"{directional_bias}"},
            ]

            profitfactor_conditions = [
                {"expr": lambda x: x < 0.5, "color": Color.CRITICAL, "msg": "Stop. Profit Factor very low.", "extra_msg": f"{directional_bias}"},
                {"expr": lambda x: x > 1.5, "color": Color.OK, "msg": ""},
            ]

            losingstreak_conditions = [
                {"expr": lambda x: x <= -4, "color": Color.CRITICAL, "msg": f"Stop. Extended losing streak. {streak_tracker.get_loss_mix()} in {streak_tracker.get_loss_elapsed_time_mins_str()}"},
                {"expr": lambda x: x <= -2, "color": Color.WARNING, "msg": f"Slow down. Consecutive losses. {streak_tracker.get_loss_mix()} in {streak_tracker.get_loss_elapsed_time_mins_str()}"},
            ]

            loss_max_size_conditions = [
                {"expr": lambda x: x >= 10, "color": Color.CRITICAL, "msg": "Stop. Size down."},
                {"expr": lambda x: x >= 6, "color": Color.WARNING, "msg": "Size down."},
            ]
            
            loss_scaled_count_conditions = [
                {"expr": lambda x: x >= 5, "color": Color.CRITICAL, "msg": "Stop. Scale up winners only."},
                {"expr": lambda x: x >= 3, "color": Color.WARNING, "msg": "Scale up winners only."},
            ]

            winrate_color, winrate_msg, winrate_critical, winrate_extramsg = evaluate_conditions(win_rate, winrate_conditions)
            overtrade_color, overtrade_msg, overtrade_critical, overtrade_extramsg = evaluate_conditions(completed_trades, trade_conditions)
            pnl_color, pnl_msg, pnl_critical, extra_msg_placeholder = evaluate_conditions(total_profit_or_loss, pnl_conditions)
            profitfactor_color, profitfactor_msg, profitfactor_critical, profitfactor_extramsg = evaluate_conditions(profit_factor, profitfactor_conditions)
            losing_streak_color, losing_streak_msg, losingstreak_critical, extra_msg_placeholder = evaluate_conditions(streak_tracker.streak, losingstreak_conditions)
            loss_max_size_color, loss_max_size_msg, loss_max_size_critical, loss_max_size_extramsg = evaluate_conditions(loss_max_size, loss_max_size_conditions)
            loss_scaled_count_color, loss_scaled_count_msg, loss_scaled_count_critical, extra_msg_placeholder = evaluate_conditions(loss_scaled_count, loss_scaled_count_conditions)
            
            # color change only (can be converted to above approach too with resulting empty msg but only if there's benefit)  
            open_size_color = Color.CAUTION if abs(position_size) > 3 else Color.DEFAULT
            avg_duration_color = Color.WARNING if win_avg_secs < loss_avg_secs else Color.DEFAULT
            max_duration_color = Color.WARNING if win_max_secs < loss_max_secs else Color.DEFAULT
            intertrade_time_avg_color = Color.WARNING if time_between_trades_avg_secs < timedelta(seconds=60) else Color.DEFAULT
            win_scaled_count_color = Color.OK if win_scaled_count >= 2 else Color.DEFAULT

            open_entry_time_i = entry_time.strftime(DAY_TIME_FORMAT) if position_size != 0 else ''
            open_entry_duration = calculate_mins(open_entry_time_i, datetime.now())
            open_entry_duration_str = "" if open_entry_duration == 0 else open_entry_duration

            avg_orders_per_trade = 0 if completed_trades == 0 else (total_buys + total_sells) / (completed_trades * 2)
            
            trading_stats = [
                {"Trades": [f'{completed_trades}', f'{overtrade_color}']},
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

            account_trading_stats[account_name] = trading_stats

            alert_duration_default = 20
            alert_duration_critical = 120
            alert_min_interval_secs_default = 600 # 10 mins
            alert_extramsg_default = ""
            alerts_data = [
                (overtrade_msg, False, overtrade_critical, overtrade_extramsg),
                (pnl_msg, False, pnl_critical, alert_extramsg_default),
                (winrate_msg if completed_trades > 3 else "", False, winrate_critical, winrate_extramsg),
                (profitfactor_msg if completed_trades > 3 else "", False, profitfactor_critical, profitfactor_extramsg),
                (losing_streak_msg, False, losingstreak_critical, alert_extramsg_default),
                (loss_max_size_msg, False, loss_max_size_critical, loss_max_size_extramsg),
                (loss_scaled_count_msg, False, loss_scaled_count_critical, alert_extramsg_default),
            ]

            critical_alerts = []
            non_critical_alerts = []

            # TODO lambda sort based on critical when adding trading_alerts to simplify
            for msg, show_once, critical, extra_msg in alerts_data:
                if msg:
                    alert = AlertMessage(msg, account_name, alert_duration_critical if critical else alert_duration_default, show_once, alert_min_interval_secs_default, critical, extra_msg)
                    if critical:
                        critical_alerts.append(alert)
                    else:
                        non_critical_alerts.append(alert)

            trading_alerts = []
            trading_alerts.extend(critical_alerts)
            trading_alerts.extend(non_critical_alerts)

            account_trading_alerts[account_name] = trading_alerts

    account_names_no_fills = [item for item in account_names_loaded if item not in account_names_with_fills]
    for no_fill_account in account_names_no_fills:
        trading_stats = [
            {"Trades": [f'0']},
            {"Last Updated": [f'{datetime.now().strftime(DATE_TIME_FORMAT)}']},
        ]
        account_trading_stats[no_fill_account] = trading_stats

    return [ account_trading_stats, account_trading_alerts ]

def evaluate_conditions(value, conditions):
    for cond in conditions:
        if isinstance(cond, dict):
            if cond["expr"](value):
                return cond["color"], cond["msg"], cond["color"] == Color.CRITICAL, cond.get("extra_msg", "")
        elif isinstance(cond, tuple) and len(cond) == 3:
            if cond[0](value):
                return cond[1], cond[2], cond[1] == Color.CRITICAL, ""
    return Color.DEFAULT, "", False, ""

open_entry_time_str = ""  # Global variable to store the Open Entry time string
open_duration_label = None

alert_manager = HammerspoonAlertManager()
app = QApplication(sys.argv)
dropdown = QComboBox()

def create_stats_window_pyqt6(account_trading_stats):
    window = QWidget()
    window.setWindowTitle("Trading Statistics")
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    window.setStyleSheet("background-color: rgba(0, 0, 0, 20);")
    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    window.setWindowOpacity(opacity)

    layout = QGridLayout(window)  # Set layout on the window directly

    font_name = "Courier New" #Andale Mono, Menlo

    sorted_keys = sorted(list(account_names_loaded))
    dropdown.addItems(sorted_keys)
    dropdown_font = QFont(font_name)
    dropdown_font.setPointSize(27)
    dropdown.setFont(dropdown_font)
    dropdown.setStyleSheet("background-color: gray; color: black;")
    layout.addWidget(dropdown, 0, 0, 1, 2)

    spacer_height = 30
    dummy_label = QLabel("")
    layout.addWidget(dummy_label, 1, 0, 1, 2)
    layout.setRowMinimumHeight(1, spacer_height)

    extra_metrics_checkbox = QCheckBox("Extra Metrics")
    extra_metrics_checkbox.setChecked(False)
    refresh_button = QPushButton("Refresh")
    pause_button = QPushButton("Pause Trading")
    close_button = QPushButton("Close")

    def refresh_data():
        refresh_button.setText(f'Refresh [{datetime.now().strftime(DATE_TIME_FORMAT)}]')
        selected_key = dropdown.currentText()
        fill_data = get_fills(filepath, contract_symbol)
        current_fill_count = len(fill_data)
        global existing_fill_count
        if current_fill_count != existing_fill_count:
            account_trading_stats, account_trading_alerts = compute_trade_stats(fill_data, contract_value)
            dropdown_changed(selected_key) #re-render with the updated data.
            existing_fill_count = current_fill_count

    def close_app():
        app.quit()

    refresh_button.clicked.connect(refresh_data)
    close_button.clicked.connect(close_app)

    def dropdown_changed(selected_key):
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            if item and item.widget() and item.widget() not in (dropdown, dummy_label, extra_metrics_checkbox, refresh_button, pause_button, close_button):
                item.widget().deleteLater()
                layout.removeItem(item)

        selected_stats = account_trading_stats[selected_key]
        row_index = 2
        for stat in selected_stats:
            for key, value_color in stat.items():
                if not extra_metrics_checkbox.isChecked() and key in keys_to_exclude: # Check if key should be excluded.
                    continue
                if isinstance(key, str) and not key:
                    layout.setRowMinimumHeight(row_index, 20)
                    row_index += 1
                else:
                    if key == MetricNames.OPEN_ENTRY:
                        global open_entry_time_str
                        open_entry_time_str = str(value_color[0])
                        
                    key_label = QLabel(key)
                    key_label.setStyleSheet("border: 1px solid black; color: white;")
                    key_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    font = QFont(font_name)
                    font.setPointSize(27)
                    key_label.setFont(font)
                    layout.addWidget(key_label, row_index, 0)

                    value_label = QLabel(str(value_color[0]))
                    color = value_color[1] if len(value_color) > 1 else Color.DEFAULT
                    value_label.setStyleSheet(f"border: 1px solid black; color: {color};")
                    font = QFont(font_name)
                    font.setPointSize(27)
                    value_label.setFont(font)
                    layout.addWidget(value_label, row_index, 1)

                    if key == MetricNames.OPEN_DURATION:
                        global open_duration_label
                        open_duration_label = value_label

                    row_index += 1

        update_minutes()
        
        if selected_key in account_trading_alerts:
            selected_alerts = account_trading_alerts[selected_key]
            for alert in selected_alerts:
                alert_manager.display_alert(alert.message, alert.account, alert.duration_secs, alert.display_once, alert.min_interval_secs, alert.critical, alert.extra_msg)
        
    dropdown.currentTextChanged.connect(dropdown_changed)
    dropdown_changed(sorted_keys[0])
    
    def checkbox_changed(state):
        selected_key = dropdown.currentText()
        dropdown_changed(selected_key)
        window.adjustSize()

    extra_metrics_checkbox.stateChanged.connect(checkbox_changed)

    layout.addWidget(extra_metrics_checkbox, button_row_index_start, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(refresh_button, button_row_index_start + 1, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(close_button, button_row_index_start + 2, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
    window.adjustSize()

    window.show()

    timer = QTimer()
    timer.timeout.connect(refresh_data)
    timer.start(auto_refresh_ms) #use variable.

    duration_timer = QTimer()
    duration_timer.timeout.connect(update_minutes)
    duration_timer.start(60000)  # 60000 milliseconds = 1 minute
    sys.exit(app.exec())

def calculate_mins(open_entry_time_str, reference_time):
    if not open_entry_time_str:
        return 0
    try:
        open_entry_time = datetime.strptime(open_entry_time_str, DAY_TIME_FORMAT)
        current_year = reference_time.year
        open_entry_time = open_entry_time.replace(year=current_year)
        time_difference = reference_time - open_entry_time
        minutes = int(time_difference.total_seconds() / 60)
        return minutes
    except ValueError as e:
        print(e)
        return 0

def update_minutes():
    minutes = calculate_mins(open_entry_time_str, datetime.now())
    if minutes != 0:
        global open_duration_label
        open_duration_label.setText(f'{minutes}')

        caution_minutes = 10 # TODO set to correct threshold = 10
        if minutes >= caution_minutes: 
            open_duration_label.setStyleSheet(f"border: 1px solid black; color: yellow;")
            print(dropdown.currentText())
            alert_manager.display_alert(f"Trade open for > 10 mins", dropdown.currentText(), 5, False, 600, False)

def get_latest_output_file(directory):
    """
    Finds the most recently created or modified file in a directory that starts with "output".

    Args:
        directory (str): The path to the directory.

    Returns:
        str: The path to the latest file, or None if no matching files are found.
    """

    try:
        # Construct the file pattern
        file_pattern = os.path.join(directory, "output*")

        # Find all files matching the pattern
        files = glob.glob(file_pattern)

        if not files:
            return None  # No matching files found

        # Get the file paths and modification times
        file_times = [(file, os.path.getmtime(file)) for file in files]

        # Find the file with the latest modification time
        latest_file = max(file_times, key=lambda x: x[1])[0]

        return latest_file

    except Exception as e:
        print(f"An error occurred: {e}")
        return None

filepath = ""
contract_symbol = "ESM5"
contract_value = 50
directory_path = "/Users/ryangaraygay/Library/MotiveWave/output/"  # Replace with your directory path
auto_refresh_ms = 30000 #60000
opacity = 1
button_row_index_start = 38 # fixed so we don't have to window adjust when refreshing and some accounts have no fills (and therefore no stats)

if __name__ == "__main__":
    filepath = get_latest_output_file(directory_path)
    # filepath = "/Users/ryangaraygay/Library/MotiveWave/output/output (Mar-27 203706).txt" # some accounts with no fills
    # filepath = "/Users/ryangaraygay/Library/MotiveWave/output/output (Mar-27 062404).txt"
    get_account_names(filepath)
    fill_data = get_fills(filepath, contract_symbol)
    account_trading_stats, account_trading_alerts = compute_trade_stats(fill_data, contract_value)
    if len(account_trading_stats) > 0:
        create_stats_window_pyqt6(account_trading_stats)
    else:
        print('no fills found')

# TODO
#   what % of wins are scaled wins
## analyze more files to see any patterns/standouts (multi-file handling - even if no GUI yet)
## more features
#   handle the ALL stats case (multi-account view)
#   dropdown selection for which file (or maybe even multi-select)
#   limit to one instance running, alert if attempting to open more

## improvements
#   calculate average through the loop instead of lambda
#   profile and improve performance (so refresh freq can be higher)
#   clean-up and organize code