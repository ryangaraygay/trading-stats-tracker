import sys
import re
import os
import glob
import datetime
import my_utils
from streak import Streak  # Import the Streak class

from collections import defaultdict, namedtuple
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QGridLayout, QPushButton, QComboBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette, QFont
from pynput.keyboard import Key, Controller
from datetime import timedelta

Trade = namedtuple("Trade", ["account_name", "order_id", "order_type", "quantity", "fill_price", "fill_time"])
StatValue = namedtuple("Key", "Value")
class Color:
    CAUTION = "yellow"
    WARNING = "orange"
    CRITICAL = "red"
    OK = "green"
    DEFAULT = "white"
    
account_trading_stats = {}
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

                # print(f'Order ID: {order_id}')
                # print(f'Order Type: {order_type}')
                # print(f'Quantity: {quantity if "BUY" in order_type else -quantity}')
                # print(f'Fill Time: {fill_time}')
                # print(f'Fill Price: {fill_price}')
                # print('-' * 40)

                fill_data.append(Trade(account_name, order_id, order_type, quantity, fill_price, fill_time))
    return fill_data

def compute_trade_stats(fill_data, es_contract_value):
    if fill_data:
        # get list of AccountNames in fill
        account_names_with_fills = set()
        for item in fill_data:
            account_names_with_fills.add(item.account_name)
        # print(account_names_with_fills)

        account_names_no_fills = [item for item in account_names_loaded if item not in account_names_with_fills]
        for no_fill_account in account_names_no_fills:
            trading_stats = [
                {"Trades": [f'0']},
                {"Last Updated": [f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}']},
            ]
            account_trading_stats[no_fill_account] = trading_stats

        # # test specific accounts only
        # account_names_with_fills.clear()
        # account_names_with_fills.add("account-name-here")

        for account_name in account_names_with_fills:
            grouped_trades = defaultdict(list)
            completed_trades = 0
            total_buys = 0
            total_buy_contracts = 0
            total_sells = 0
            total_sell_contracts = 0
            total_profit_or_loss = 0.0
            total_wins = 0
            gains = 0
            losses = 0
            max_realized_drawdown = 0
            loss_max_size = 0 # not individual orders but within a trade (group)
            loss_max_value = 0 # not individual orders but within a trade (group)
            loss_scaled_count = 0 # losses that involved multiple entries

            streak_tracker = Streak()

            filtered_list = my_utils.filter_namedtuples(fill_data, "account_name", account_name)

            sorted_fill = sorted(filtered_list, key=lambda record: record.order_id, reverse=False) # keeping only digits for SIM-ID orders
            # print(sorted_fill)

            min_time = datetime.max
            max_time = datetime.min
            last_exit_time = datetime.max
            loss_duration = list()
            win_duration = list()
            entry_is_long = True
            time_between_trades = list()

            for fill in sorted_fill:
                if len(grouped_trades) == 0:
                    entry_is_long = "BUY" in fill.order_type
                    if completed_trades > 0: # start only when there is at least one
                        duration_since_last_trade = fill.fill_time - last_exit_time
                        time_between_trades.append(duration_since_last_trade)

                grouped_trades[fill.order_type].append(fill)
                # print(grouped_trades)

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
                    min_time = min(min_time, trade.fill_time)
                    max_time = max(max_time, trade.fill_time)

                for trade in grouped_trades["Filled SELL"]:
                    sell_qty += trade.quantity
                    sell_total_value += trade.quantity * trade.fill_price
                    min_time = min(min_time, trade.fill_time)
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
                    duration = max_time - min_time
                    last_exit_time = max_time
                    
                    if not is_win:
                        loss_max_size = max(loss_max_size, buy_qty) # can be sell_qty since completed trades have equal sell and buy qty
                        loss_max_value = min(loss_max_value, completed_profit_loss)
                        
                        loss_duration.append(duration)

                        # scaled loss
                        entries_in_trade_count = len(grouped_trades["Filled BUY" if entry_is_long else "Filled SELL"])
                        loss_scaled_count += 1 if entries_in_trade_count > 1 else 0
                    else:
                        win_duration.append(duration)
                        
                    streak_tracker.process(is_win, entry_is_long)

                    # print('trade complete')
                    grouped_trades.clear()
                    min_time = datetime.max
                    max_time = datetime.min

            win_rate = 0 if completed_trades == 0 else total_wins/completed_trades * 100
            profit_factor = 2 if losses == 0 else gains/losses
            
            overtrade_color = Color.CRITICAL if completed_trades > 20 else Color.WARNING if completed_trades > 10 else Color.DEFAULT
            winrate_color = Color.CRITICAL if win_rate < 20 else Color.WARNING if win_rate < 40 else Color.DEFAULT
            profitfactor_color = Color.CRITICAL if profit_factor < 0.5 else Color.WARNING if profit_factor < 1 else Color.DEFAULT
            losing_streak_color = Color.CRITICAL if streak_tracker.streak <= -5 else Color.WARNING if streak_tracker.streak <=-2 else Color.DEFAULT
            pnl_color = Color.CRITICAL if total_profit_or_loss < -1000 else Color.OK if total_profit_or_loss >= 1000 else Color.DEFAULT
            max_drawdown_color = Color.WARNING if max_realized_drawdown < -1000 else Color.DEFAULT
            max_loss_color = Color.WARNING if loss_max_value <= -900 else Color.DEFAULT
            open_size_color = Color.WARNING if abs(position_size) > 3 else Color.DEFAULT
            loss_max_size_color = Color.CRITICAL if loss_max_size >= 10 else Color.WARNING if loss_max_size >= 6 else Color.DEFAULT
            loss_scaled_count_color = Color.CRITICAL if loss_scaled_count >= 5 else Color.WARNING if loss_scaled_count >= 3 else Color.DEFAULT

            loss_avg_secs = my_utils.average_timedelta(loss_duration)
            loss_max_secs = my_utils.max_timedelta(loss_duration)
            win_avg_secs = my_utils.average_timedelta(win_duration)
            win_max_secs = my_utils.max_timedelta(win_duration)
            avg_duration_color = Color.WARNING if win_avg_secs < loss_avg_secs else Color.DEFAULT
            max_duration_color = Color.WARNING if win_max_secs < loss_max_secs else Color.DEFAULT
            time_between_trades_avg_secs = my_utils.average_timedelta(time_between_trades)
            time_between_trades_max_secs = my_utils.max_timedelta(time_between_trades)
            intertrade_time_avg_color = Color.WARNING if time_between_trades_avg_secs < timedelta(seconds=60) else Color.DEFAULT
            
            trading_stats = [
                {"Trades": [f'{completed_trades}', f'{overtrade_color}']},
                {"Win Rate": [f'{win_rate:.0f}%', f'{winrate_color}']},
                {"Profit Factor": [f'{profit_factor:.01f}', f'{profitfactor_color}']},
                {"Long/Short Trades": [f'{total_buys} / {total_sells}']},
                {"": [f'']},
                {"Streak": [f'{streak_tracker.streak:+}', f'{losing_streak_color}']},
                {"Streak Loss Mix": [f'{streak_tracker.get_loss_mix()}', f'{losing_streak_color}']},
                {"Best/Worst Streak": [f'{streak_tracker.best_streak:+} / {streak_tracker.worst_streak:+}']},
                {"": [f'']},
                {"Net P/L": [f'${int(total_profit_or_loss):,}', f'{pnl_color}']},
                {"Max Drawdown": [f'${int(max_realized_drawdown):,}', f'{max_drawdown_color}']},
                {"Max Loss": [f'${int(loss_max_value):,}', f'{max_loss_color}']},
                {"Scaled Losses": [f'{int(loss_scaled_count):,}', f'{loss_scaled_count_color}']},
                {"": [f'']},
                {"Open Size": [f'{int(position_size)}', f'{open_size_color}']},
                {"Max Loss Size": [f'{int(loss_max_size)}', f'{loss_max_size_color}']},
                {"": [f'']},
                {"Duration Avg W/L": [f'{my_utils.format_timedelta(win_avg_secs)} / {my_utils.format_timedelta(loss_avg_secs)}', f'{avg_duration_color}']},
                {"Duration Max W/L": [f'{my_utils.format_timedelta(win_max_secs)} / {my_utils.format_timedelta(loss_max_secs)}', f'{max_duration_color}']},
                {"InterTrade Avg": [f'{my_utils.format_timedelta(time_between_trades_avg_secs)}', f'{intertrade_time_avg_color}']},
                {"InterTrade Max": [f'{my_utils.format_timedelta(time_between_trades_max_secs)}']},
                {"": [f'']},
                {"Contracts L/S": [f'{total_buy_contracts} / {total_sell_contracts}']},
                {"Last Updated": [f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}']},
                # {"Account": f'{account_name}'}
            ]

            # print(trading_stats)

            account_trading_stats[account_name] = trading_stats

    return account_trading_stats

def pause_trading():
    """Pause trading functionality (empty implementation)."""
    keyboard = Controller()

    keyboard.press(Key.cmd)
    keyboard.press(Key.alt)
    keyboard.press("d")

    keyboard.release("d")
    keyboard.release(Key.alt)
    keyboard.release(Key.cmd)
    
def create_stats_window_pyqt6(account_trading_stats):
    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Trading Statistics")
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    window.setStyleSheet("background-color: rgba(0, 0, 0, 20);")
    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
    window.setWindowOpacity(opacity)

    layout = QGridLayout(window)  # Set layout on the window directly

    dropdown = QComboBox()
    sorted_keys = sorted(list(account_trading_stats.keys()))
    dropdown.addItems(sorted_keys)
    dropdown_font = QFont()
    dropdown_font.setPointSize(27)
    dropdown.setFont(dropdown_font)
    dropdown.setStyleSheet("background-color: gray; color: black;")
    layout.addWidget(dropdown, 0, 0, 1, 2)

    spacer_height = 30
    dummy_label = QLabel("")
    layout.addWidget(dummy_label, 1, 0, 1, 2)
    layout.setRowMinimumHeight(1, spacer_height)

    refresh_button = QPushButton("Refresh")
    pause_button = QPushButton("Pause Trading")
    close_button = QPushButton("Close")

    def refresh_data():
        refresh_button.setText(f'Refresh [{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]')
        selected_key = dropdown.currentText()
        fill_data = get_fills(filepath, contract_symbol)
        current_fill_count = len(fill_data)
        global existing_fill_count
        if current_fill_count != existing_fill_count:
            account_trading_stats = compute_trade_stats(fill_data, contract_value)
            dropdown_changed(selected_key) #re-render with the updated data.
            existing_fill_count = current_fill_count

    def close_app():
        app.quit()

    refresh_button.clicked.connect(refresh_data)
    pause_button.clicked.connect(pause_trading)
    close_button.clicked.connect(close_app)

    def dropdown_changed(selected_key):
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            if item and item.widget() and item.widget() not in (dropdown, dummy_label, refresh_button, pause_button, close_button):
                item.widget().deleteLater()
                layout.removeItem(item)

        selected_stats = account_trading_stats[selected_key]
        row_index = 2
        for stat in selected_stats:
            for key, value_color in stat.items():
                if isinstance(value_color[0], str) and not value_color[0]:
                    layout.setRowMinimumHeight(row_index, 20)
                    row_index += 1
                else:
                    key_label = QLabel(key)
                    key_label.setStyleSheet("border: 1px solid black; color: white;")
                    font = QFont()
                    font.setPointSize(27)
                    key_label.setFont(font)
                    layout.addWidget(key_label, row_index, 0)

                    value_label = QLabel(str(value_color[0]))
                    color = value_color[1] if len(value_color) > 1 else Color.DEFAULT
                    value_label.setStyleSheet(f"border: 1px solid black; color: {color};")
                    font = QFont()
                    font.setPointSize(27)
                    value_label.setFont(font)
                    layout.addWidget(value_label, row_index, 1)
                    row_index += 1
    
    dropdown.currentTextChanged.connect(dropdown_changed)
    dropdown_changed(sorted_keys[0])
    
    layout.addWidget(refresh_button, button_row_index_start, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(pause_button, button_row_index_start + 1, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(close_button, button_row_index_start + 2, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
    window.adjustSize()

    window.show()

    timer = QTimer()
    timer.timeout.connect(refresh_data)
    timer.start(auto_refresh_ms) #use variable.

    sys.exit(app.exec())

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
opacity = 1.0 #0.85
button_row_index_start = 28 # fixed so we don't have to window adjust when refreshing and some accounts have no fills (and therefore no stats)

if __name__ == "__main__":
    filepath = get_latest_output_file(directory_path)
    # filepath = "/Users/ryangaraygay/Library/MotiveWave/output/output (Mar-27 203706).txt" # some accounts with no fills
    # filepath = "/Users/ryangaraygay/Library/MotiveWave/output/output (Mar-27 062404).txt"
    # print(filepath)
    get_account_names(filepath)
    fill_data = get_fills(filepath, contract_symbol)
    ats = compute_trade_stats(fill_data, contract_value)
    if len(ats) > 0:
        create_stats_window_pyqt6(ats)
    else:
        print('no fills found')

# TODO
## optional metrics (only if not computational expensive and have time to develop)
#   losing streak (total duration, avg intra-trade time) - very good indication of tilt
#   open trade duration (time since last first entry) - (yellow) we should let our winners run

## more features
# alert
#   recommended actions based on stats - display somehow (ensure relevancy/frequency)
#   pause trading when selected account has losing streak
#       but first think through how it will work (not unitentionally disruptive/nuisance)
#       ensure it does not disable on every refresh of tradestats
#       and after a break, we still have a losing streak - so do we snooze disable for N minutes?
# handle the ALL stats case (multi-account view)
# dropdown selection for which file
# overlay even to fullscreen window

## improvements
# calculate average through the loop instead of lambda