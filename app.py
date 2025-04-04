import sys
import datetime
import my_utils

from config import Config
from color import Color
from metrics_names import MetricNames
from trade_stats_processor import TradeStatsProcessor
from hammerspoon_alert_manager import HammerspoonAlertManager
from constants import CONST

from collections import Counter
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QGridLayout, QPushButton, QComboBox, QCheckBox, QDialog
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from log_file_selector import LogFileSelector

class TradingStatsApp(QApplication):
    def __init__(self, config: Config):
        super().__init__(sys.argv)
            
        self.config = config
        self.processor = TradeStatsProcessor()
        self.alert_manager = HammerspoonAlertManager()
        self.window = QWidget()
        self.dropdown = QComboBox()
        self.selectedFiles = list()
        self.open_entry_time_str = ""
        self.open_duration_label = None
        self.existing_fill_count = 0

        self.dialog = LogFileSelector(config.directory_path, CONST.LOG_FILENAME_PATTERN, self.window)
        
        self.duration_timer = QTimer()
        self.duration_timer.timeout.connect(self.update_minutes)
        self.duration_timer.start(config.open_duration_refresh_ms)

        self.reload_all_data_from_source()
        self.create_stats_window()

        print('Trading Stats App Initialized.')

    def reload_all_data_from_source(self):
        fp = self.single_log_filepath()
        self.processor.load_account_names(fp)
        fill_data = self.processor.get_fills(fp, config.contract_symbol)
        self.existing_fill_count = len(fill_data)
        self.processor.compute_trade_stats(fill_data, config.contract_value)

    def single_log_filepath(self):
        sel_files = self.dialog.get_selected_files()
        return sel_files[0] # TODO support multiple files as source

    extra_metrics_names = [
        MetricNames.AVG_SIZE,
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

    def create_stats_window(self):
        self.window.setWindowTitle("Trading Statistics")
        self.window.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.window.setStyleSheet("background-color: rgba(0, 0, 0, 20);")
        self.window.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        # self.window.setWindowOpacity(opacity) 0.85

        layout = QGridLayout(self.window)  # Set layout on the window directly

        font_name = "Courier New" #Andale Mono, Menlo

        sorted_keys = sorted(list(self.processor.account_names_loaded))
        self.dropdown.addItems(sorted_keys)
        dropdown_font = QFont(font_name)
        dropdown_font.setPointSize(27)
        self.dropdown.setFont(dropdown_font)
        self.dropdown.setStyleSheet("background-color: gray; color: black;")
        layout.addWidget(self.dropdown, 0, 0, 1, 2)

        spacer_height = 30
        dummy_label = QLabel("")
        layout.addWidget(dummy_label, 1, 0, 1, 2)
        layout.setRowMinimumHeight(1, spacer_height)

        extra_metrics_checkbox = QCheckBox("Extra Metrics")
        extra_metrics_checkbox.setChecked(False)
        refresh_button = QPushButton("Refresh")
        pause_button = QPushButton("Pause Trading")
        close_button = QPushButton("Close")
        select_logfile_button = QPushButton("Select Log File(s)")

        def refresh_data():
            refresh_button.setText(f'Refresh [{datetime.now().strftime(CONST.DATE_TIME_FORMAT)}]')
            selected_key = self.dropdown.currentText()
            fill_data = self.processor.get_fills(self.single_log_filepath(), config.contract_symbol)
            current_fill_count = len(fill_data)
            if current_fill_count != self.existing_fill_count:
                print(f'current_fill_count {current_fill_count} existing_fill_count {self.existing_fill_count}')
                self.processor.compute_trade_stats(fill_data, config.contract_value)
                dropdown_changed(selected_key) #re-render with the updated data.
                self.existing_fill_count = current_fill_count

        def close_app():
            self.quit()
            
        refresh_button.clicked.connect(refresh_data)
        close_button.clicked.connect(close_app)

        def dropdown_changed(selected_key):
            for i in reversed(range(layout.count())):
                item = layout.itemAt(i)
                if item and item.widget() and item.widget() not in (self.dropdown, dummy_label, extra_metrics_checkbox, refresh_button, pause_button, close_button, select_logfile_button):
                    item.widget().deleteLater()
                    layout.removeItem(item)

            selected_stats = self.processor.account_trading_stats[selected_key]
            row_index = 2
            for stat in selected_stats:
                for key, value_color in stat.items():
                    if not extra_metrics_checkbox.isChecked() and key in self.extra_metrics_names: # Check if key should be excluded.
                        continue
                    if isinstance(key, str) and not key:
                        layout.setRowMinimumHeight(row_index, 20)
                        row_index += 1
                    else:
                        if key == MetricNames.OPEN_ENTRY:
                            self.open_entry_time_str = str(value_color[0])
                            
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
                            self.open_duration_label = value_label

                        row_index += 1

            self.update_minutes()
            
            if selected_key in self.processor.account_trading_alerts:
                selected_alerts = self.processor.account_trading_alerts[selected_key]
                for alert in selected_alerts:
                    self.alert_manager.display_alert(alert.message, alert.account, alert.duration_secs, alert.display_once, alert.min_interval_secs, alert.critical, alert.extra_msg)
            
        self.dropdown.currentTextChanged.connect(dropdown_changed)
        self.dropdown.setCurrentText(CONST.SELECT_ACCOUNT)
        
        def checkbox_changed(state):
            selected_key = self.dropdown.currentText()
            dropdown_changed(selected_key)
            self.window.adjustSize()

        extra_metrics_checkbox.stateChanged.connect(checkbox_changed)

        def select_log_files():
            old_file_selection = self.dialog.get_selected_files()
            result = self.dialog.exec()
            if result == QDialog.DialogCode.Accepted:
                new_file_selection = self.dialog.get_selected_files()
                if Counter(old_file_selection) != Counter(new_file_selection):
                    existing_selection_key = self.dropdown.currentText()
                    self.reload_all_data_from_source()
                    sorted_keys = sorted(list(self.processor.account_names_loaded))
                    self.dropdown.currentTextChanged.disconnect(dropdown_changed)
                    self.dropdown.clear()
                    self.dropdown.addItems(sorted_keys)
                    self.dropdown.currentTextChanged.connect(dropdown_changed)
                    if not existing_selection_key:
                        self.dropdown.setCurrentText(CONST.SELECT_ACCOUNT)
                    else:
                        if existing_selection_key in sorted_keys:
                            self.dropdown.setCurrentText(existing_selection_key)
                        else:
                            self.dropdown.setCurrentText(CONST.SELECT_ACCOUNT)

        select_logfile_button.clicked.connect(select_log_files)
        
        
        button_row_index_start = 38 # fixed so we don't have to window adjust when refreshing and some accounts have no fills (and therefore no stats)
        layout.addWidget(extra_metrics_checkbox, button_row_index_start, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(select_logfile_button, button_row_index_start + 1, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(refresh_button, button_row_index_start + 2, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(close_button, button_row_index_start + 3, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.window.adjustSize()
        self.window.show()

        self.timer = QTimer()
        self.timer.timeout.connect(refresh_data)
        self.timer.start(config.auto_refresh_ms)

    def update_minutes(self):
        minutes = my_utils.calculate_mins(self.open_entry_time_str, datetime.now())
        if minutes != 0:
            self.open_duration_label.setText(f'{minutes}')
            caution_minutes = config.open_trade_duration_notice_mins
            if minutes >= caution_minutes: 
                self.open_duration_label.setStyleSheet(f"border: 1px solid black; color: yellow;")
                self.alert_manager.display_alert(f"Trade open for > 10 mins", self.dropdown.currentText(), 5, False, 600, False)

if __name__ == "__main__":
    config = Config()
    app = TradingStatsApp(config)
    sys.exit(app.exec())

# TODO
## add metric
#   current drawdown (peak to current P/L)
## more features
#   support multi-file selection and remove single_log_filepath
#   analyze more files to see any patterns/standouts
#   handle the ALL stats case (multi-account view)

## improvements
#   calculate average through the loop instead of lambda
#   profile and improve performance (so refresh freq can be higher)
#   clean-up and organize code
#   limit to one instance running, alert if attempting to open more
