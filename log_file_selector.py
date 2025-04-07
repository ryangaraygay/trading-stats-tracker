import sys
import os
import re
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLabel
)
from PyQt6.QtGui import QFont

def get_most_recent_file(directory, pattern):
    files = [f for f in os.listdir(directory) if re.match(pattern, f)]
    if not files:
        return None
    files_with_paths = [os.path.join(directory, f) for f in files]
    most_recent = max(files_with_paths, key=os.path.getmtime)
    return most_recent

def get_all_matching_files(directory, pattern):
    files = [f for f in os.listdir(directory) if re.match(pattern, f)]
    files_with_paths = [os.path.join(directory, f) for f in files]
    files_with_paths.sort(key=os.path.getmtime, reverse=True)
    return files_with_paths

class LogFileSelector(QDialog):
    def __init__(self, directory, pattern, parent=None):
        super().__init__(parent)
        self.directory = directory
        self.pattern = pattern
        self.selected_files = []
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()

        self.most_recent_label = QLabel("Most Recent File:")
        self.most_recent_label.setFont(QFont("Arial", 27))
        layout.addWidget(self.most_recent_label)

        most_recent_file = get_most_recent_file(self.directory, self.pattern)
        if most_recent_file:
            self.most_recent_label.setText(f"Most Recent File: {most_recent_file}")
            self.selected_files.append(most_recent_file)
        else:
            self.most_recent_label.setText("Most Recent File: None Found")

        self.list_widget = QListWidget()
        self.list_widget.setFont(QFont("Arial", 27))
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.list_widget)

        self.populate_list()

        button_style = """
            QPushButton {
                background-color: gray;
                color: black;
                border-radius: 5px;
                font-size: 16pt;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: lightgray;
            }
        """

        self.select_button = QPushButton("Select Files")
        self.select_button.setStyleSheet(button_style)
        self.select_button.clicked.connect(self.select_files)
        layout.addWidget(self.select_button)

        self.setLayout(layout)
        self.setWindowTitle("Log File Selector")

    def populate_list(self):
        self.list_widget.clear()
        all_files = get_all_matching_files(self.directory, self.pattern)
        for file in all_files:
            item = QListWidgetItem(file)
            self.list_widget.addItem(item)
            if file in self.selected_files:
                item.setSelected(True)

    def select_files(self):
        self.selected_files = [item.text() for item in self.list_widget.selectedItems()]
        self.accept()

    def get_selected_files(self):
        return self.selected_files
