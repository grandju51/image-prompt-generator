from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.config_manager import ConfigManager
from app.ui.log_widget import LogWidget
from app.ui.settings_widget import SettingsWidget


class ControlPanel(QWidget):
    start_batch_requested = Signal()
    cancel_requested = Signal()
    retry_failed_requested = Signal()
    process_selected_requested = Signal()
    test_connection_requested = Signal()
    settings_changed = Signal(object)  # AppConfig

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ── Scrollable settings ─────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)

        self._settings = SettingsWidget()
        self._settings.settings_changed.connect(self.settings_changed)
        self._settings.test_connection_requested.connect(self.test_connection_requested)
        cl.addWidget(self._settings)

        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # ── Batch action buttons ────────────────────────────────────────
        action_box = QGroupBox()
        al = QVBoxLayout(action_box)
        al.setSpacing(4)

        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        self._progress.setVisible(False)
        al.addWidget(self._progress)

        row1 = QHBoxLayout()
        self._start_btn = QPushButton("Start Batch")
        self._start_btn.clicked.connect(self.start_batch_requested)
        self._proc_sel_btn = QPushButton("Process Selected")
        self._proc_sel_btn.clicked.connect(self.process_selected_requested)
        row1.addWidget(self._start_btn)
        row1.addWidget(self._proc_sel_btn)
        al.addLayout(row1)

        row2 = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.cancel_requested)
        self._cancel_btn.setEnabled(False)
        self._retry_btn = QPushButton("Retry Failed")
        self._retry_btn.clicked.connect(self.retry_failed_requested)
        self._retry_btn.setEnabled(False)
        row2.addWidget(self._cancel_btn)
        row2.addWidget(self._retry_btn)
        al.addLayout(row2)

        root.addWidget(action_box)

        # ── Log area ────────────────────────────────────────────────────
        log_box = QGroupBox("Log")
        ll = QVBoxLayout(log_box)
        ll.setContentsMargins(4, 4, 4, 4)
        self.log_widget = LogWidget()
        ll.addWidget(self.log_widget)
        log_box.setMaximumHeight(200)
        root.addWidget(log_box)

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def load_settings(self):
        self._settings.load_from_config(ConfigManager.instance().config)

    def set_batch_running(self, running: bool):
        self._start_btn.setEnabled(not running)
        self._proc_sel_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._progress.setVisible(running)
        if not running:
            self._progress.setValue(0)

    def update_progress(self, current: int, total: int):
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._progress.setFormat(f"{current} / {total}")

    def enable_retry_button(self):
        self._retry_btn.setEnabled(True)

    def disable_retry_button(self):
        self._retry_btn.setEnabled(False)

    def show_connection_result(self, success: bool, message: str, models: list):
        self._settings.show_connection_result(success, message, models)

    def set_testing_connection(self):
        self._settings.set_testing()
