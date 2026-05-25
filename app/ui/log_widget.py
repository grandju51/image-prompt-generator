from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QHBoxLayout, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

_LEVEL_COLORS = {
    "info": "#AAAAAA",
    "warning": "#FFA500",
    "error": "#FF6B6B",
    "success": "#5CB85C",
}


class LogWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(55)
        clear_btn.clicked.connect(self._text.clear if hasattr(self, "_text") else lambda: None)
        btn_row.addWidget(clear_btn)

        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(2000)
        font = self._text.font()
        font.setFamily("Monospace")
        font.setPointSize(8)
        self._text.setFont(font)

        clear_btn.clicked.disconnect()
        clear_btn.clicked.connect(self._text.clear)

        layout.addLayout(btn_row)
        layout.addWidget(self._text)

    def append_log(self, message: str, level: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        color = _LEVEL_COLORS.get(level, _LEVEL_COLORS["info"])
        label = level.upper().ljust(7)
        html = f'<span style="color:{color};font-family:monospace">[{ts}] {label} {message}</span>'
        self._text.appendHtml(html)
        self._text.moveCursor(QTextCursor.MoveOperation.End)
