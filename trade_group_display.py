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
        readable_headers = ["Entry Time", "Exit Time", "Max Size", "Long/Short",  "Points", "Amount", "Cumulative", "Streak"]
        num_rows = len(trade_groups)
        num_cols = len(readable_headers)
        table.setRowCount(num_rows)
        table.setColumnCount(num_cols)
        table.setHorizontalHeaderLabels(readable_headers)

        def apply_gradient_to_column(
            table: QTableWidget,
            column_index: int,
            color_positive: QColor = QColor(100, 255, 100),
            color_negative: QColor = QColor(255, 100, 100)
        ):
            values = []

            # Collect numeric values from the column
            for row in range(table.rowCount()):
                item = table.item(row, column_index)
                if not item:
                    values.append(0.0)
                    continue
                try:
                    value = float(item.data(Qt.ItemDataRole.UserRole))
                except (ValueError, TypeError):
                    value = 0.0
                values.append(value)

            if not values:
                return

            max_abs_val = max(abs(v) for v in values) or 1

            # Apply background gradient
            for row, val in enumerate(values):
                item = table.item(row, column_index)
                if not item:
                    continue

                norm = abs(val) / max_abs_val

                if val > 0:
                    # Interpolate between white and color_positive
                    r = int(255 - (255 - color_positive.red()) * norm)
                    g = int(255 - (255 - color_positive.green()) * norm)
                    b = int(255 - (255 - color_positive.blue()) * norm)
                elif val < 0:
                    # Interpolate between white and color_negative
                    r = int(255 - (255 - color_negative.red()) * norm)
                    g = int(255 - (255 - color_negative.green()) * norm)
                    b = int(255 - (255 - color_negative.blue()) * norm)
                else:
                    r = g = b = 255  # White

                item.setBackground(QBrush(QColor(r, g, b)))
                item.setForeground(QBrush(QColor(0, 0, 0)))  # Black text

        for row_idx, trade_group in enumerate(trade_groups):
            val1 = trade_group.entry_time; item1 = DateTimeTableWidgetItem(format_datetime(val1), val1); item1.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter); table.setItem(row_idx, 0, item1)
            val2 = trade_group.exit_time; item2 = DateTimeTableWidgetItem(format_datetime(val2), val2); item2.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter); table.setItem(row_idx, 1, item2)
            
            val3 = trade_group.max_trade_size * (1 if trade_group.entry_is_long else -1)
            item3 = NumericTableWidgetItem(format_float_size(val3), val3)
            item3.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item3.setData(Qt.ItemDataRole.UserRole, val3)  # Store numeric value for later access
            table.setItem(row_idx, 2, item3)
            apply_gradient_to_column(table, 2, QColor(100, 100, 255), QColor(255, 165, 100))

            val0 = trade_group.entry_is_long; item0 = QTableWidgetItem("Long" if val0 else "Short"); item0.setTextAlignment(Qt.AlignmentFlag.AlignCenter); table.setItem(row_idx, 3, item0)

            val4 = trade_group.trade_point; item4 = NumericTableWidgetItem(format_float_points(val4), val4); item4.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item4.setData(Qt.ItemDataRole.UserRole, val4)  # Store numeric value for later access
            table.setItem(row_idx, 4, item4)
            apply_gradient_to_column(table, 4)

            val5 = trade_group.trade_amount
            item5 = NumericTableWidgetItem(format_float_amount(val5), val5)
            item5.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item5.setData(Qt.ItemDataRole.UserRole, val5)  # Store numeric value for later access
            table.setItem(row_idx, 5, item5)
            apply_gradient_to_column(table, 5)

            # Add Cumulative column (we will update this later)
            item6 = QTableWidgetItem("")  # Placeholder
            item6.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item6.setForeground(QBrush(QColor(0, 0, 0)))
            item6.setFlags(item6.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row_idx, 6, item6)

            # Add Cumulative Streak column (we will update this later)
            item7 = QTableWidgetItem("")  # Placeholder
            item7.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item7.setForeground(QBrush(QColor(0, 0, 0)))
            item7.setFlags(item7.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row_idx, 7, item7)

            for col_idx in range(num_cols):
                item = table.item(row_idx, col_idx); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable) if item else None
        
        table.setSortingEnabled(True)

        def update_cumulative_column(table: QTableWidget):
            cumulative = 0.0
            cumulative_values = []

            # First pass to collect cumulative values
            for row in range(table.rowCount()):
                item = table.item(row, 5)
                if not item:
                    cumulative_values.append(0.0)
                    continue
                try:
                    value = float(item.data(Qt.ItemDataRole.UserRole))
                except (ValueError, TypeError):
                    value = 0.0
                cumulative += value
                cumulative_values.append(cumulative)

            if not cumulative_values:
                return

            # Second pass: set text and background color
            for row, cum_val in enumerate(cumulative_values):
                item = table.item(row, 6)
                if not item:
                    continue
                item.setText(format_float_cumulative_amount(cum_val))
                item.setData(Qt.ItemDataRole.UserRole, cum_val)  # Store numeric value for later access

            apply_gradient_to_column(table, 6)

        def update_streak_cumulative_column(table: QTableWidget, points_col: int, streak_col: int):
            prev_sign = 0
            streak_total = 0.0
            streak_values = []

            for row in range(table.rowCount()):
                item = table.item(row, points_col)
                if not item:
                    streak_values.append(0.0)
                    continue

                try:
                    val = float(item.data(Qt.ItemDataRole.UserRole))
                except (ValueError, TypeError):
                    val = 0.0

                current_sign = 1 if val > 0 else -1 if val < 0 else 0

                # Reset streak if sign changes (ignores 0 for reset purposes)
                if current_sign != 0 and current_sign != prev_sign:
                    streak_total = 0.0

                streak_total += val
                streak_values.append(streak_total)
                prev_sign = current_sign if current_sign != 0 else prev_sign

            for row, val in enumerate(streak_values):
                item = QTableWidgetItem(format_float_cumulative_streak_amount(val))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setData(Qt.ItemDataRole.UserRole, val)
                item.setForeground(QBrush(QColor(150, 255, 150) if val > 0 else QColor(255, 150, 150) if val < 0 else QColor(255, 255, 255)))
                table.setItem(row, streak_col, item)

        def update_cumulative_columns(table: QTableWidget, point_col_index:int, streak_col_index: int):
            update_cumulative_column(table)
            update_streak_cumulative_column(table, point_col_index, streak_col_index)

        table.horizontalHeader().sortIndicatorChanged.connect(lambda _, __: update_cumulative_columns(table, 5, 7))
        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        table.setFont(QFont("Courier New", 20))
        update_cumulative_columns(table, 5, 7)

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
def format_float_size(val): return f"{int(val):+}"
def format_float_points(val): return f"{val:.2f}"
def format_float_amount(val): return f"{int(val):,}"
def format_float_cumulative_amount(val): return f"{int(val):,}"
def format_float_cumulative_streak_amount(val): return f"{int(val):,}"

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

