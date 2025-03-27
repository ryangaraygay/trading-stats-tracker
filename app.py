import sys
import re
import os
import glob
import datetime
import locale

from collections import defaultdict, namedtuple
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QGridLayout, QPushButton, QComboBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette, QFont

Trade = namedtuple("Trade", ["account_name", "order_id", "order_type", "quantity", "fill_price", "fill_time"])
StatValue = namedtuple("Key", "Value")
account_trading_stats = {}

def get_fills(file_path, contract_symbol):
    fill_data = []
    pattern = rf'OrderDirectory::orderFilled\(\) order: ID: (\S+) (\S+) {contract_symbol}\.CME.*(Filled BUY|Filled SELL).*Qty:(\d+\.\d+).*Last Fill Time:\s*(\d{{2}}/\d{{2}}/\d{{4}} \d{{1,2}}:\d{{2}} [AP]M).*fill price: (\d+\.\d+)'
    with open(file_path, 'r') as file:
        for line in file:
            match = re.search(pattern, line)
            if match:
            # if match and match.group(2) == "simulated":
                order_id = match.group(1)
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

def find_key_with_lowest_order_id(data):
    """
    Finds the key in a defaultdict(list) that contains the Trade object with the
    lowest order_id among all Trade objects in all lists.

    Args:
        data: The defaultdict(list) where values are lists of Trade objects.

    Returns:
        The key with the lowest order_id, or None if the defaultdict is empty.
    """
    lowest_order_id = float('inf')  # Initialize with positive infinity
    key_with_lowest = None

    for key, trades in data.items():
        for trade in trades:
            number_only_order_id = int(re.sub(r"[^0-9]", "", trade.order_id))
            if number_only_order_id < lowest_order_id:
            # if trade.order_id < lowest_order_id:
                lowest_order_id = number_only_order_id
                key_with_lowest = key

    return key_with_lowest

def parse_trading_log(fill_data, es_contract_value):
    if fill_data:
        # get list of AccountNames
        unique_account_names = set()
        for item in fill_data:
            unique_account_names.add(item.account_name)
        # print(unique_account_names)

        for account_name in unique_account_names:
            grouped_trades = defaultdict(list)
            completed_trades = 0
            total_buys = 0
            total_buy_contracts = 0
            total_sells = 0
            total_sell_contracts = 0
            total_profit_or_loss = 0.0
            total_wins = 0
            is_last_trade_win = False
            streak = 0
            best_streak = 0
            worst_streak = 0
            # winning_long = 0
            # long_profits = 0
            
            filtered_list = filter_namedtuples(fill_data, "account_name", account_name)

            sorted_fill = sorted(filtered_list, key=lambda record: int(re.sub(r"[^0-9]", "", record.order_id)), reverse=False) # keeping only digits for SIM-ID orders
            # print(sorted_fill)

            for fill in sorted_fill:
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

                for trade in grouped_trades["Filled SELL"]:
                    sell_qty += trade.quantity
                    sell_total_value += trade.quantity * trade.fill_price

                if len(grouped_trades) >=2 and (buy_qty - sell_qty) == 0:
                    completed_trades += 1
                    completed_profit_loss = (sell_total_value - buy_total_value) * es_contract_value
                    total_profit_or_loss += completed_profit_loss
                    is_win = completed_profit_loss > 0
                    total_wins += is_win

                    # if is_win:
                    #     winning_order_type = f'key= {find_key_with_lowest_order_id(grouped_trades)}'
                    #     winning_long += 1 if "BUY" in winning_order_type else 0 
                    #     long_profits += completed_profit_loss if "BUY" in winning_order_type else 0 

                    # print(f' win ' if is_win else 'loss')

                    if is_last_trade_win:
                        if is_win:
                            streak += 1
                        else:
                            streak = -1
                    else:
                        if is_win:
                            streak = 1
                        else:
                            streak -= 1

                    is_last_trade_win = is_win

                    best_streak = max(streak, best_streak)
                    worst_streak = min(streak, worst_streak)

                    # print('trade complete')
                    grouped_trades.clear()
        
            win_rate = 0 if completed_trades == 0 else total_wins/completed_trades * 100
            # long_win_rate = 0 if total_wins == 0 else winning_long/total_wins * 100
            # short_win_rate = 0 if total_wins == 0 else (total_wins-winning_long)/total_wins * 100

            trading_stats = [
                {"Trades (Win Rate)": f'{completed_trades} ({win_rate:.0f}%)'},
                {"Streak": f'{streak:+}'},
                {"Net P/L": f'${int(total_profit_or_loss):,}'},
                {"Best / Worst Streak": f'{best_streak:+} / {worst_streak:+}'},
                {"Long / Short Trades": f'{total_buys} / {total_sells}'},
                {"Contracts": f'{total_buy_contracts} / {total_sell_contracts}'},
                # {"Account": f'{account_name}'}
            ]

            # print(trading_stats)
            account_trading_stats[account_name] = trading_stats

    return account_trading_stats

def filter_namedtuples(list_of_namedtuples, attribute_name, target_value):
  """
  Filters a list of namedtuples based on the value of a specific attribute.

  Args:
    list_of_namedtuples: A list of namedtuples.
    attribute_name: The name of the attribute to filter by (as a string).
    target_value: The value to filter for.

  Returns:
    A new list containing only the namedtuples where the specified
    attribute's value matches the target_value.
  """
  filtered_list = [
      item
      for item in list_of_namedtuples
      if getattr(item, attribute_name) == target_value
  ]
  return filtered_list

def create_stats_window_pyqt6(account_trading_stats):
    """Creates a semi-transparent, always-on-top window with trading stats using PyQt6."""

    app = QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("Trading Statistics")

    # Make the window semi-transparent using a background color with alpha
    window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    window.setStyleSheet("background-color: rgba(0, 0, 0, 20);")  # Increased transparency (lower alpha)

    # Make the window always on top
    window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)

    # Set window opacity
    window.setWindowOpacity(0.85)

    layout = QGridLayout()

    # Dropdown (ComboBox)
    dropdown = QComboBox()
    sorted_keys = sorted(list(account_trading_stats.keys()))  # Sort the keys
    dropdown.addItems(sorted_keys)  # Fill dropdown with sorted keys

    # Increase font size for dropdown items
    dropdown_font = QFont()
    dropdown_font.setPointSize(27)  # Match table text size
    dropdown.setFont(dropdown_font)

    # Set white background and black text for dropdown
    dropdown.setStyleSheet("background-color: white; color: black;")

    layout.addWidget(dropdown, 0, 0, 1, 2)

    # Set fixed spacer height
    spacer_height = 30

    # Add dummy empty row to create space
    dummy_label = QLabel("")  # Create an empty label
    layout.addWidget(dummy_label, 1, 0, 1, 2)
    layout.setRowMinimumHeight(1, spacer_height)

    def refresh_data():
        selected_key = dropdown.currentText()
        fill_data = get_fills(filepath, contract_symbol)
        account_trading_stats = parse_trading_log(fill_data, contract_value)
        dropdown_changed(selected_key) #re-render with the updated data.

    # Refresh button
    refresh_button = QPushButton("Refresh")
    refresh_button.clicked.connect(refresh_data)

    def dropdown_changed(selected_key):
        """Handles dropdown selection change."""
        # Clear previous stats
        for i in reversed(range(layout.count())):
            item = layout.itemAt(i)
            if item and item.widget() and item.widget() != dropdown and item.widget() != dummy_label and item.widget() != refresh_button:
                item.widget().deleteLater()
                layout.removeItem(item)

        # Display stats for selected key
        selected_stats = account_trading_stats[selected_key]
        row_index = 2  # Start after the dropdown and dummy row.
        for stat in selected_stats:
            for key, value in stat.items():
                if key.lower() == "win_rate":
                    value = f'{value:.2f}%'

                key_label = QLabel(key)
                key_label.setStyleSheet("border: 1px solid black; color: white;")
                font = QFont()
                font.setPointSize(27)
                key_label.setFont(font)
                layout.addWidget(key_label, row_index, 0)

                value_label = QLabel(str(value))
                value_label.setStyleSheet("border: 1px solid black; color: white;")
                font = QFont()
                font.setPointSize(27)
                value_label.setFont(font)
                layout.addWidget(value_label, row_index, 1)

                row_index += 1

        layout.addWidget(refresh_button, row_index, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)

    dropdown.currentTextChanged.connect(dropdown_changed)

    # Call dropdown_changed before setting the layout
    dropdown_changed(sorted_keys[0])

    window.setLayout(layout)

    # Reduce window width by 50%
    window_width = 375
    window_height = 500
    window.resize(window_width, window_height)

    window.show()

    # Timer to auto refresh
    timer = QTimer()
    timer.timeout.connect(refresh_data)
    timer.start(auto_refresh_ms)

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
auto_refresh_ms = 60000

if __name__ == "__main__":
    filepath = get_latest_output_file(directory_path)
    # print(filepath)
    fill_data = get_fills(filepath, contract_symbol)
    ats = parse_trading_log(fill_data, contract_value)
    create_stats_window_pyqt6(ats)

# filepath = '/Users/ryangaraygay/Library/MotiveWave/output/output (Mar-26 215623).txt'
# file_path = "/Users/ryangaraygay/Library/MotiveWave/output/output (Mar-26 062616).txt"
# file_path = "/Users/ryangaraygay/Library/MotiveWave/output/output (Mar-26 105455).txt"
# output (Mar-26 215623).txt

# TODO
# commit to Github
# long vs short profitable (whats the right metric) - stands out as one is working we're on it or one is not working and we're against it
# time since last first entry
# time since last exit
# time since last order
# color or alerts
# handle the ALL stats case
# dropdown selection for which file
# overlay even to fullscreen window

# expectancy (if long versus short working)
# profit factor (profit/loss)
# max gain, max loss + position sizes
# avg gain, avg loss
# average size
# average duration
# average time between trades