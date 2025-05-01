import sys
import datetime
import my_utils

from config import Config
from concern_level import ConcernLevel
from metrics_names import MetricNames
from trade_stats_processor import TradeStatsProcessor
from hammerspoon_alert_manager import HammerspoonAlertManager
from constants import CONST
from trade_group_display import TradeGroupDisplay

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
        self.processor = TradeStatsProcessor(config)
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

        self.account_tradecount_on_recent_alert = {}
        self.reload_all_data_from_source()
        self.create_stats_window()

        print('Trading Stats App Initialized.')

    def reload_all_data_from_source(self):
        filepaths = self.dialog.get_selected_files()
        self.processor.load_account_names(filepaths)
        fill_data = self.processor.get_fills(filepaths, config.contract_symbol)
        self.existing_fill_count = len(fill_data)
        self.processor.compute_trade_stats(fill_data)

    def call_last_trade(self):
        self.last_trade_count = self.processor.get_total_trades_across_all()
        self.alert_manager.display_alert("You have called for a Last Trade. Winding down.", "ALL_ACCOUNTS", 5, 5, ConcernLevel.DEFAULT, "")

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
        refresh_button = QPushButton("Refresh Fills")
        pause_button = QPushButton("Pause Trading")
        close_button = QPushButton("Close")
        select_logfile_button = QPushButton("Select Log File(s)")
        refresh_all_button = QPushButton("Refresh All")
        call_last_trade_button = QPushButton("Call For Last Trade")
        show_trades_button = QPushButton("Show Trades")

        def refresh_data():
            selected_key = self.dropdown.currentText()
            fill_data = self.processor.get_fills(self.dialog.get_selected_files(), config.contract_symbol)
            current_fill_count = len(fill_data)
            if current_fill_count != self.existing_fill_count:
                self.processor.compute_trade_stats(fill_data)
                dropdown_changed(selected_key) #re-render with the updated data.
                self.existing_fill_count = current_fill_count
            refresh_button.setText(f'Refresh Fills [{datetime.now().strftime(CONST.DATE_TIME_FORMAT)}]')

        def close_app():
            self.quit()

        refresh_button.clicked.connect(refresh_data)
        close_button.clicked.connect(close_app)

        def dropdown_changed(selected_key):
            for i in reversed(range(layout.count())):
                item = layout.itemAt(i)
                if item and item.widget() and item.widget() not in (
                        self.dropdown, 
                        dummy_label, 
                        extra_metrics_checkbox, 
                        refresh_button, 
                        refresh_all_button, 
                        pause_button, 
                        close_button, 
                        select_logfile_button,
                        call_last_trade_button,
                        show_trades_button):
                    item.widget().deleteLater()
                    layout.removeItem(item)

            selected_stats = self.processor.account_trading_stats[selected_key]
            row_index = 2
            for stat in selected_stats:
                for key, value_color in stat.items():
                    if not extra_metrics_checkbox.isChecked() and key in MetricNames.get_extra_metric_names(): # Check if key should be excluded.
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
                        color = value_color[1] if len(value_color) > 1 else ConcernLevel.DEFAULT.get_color()
                        value_label.setStyleSheet(f"border: 1px solid black; color: {color};")
                        font = QFont(font_name)
                        font.setPointSize(27)
                        value_label.setFont(font)
                        layout.addWidget(value_label, row_index, 1)

                        if key == MetricNames.OPEN_DURATION:
                            self.open_duration_label = value_label

                        row_index += 1

            self.update_minutes()
            
            # handle alerts and blocks
            if hasattr(self, 'last_trade_count'):
                new_total_tradecount = self.processor.get_total_trades_across_all()
                if (new_total_tradecount > self.last_trade_count):
                    last_trade_alert_duration_secs = 300
                    last_trade_alert_min_interval_secs = 300
                    self.alert_manager.display_alert(
                        "You have completed your Last Trade. Well done.", 
                        "ALL_ACCOUNTS", 
                        last_trade_alert_duration_secs, 
                        last_trade_alert_min_interval_secs, 
                        ConcernLevel.OK, 
                        "")
                    self.alert_manager.trigger_event(
                        "block-app", 
                        {"app_name": config.block_app_name, "duration": last_trade_alert_duration_secs},
                        last_trade_alert_min_interval_secs)
                    return 

            account_name = selected_key
            if account_name in self.processor.account_trading_alerts:
                selected_alerts = self.processor.account_trading_alerts[account_name]
                if len(selected_alerts) > 0:
                    # check first if there have been new trades since last alert
                    new_tradecount = 0
                    for item in selected_stats:
                        if MetricNames.TRADES in item:
                            new_tradecount = int(item[MetricNames.TRADES][0])

                    old_tradecount = 0
                    if account_name in self.account_tradecount_on_recent_alert:
                        old_tradecount = self.account_tradecount_on_recent_alert[account_name]                        

                    if new_tradecount != old_tradecount:
                        concernLevel = ConcernLevel.DEFAULT
                        for alert in selected_alerts:
                            if config.alert_enabled:
                                self.alert_manager.display_alert(alert.message, alert.account, alert.duration_secs, alert.min_interval_secs, alert.level, alert.extra_msg)
                            concernLevel = max(concernLevel, alert.level)

                        if (config.block_app_on_critical_alerts):
                            if concernLevel >= ConcernLevel.CAUTION:
                                self.alert_manager.trigger_event(
                                    "block-app", 
                                    {"app_name": config.block_app_name, "duration": config.get_alert_duration(concernLevel)}, # sync duration of both block and alert 
                                    config.get_min_interval_secs(concernLevel)) # sync quiet period of both block and alert
                        self.account_tradecount_on_recent_alert[account_name] = new_tradecount

        self.dropdown.currentTextChanged.connect(dropdown_changed)
        self.dropdown.setCurrentText(CONST.SELECT_ACCOUNT)
        
        def checkbox_changed(state):
            selected_key = self.dropdown.currentText()
            dropdown_changed(selected_key)
            self.window.adjustSize()

        extra_metrics_checkbox.stateChanged.connect(checkbox_changed)

        def refresh_all():
            existing_selection_key = self.dropdown.currentText()
            self.reload_all_data_from_source()
            sorted_keys = sorted(list(self.processor.account_names_loaded))
            self.dropdown.currentTextChanged.disconnect(dropdown_changed)
            self.dropdown.clear()
            self.dropdown.addItems(sorted_keys)
            if not existing_selection_key:
                self.dropdown.setCurrentText(CONST.SELECT_ACCOUNT)
                dropdown_changed(CONST.SELECT_ACCOUNT)
            else:
                if existing_selection_key in sorted_keys:
                    self.dropdown.setCurrentText(existing_selection_key)
                    dropdown_changed(existing_selection_key)
                else:
                    self.dropdown.setCurrentText(CONST.SELECT_ACCOUNT)
                    dropdown_changed(CONST.SELECT_ACCOUNT)
            self.dropdown.currentTextChanged.connect(dropdown_changed)

        refresh_all_button.clicked.connect(refresh_all)

        def select_log_files():
            old_file_selection = self.dialog.get_selected_files()
            result = self.dialog.exec()
            if result == QDialog.DialogCode.Accepted:
                new_file_selection = self.dialog.get_selected_files()
                if Counter(old_file_selection) != Counter(new_file_selection):
                    refresh_all()
                    
        select_logfile_button.clicked.connect(select_log_files)
        call_last_trade_button.clicked.connect(self.call_last_trade)

        def open_trades_window():
            account_name = self.dropdown.currentText()
            if account_name in self.processor.account_trade_groups.keys():
                selected_trade_groups = self.processor.account_trade_groups[account_name]
                trade_group_dialog = TradeGroupDisplay(selected_trade_groups, self.window)
                trade_group_dialog.show()

        show_trades_button.clicked.connect(open_trades_window)

        button_style = """
            QPushButton {
                background-color: gray;
                color: black;
                border-radius: 5px;
                font-size: 16pt;
                padding: 5px 10px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: lightgray;
            }
        """
        call_last_trade_button.setStyleSheet(button_style)
        select_logfile_button.setStyleSheet(button_style)
        refresh_button.setStyleSheet(button_style)
        refresh_all_button.setStyleSheet(button_style)
        close_button.setStyleSheet(button_style)
        show_trades_button.setStyleSheet(button_style)

        button_row_index_start = 44 # fixed so we don't have to window adjust when refreshing and some accounts have no fills (and therefore no stats)
        layout.addWidget(extra_metrics_checkbox, button_row_index_start, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(call_last_trade_button, button_row_index_start + 1, 0, 1, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(show_trades_button, button_row_index_start + 1, 1, 1, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(select_logfile_button, button_row_index_start + 2, 0, 1, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(refresh_all_button, button_row_index_start + 2, 1, 1, 1, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(refresh_button, button_row_index_start + 3, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(close_button, button_row_index_start + 4, 0, 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)

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
                if config.alert_enabled:
                    self.alert_manager.display_alert(f"Trade open for > 10 mins", self.dropdown.currentText(), 5, 600, ConcernLevel.CAUTION, "")

if __name__ == "__main__":
    config = Config()
    app = TradingStatsApp(config)
    sys.exit(app.exec())