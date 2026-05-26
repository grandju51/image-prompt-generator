from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from app.config_manager import AppConfig, ConfigManager, save_config
from app.constants import (
    FrameExtractionMode,
    IMAGE_SIZE_PRESETS,
    OverwritePolicy,
    PayloadMode,
    VideoMode,
)


class SettingsWidget(QWidget):
    settings_changed = Signal(object)       # AppConfig
    test_connection_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._setup_ui()

    # ------------------------------------------------------------------ #
    #  Build UI
    # ------------------------------------------------------------------ #

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._build_api_group())
        layout.addWidget(self._build_generation_group())
        layout.addWidget(self._build_image_group())
        layout.addWidget(self._build_video_group())
        layout.addWidget(self._build_behavior_group())
        layout.addWidget(self._build_cleanup_group())
        layout.addWidget(self._build_sam_group())

    def _build_api_group(self) -> QGroupBox:
        box = QGroupBox("API Connection")
        form = QFormLayout(box)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self._url = QLineEdit()
        self._url.setPlaceholderText("http://localhost:1234/v1")
        form.addRow("Base URL:", self._url)

        self._model = QLineEdit()
        self._model.setPlaceholderText("local-model")
        form.addRow("Model:", self._model)

        self._api_key = QLineEdit()
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setPlaceholderText("Optional — leave empty if not required")
        form.addRow("API Key:", self._api_key)

        self._payload_mode = QComboBox()
        self._payload_mode.addItem("Auto (try Data URI, fallback Raw)", PayloadMode.AUTO.value)
        self._payload_mode.addItem("Data URI — recommended", PayloadMode.DATA_URI.value)
        self._payload_mode.addItem("Raw Base64 — experimental", PayloadMode.RAW_BASE64.value)
        form.addRow("Payload mode:", self._payload_mode)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.clicked.connect(self.test_connection_requested)
        self._test_status = QLabel("")
        self._test_status.setWordWrap(True)
        test_row.addWidget(self._test_btn)
        test_row.addWidget(self._test_status, 1)
        form.addRow("", test_row)

        self._url.textChanged.connect(self._on_change)
        self._model.textChanged.connect(self._on_change)
        self._api_key.textChanged.connect(self._on_change)
        self._payload_mode.currentIndexChanged.connect(self._on_change)
        return box

    def _build_generation_group(self) -> QGroupBox:
        box = QGroupBox("Generation")
        form = QFormLayout(box)

        self._system_prompt = QTextEdit()
        self._system_prompt.setMaximumHeight(65)
        self._system_prompt.setPlaceholderText("System prompt sent to the model...")
        form.addRow("System prompt:", self._system_prompt)

        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.05)
        self._temperature.setDecimals(2)
        form.addRow("Temperature:", self._temperature)

        self._top_p = QDoubleSpinBox()
        self._top_p.setRange(0.0, 1.0)
        self._top_p.setSingleStep(0.05)
        self._top_p.setDecimals(2)
        form.addRow("Top P:", self._top_p)

        # Optional: Top K
        self._use_top_k = QCheckBox("Enable Top K")
        self._top_k = QSpinBox()
        self._top_k.setRange(1, 1000)
        row_topk = QHBoxLayout()
        row_topk.addWidget(self._use_top_k)
        row_topk.addWidget(self._top_k)
        row_topk.addStretch()
        form.addRow("", row_topk)

        # Optional: Repetition penalty
        self._use_rep_pen = QCheckBox("Enable Rep. Penalty")
        self._rep_pen = QDoubleSpinBox()
        self._rep_pen.setRange(0.5, 3.0)
        self._rep_pen.setSingleStep(0.05)
        self._rep_pen.setDecimals(2)
        row_rep = QHBoxLayout()
        row_rep.addWidget(self._use_rep_pen)
        row_rep.addWidget(self._rep_pen)
        row_rep.addStretch()
        form.addRow("", row_rep)

        # Optional: Max tokens
        self._use_max_tokens = QCheckBox("Limit Max Tokens")
        self._max_tokens = QSpinBox()
        self._max_tokens.setRange(1, 32768)
        self._max_tokens.setSingleStep(128)
        row_mt = QHBoxLayout()
        row_mt.addWidget(self._use_max_tokens)
        row_mt.addWidget(self._max_tokens)
        row_mt.addStretch()
        form.addRow("", row_mt)

        # Toggle enabled state
        self._use_top_k.stateChanged.connect(lambda s: self._top_k.setEnabled(bool(s)))
        self._use_rep_pen.stateChanged.connect(lambda s: self._rep_pen.setEnabled(bool(s)))
        self._use_max_tokens.stateChanged.connect(lambda s: self._max_tokens.setEnabled(bool(s)))

        for w in [
            self._system_prompt, self._temperature, self._top_p,
            self._use_top_k, self._top_k, self._use_rep_pen, self._rep_pen,
            self._use_max_tokens, self._max_tokens,
        ]:
            self._connect_widget(w)

        return box

    def _build_image_group(self) -> QGroupBox:
        box = QGroupBox("Image")
        form = QFormLayout(box)

        self._image_size = QComboBox()
        for s in IMAGE_SIZE_PRESETS:
            self._image_size.addItem(f"{s}px", s)
        self._image_size.addItem("Original (no resize)", -1)
        self._image_size.addItem("Custom…", 0)

        self._image_size_custom = QSpinBox()
        self._image_size_custom.setRange(32, 8192)
        self._image_size_custom.setSuffix(" px")
        self._image_size_custom.setEnabled(False)

        size_row = QHBoxLayout()
        size_row.addWidget(self._image_size)
        size_row.addWidget(self._image_size_custom)
        form.addRow("Transmit size:", size_row)

        self._image_size.currentIndexChanged.connect(self._on_size_change)
        self._image_size_custom.valueChanged.connect(self._on_change)
        return box

    def _build_video_group(self) -> QGroupBox:
        box = QGroupBox("Video")
        form = QFormLayout(box)

        self._video_mode = QComboBox()
        self._video_mode.addItem("Frame extraction  (default)", VideoMode.FRAME_EXTRACTION.value)
        self._video_mode.addItem("Native video  ⚠ Experimental", VideoMode.NATIVE_VIDEO.value)
        form.addRow("Mode:", self._video_mode)

        self._frame_mode = QComboBox()
        self._frame_mode.addItem("Every N seconds", FrameExtractionMode.EVERY_N_SECONDS.value)
        self._frame_mode.addItem("Every N frames", FrameExtractionMode.EVERY_N_FRAMES.value)
        self._frame_mode.addItem("Max N frames (evenly spread)", FrameExtractionMode.MAX_N_FRAMES.value)
        form.addRow("Extract:", self._frame_mode)

        self._frame_interval = QDoubleSpinBox()
        self._frame_interval.setRange(0.1, 3600.0)
        self._frame_interval.setSingleStep(0.5)
        self._frame_interval.setSuffix(" s")
        form.addRow("Interval:", self._frame_interval)

        self._frame_step = QSpinBox()
        self._frame_step.setRange(1, 10000)
        self._frame_step.setSuffix(" frames")
        form.addRow("Frame step:", self._frame_step)

        self._frame_max = QSpinBox()
        self._frame_max.setRange(1, 200)
        self._frame_max.setSuffix(" max")
        form.addRow("Max frames:", self._frame_max)

        for w in [self._video_mode, self._frame_mode, self._frame_interval,
                  self._frame_step, self._frame_max]:
            self._connect_widget(w)

        return box

    def _build_behavior_group(self) -> QGroupBox:
        box = QGroupBox("File Behavior")
        form = QFormLayout(box)

        self._overwrite = QComboBox()
        self._overwrite.addItem("Skip existing .txt files", OverwritePolicy.SKIP.value)
        self._overwrite.addItem("Overwrite existing .txt files", OverwritePolicy.OVERWRITE.value)
        self._overwrite.addItem("Ask once per batch", OverwritePolicy.ASK_BATCH.value)
        form.addRow("Existing .txt:", self._overwrite)

        self._overwrite.currentIndexChanged.connect(self._on_change)

        self._concurrency = QSpinBox()
        self._concurrency.setRange(1, 16)
        self._concurrency.setSuffix(" parallel")
        self._concurrency.setToolTip(
            "Number of images analysed simultaneously.\n"
            "Start with 2–4. Too many may overload the server."
        )
        form.addRow("Batch concurrency:", self._concurrency)
        self._concurrency.valueChanged.connect(self._on_change)

        return box

    def _build_cleanup_group(self) -> QGroupBox:
        from PySide6.QtWidgets import QPlainTextEdit
        box = QGroupBox("Output Cleanup")
        form = QFormLayout(box)

        self._use_markers = QCheckBox("Strip text before first marker")
        form.addRow(self._use_markers)

        self._markers_edit = QPlainTextEdit()
        self._markers_edit.setPlaceholderText(
            "One marker per line.\nExample:\n**Prompt:**\n**Prompt**\nPrompt:"
        )
        self._markers_edit.setMaximumHeight(90)
        self._markers_edit.setToolTip(
            "When the LLM output contains one of these markers, everything before it "
            "(including the marker itself) will be stripped. The first matching marker wins."
        )
        form.addRow("Markers:", self._markers_edit)

        self._use_markers.stateChanged.connect(
            lambda s: self._markers_edit.setEnabled(bool(s))
        )
        self._use_markers.stateChanged.connect(self._on_change)
        self._markers_edit.textChanged.connect(self._on_change)
        return box

    def _build_sam_group(self) -> QGroupBox:
        box = QGroupBox("SAM3 — Modèle")
        form = QFormLayout(box)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        # Model directory row with browse button
        self._sam_model_dir = QLineEdit()
        self._sam_model_dir.setPlaceholderText("/home/julien/IA/ComfyUI/models/sam3")
        browse_model = QPushButton("…")
        browse_model.setFixedWidth(28)
        browse_model.setToolTip("Dossier contenant sam3.safetensors ou sam3.pt")
        browse_model.clicked.connect(self._browse_sam_model_dir)
        row_model = QHBoxLayout()
        row_model.addWidget(self._sam_model_dir)
        row_model.addWidget(browse_model)
        form.addRow("Dossier modèle :", row_model)

        self._sam_model_file = QLineEdit()
        self._sam_model_file.setPlaceholderText("sam3.safetensors")
        form.addRow("Fichier modèle :", self._sam_model_file)

        self._sam_device = QComboBox()
        self._sam_device.addItem("Auto (CUDA si disponible)", "auto")
        self._sam_device.addItem("CUDA (GPU)", "cuda")
        self._sam_device.addItem("CPU", "cpu")
        form.addRow("Device :", self._sam_device)

        self._sam_confidence = QDoubleSpinBox()
        self._sam_confidence.setRange(0.05, 0.95)
        self._sam_confidence.setSingleStep(0.05)
        self._sam_confidence.setDecimals(2)
        self._sam_confidence.setToolTip(
            "Seuil de confiance par défaut (aussi réglable dans l'onglet SAM Masking)"
        )
        form.addRow("Seuil détection :", self._sam_confidence)

        self._sam_model_dir.textChanged.connect(self._on_change)
        self._sam_model_file.textChanged.connect(self._on_change)
        self._sam_device.currentIndexChanged.connect(self._on_change)
        self._sam_confidence.valueChanged.connect(self._on_change)

        return box

    def _browse_sam_model_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Dossier modèle SAM3", self._sam_model_dir.text() or "/"
        )
        if folder:
            self._sam_model_dir.setText(folder)

    # ------------------------------------------------------------------ #
    #  Load / save
    # ------------------------------------------------------------------ #

    def load_from_config(self, config: AppConfig):
        self._loading = True
        try:
            self._url.setText(config.api_base_url)
            self._model.setText(config.model_name)
            self._api_key.setText(config.api_key)
            self._set_combo(self._payload_mode, config.payload_mode)

            self._system_prompt.setPlainText(config.system_prompt)
            self._temperature.setValue(config.temperature)
            self._top_p.setValue(config.top_p)
            self._use_top_k.setChecked(config.use_top_k)
            self._top_k.setValue(config.top_k)
            self._top_k.setEnabled(config.use_top_k)
            self._use_rep_pen.setChecked(config.use_repetition_penalty)
            self._rep_pen.setValue(config.repetition_penalty)
            self._rep_pen.setEnabled(config.use_repetition_penalty)
            self._use_max_tokens.setChecked(config.use_max_tokens)
            self._max_tokens.setValue(config.max_tokens)
            self._max_tokens.setEnabled(config.use_max_tokens)

            self._set_combo(self._image_size, config.image_size)
            self._image_size_custom.setValue(config.image_size_custom)
            self._image_size_custom.setEnabled(config.image_size == 0)

            self._set_combo(self._video_mode, config.video_mode)
            self._set_combo(self._frame_mode, config.frame_mode)
            self._frame_interval.setValue(config.frame_every_n_seconds)
            self._frame_step.setValue(config.frame_every_n_frames)
            self._frame_max.setValue(config.frame_max_n)

            self._set_combo(self._overwrite, config.overwrite_policy)
            self._concurrency.setValue(config.batch_concurrency)

            self._use_markers.setChecked(config.use_output_markers)
            self._markers_edit.setPlainText("\n".join(config.output_markers))
            self._markers_edit.setEnabled(config.use_output_markers)

            self._sam_model_dir.setText(config.sam3_model_dir)
            self._sam_model_file.setText(config.sam3_model_file)
            self._set_combo(self._sam_device, config.sam3_device)
            self._sam_confidence.setValue(config.sam3_confidence)
        finally:
            self._loading = False

    def _set_combo(self, combo: QComboBox, value):
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------ #
    #  Change handlers
    # ------------------------------------------------------------------ #

    def _connect_widget(self, w):
        if isinstance(w, QTextEdit):
            w.textChanged.connect(self._on_change)
        elif isinstance(w, (QDoubleSpinBox, QSpinBox)):
            w.valueChanged.connect(self._on_change)
        elif isinstance(w, QCheckBox):
            w.stateChanged.connect(self._on_change)
        elif isinstance(w, QComboBox):
            w.currentIndexChanged.connect(self._on_change)

    def _on_size_change(self, *_):
        is_custom = self._image_size.currentData() == 0
        self._image_size_custom.setEnabled(is_custom)
        self._on_change()

    def _on_change(self, *_):
        if self._loading:
            return
        cfg = ConfigManager.instance().config
        cfg.api_base_url = self._url.text().strip()
        cfg.model_name = self._model.text().strip()
        cfg.api_key = self._api_key.text()
        cfg.payload_mode = self._payload_mode.currentData()
        cfg.system_prompt = self._system_prompt.toPlainText()
        cfg.temperature = self._temperature.value()
        cfg.top_p = self._top_p.value()
        cfg.use_top_k = self._use_top_k.isChecked()
        cfg.top_k = self._top_k.value()
        cfg.use_repetition_penalty = self._use_rep_pen.isChecked()
        cfg.repetition_penalty = self._rep_pen.value()
        cfg.use_max_tokens = self._use_max_tokens.isChecked()
        cfg.max_tokens = self._max_tokens.value()
        cfg.image_size = self._image_size.currentData()
        cfg.image_size_custom = self._image_size_custom.value()
        cfg.video_mode = self._video_mode.currentData()
        cfg.frame_mode = self._frame_mode.currentData()
        cfg.frame_every_n_seconds = self._frame_interval.value()
        cfg.frame_every_n_frames = self._frame_step.value()
        cfg.frame_max_n = self._frame_max.value()
        cfg.overwrite_policy = self._overwrite.currentData()
        cfg.batch_concurrency = self._concurrency.value()
        cfg.use_output_markers = self._use_markers.isChecked()
        cfg.output_markers = [
            line for line in self._markers_edit.toPlainText().splitlines() if line.strip()
        ]
        cfg.sam3_model_dir = self._sam_model_dir.text().strip()
        cfg.sam3_model_file = self._sam_model_file.text().strip()
        cfg.sam3_device = self._sam_device.currentData()
        cfg.sam3_confidence = self._sam_confidence.value()
        save_config()
        self.settings_changed.emit(cfg)

    # ------------------------------------------------------------------ #
    #  Connection test feedback
    # ------------------------------------------------------------------ #

    def show_connection_result(self, success: bool, message: str, models: list):
        self._test_btn.setEnabled(True)
        self._test_btn.setText("Test Connection")
        color = "#5CB85C" if success else "#D9534F"
        self._test_status.setText(f'<span style="color:{color}">{message}</span>')

        if success and models:
            current = self._model.text().strip()
            # Auto-populate if empty or current model not in the server's list
            if not current or current not in models:
                self._model.setText(models[0])
                self._on_change()

    def set_testing(self):
        self._test_btn.setEnabled(False)
        self._test_btn.setText("Testing…")
        self._test_status.setText('<span style="color:#AAAAAA">Connecting…</span>')
