from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.config_manager import ConfigManager
from app.ui.log_widget import LogWidget
from app.ui.sam_panel import SamPanel
from app.ui.settings_widget import SettingsWidget


class ControlPanel(QWidget):
    # LLM signals
    start_batch_requested = Signal()
    cancel_requested = Signal()
    retry_failed_requested = Signal()
    process_selected_requested = Signal()
    test_connection_requested = Signal()
    settings_changed = Signal(object)  # AppConfig

    # SAM signals (forwarded from SamPanel)
    sam_run_selected_requested = Signal(list)   # list[str] labels
    sam_run_batch_requested = Signal(list)      # list[str] labels
    sam_cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        tabs = QTabWidget()
        tabs.addTab(self._build_llm_tab(), "LLM")
        tabs.addTab(self._build_sam_tab(), "SAM Masking")
        root.addWidget(tabs)

    # ------------------------------------------------------------------ #
    #  LLM tab
    # ------------------------------------------------------------------ #

    def _build_llm_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)

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
        layout.addWidget(scroll, 1)

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

        layout.addWidget(action_box)

        # ── Log area ────────────────────────────────────────────────────
        log_box = QGroupBox("Log")
        ll = QVBoxLayout(log_box)
        ll.setContentsMargins(4, 4, 4, 4)
        self.log_widget = LogWidget()
        ll.addWidget(self.log_widget)
        log_box.setMaximumHeight(200)
        layout.addWidget(log_box)

        return tab

    # ------------------------------------------------------------------ #
    #  SAM tab
    # ------------------------------------------------------------------ #

    def _build_sam_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._sam_panel = SamPanel()
        self._sam_panel.run_selected_requested.connect(self.sam_run_selected_requested)
        self._sam_panel.run_batch_requested.connect(self.sam_run_batch_requested)
        self._sam_panel.cancel_requested.connect(self.sam_cancel_requested)

        scroll.setWidget(self._sam_panel)
        layout.addWidget(scroll)

        return tab

    # ------------------------------------------------------------------ #
    #  Public API — LLM
    # ------------------------------------------------------------------ #

    def load_settings(self):
        cfg = ConfigManager.instance().config
        self._settings.load_from_config(cfg)
        self._sam_panel.load_from_config(cfg)

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

    # ------------------------------------------------------------------ #
    #  Public API — SAM
    # ------------------------------------------------------------------ #

    def set_sam_running(self, running: bool):
        self._sam_panel.set_running(running)

    def update_sam_progress(self, current: int, total: int):
        self._sam_panel.update_progress(current, total)

    @property
    def sam_log_widget(self) -> LogWidget:
        return self._sam_panel.log_widget
