from dataclasses import fields
from trade_group import TradeGroup

from PyQt6.QtWidgets import (
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor, QBrush

class TradeGroupDisplay(QDialog):
    def __init__(self, trade_groups, parent=None):
        super().__init__(parent)
        self.initUI(trade_groups)

    def initUI(self, trade_groups):
        self.setWindowTitle("Trade Group Details")

        table = QTableWidget()
        dataclass_fields = fields(TradeGroup)
        headers = [field.name for field in dataclass_fields]
        readable_headers = ["Entry Time", "Exit Time", "Max Size", "Long/Short", "Points"]
        display_headers = readable_headers if len(readable_headers) == len(headers) else [h.replace('_', ' ').title() for h in headers]
        num_rows = len(trade_groups)
        num_cols = len(headers)
        table.setRowCount(num_rows)
        table.setColumnCount(num_cols)
        table.setHorizontalHeaderLabels(display_headers)
        for row_idx, trade_group in enumerate(trade_groups):
            val1 = trade_group.entry_time; item1 = DateTimeTableWidgetItem(format_datetime(val1), val1); item1.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter); table.setItem(row_idx, 0, item1)
            val2 = trade_group.exit_time; item2 = DateTimeTableWidgetItem(format_datetime(val2), val2); item2.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter); table.setItem(row_idx, 1, item2)
            val3 = trade_group.max_trade_size; item3 = NumericTableWidgetItem(format_float_size(val3), val3); item3.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            item3.setForeground(QBrush(QColor(100, 255, 100) if trade_group.entry_is_long else QColor(255, 100, 100)))
            table.setItem(row_idx, 2, item3)

            val0 = trade_group.entry_is_long; item0 = QTableWidgetItem("Long" if val0 else "Short"); item0.setTextAlignment(Qt.AlignmentFlag.AlignCenter); table.setItem(row_idx, 3, item0)

            val4 = trade_group.trade_point; item4 = NumericTableWidgetItem(format_float_points(val4), val4); item4.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item4.setForeground(QBrush(QColor(0, 0, 0)))
            if val4 > 0: item4.setBackground(QBrush(QColor(200, 255, 200)))
            elif val4 < 0: item4.setBackground(QBrush(QColor(255, 200, 200)))
            else: item4.setBackground(QBrush(QColor(255, 255, 255)))
            table.setItem(row_idx, 4, item4)

            for col_idx in range(num_cols):
                item = table.item(row_idx, col_idx); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable) if item else None
        table.setSortingEnabled(True)
        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.setFont(QFont("Courier New", 20))

        layout = QVBoxLayout(self)
        layout.addWidget(table)

        table.resizeColumnsToContents()
        table.resizeRowsToContents()
        table.updateGeometry()

        # Calculate required width/height
        width = table.verticalHeader().width()  # start with row header width
        for i in range(table.columnCount()):
            width += table.columnWidth(i)
        width += table.frameWidth() * 2

        height = table.horizontalHeader().height()
        for i in range(table.rowCount()):
            height += table.rowHeight(i)
        height += table.frameWidth() * 2

        # Add layout spacing/margins
        width += layout.contentsMargins().left() + layout.contentsMargins().right() + 20 # add for vertical scrollbar
        height += layout.contentsMargins().top() + layout.contentsMargins().bottom()

        # Resize dialog
        self.resize(width, height)

# --- Formatting functions (Unchanged) ---
def format_bool(val): return str(val)
def format_datetime(dt): return dt.strftime('%m-%d %H:%M') if dt else ""
def format_float_size(val): return f"{int(val)}"
def format_float_points(val): return f"{val:.2f}"

class DateTimeTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, dt_value): super().__init__(text); self.dt_value = dt_value
    def __lt__(self, other):
        if isinstance(other, DateTimeTableWidgetItem):
            if self.dt_value is None and other.dt_value is None: return False
            if self.dt_value is None: return True
            if other.dt_value is None: return False
            return self.dt_value < other.dt_value
        return super().__lt__(other)

class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, num_value): super().__init__(text); self.num_value = num_value
    def __lt__(self, other): return self.num_value < other.num_value if isinstance(other, NumericTableWidgetItem) else super().__lt__(other)

class BoolTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, bool_value): super().__init__(text); self.bool_value = bool_value
    def __lt__(self, other): return self.bool_value < other.bool_value if isinstance(other, BoolTableWidgetItem) else super().__lt__(other)

