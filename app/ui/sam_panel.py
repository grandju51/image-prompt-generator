from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.config_manager import AppConfig, ConfigManager, save_config
from app.ui.log_widget import LogWidget


class SamPanel(QWidget):
    """
    SAM3 masking panel.

    Signals
    -------
    run_selected_requested(labels)  – run SAM3 on selected images
    run_batch_requested(labels)     – run SAM3 on all images
    cancel_requested()
    """

    run_selected_requested = Signal(list)   # list[str]
    run_batch_requested = Signal(list)      # list[str]
    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    # ------------------------------------------------------------------ #
    #  Build UI
    # ------------------------------------------------------------------ #

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)

        layout.addWidget(self._build_labels_group())
        layout.addWidget(self._build_options_group())
        layout.addWidget(self._build_actions_group())
        layout.addWidget(self._build_log_group())
        layout.addStretch()

    def _build_labels_group(self) -> QGroupBox:
        box = QGroupBox("Ce que SAM3 doit segmenter")
        form = QFormLayout(box)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setSpacing(8)

        # Prominent labels input
        self._labels_edit = QLineEdit()
        self._labels_edit.setPlaceholderText(
            "Ex : face, hands    |    logo, text    |    car, wheel, person"
        )
        self._labels_edit.setMinimumHeight(30)
        font = self._labels_edit.font()
        font.setPointSize(font.pointSize() + 1)
        self._labels_edit.setFont(font)
        self._labels_edit.setToolTip(
            "Labels séparés par des virgules.\n"
            "Chaque label génère un fichier PNG séparé :\n"
            "  image-face-masklabel.png\n"
            "  image-hands-masklabel.png"
        )
        form.addRow("Labels :", self._labels_edit)

        self._confidence = QDoubleSpinBox()
        self._confidence.setRange(0.05, 0.95)
        self._confidence.setSingleStep(0.05)
        self._confidence.setDecimals(2)
        self._confidence.setValue(0.5)
        self._confidence.setToolTip(
            "Seuil de confiance de détection.\n"
            "Plus bas = plus de détections (risque de faux positifs).\n"
            "Plus haut = détections plus précises."
        )
        form.addRow("Confiance :", self._confidence)

        # Coordination with LLM
        self._also_with_llm = QCheckBox(
            "Lancer SAM3 automatiquement avec le batch LLM"
        )
        self._also_with_llm.setToolTip(
            "Si coché, SAM3 s'exécutera sur chaque image\n"
            "en même temps que la génération des prompts LLM."
        )
        form.addRow(self._also_with_llm)

        self._labels_edit.textChanged.connect(self._on_change)
        self._confidence.valueChanged.connect(self._on_change)
        self._also_with_llm.stateChanged.connect(self._on_change)

        return box

    def _build_options_group(self) -> QGroupBox:
        box = QGroupBox("Options du masque")
        form = QFormLayout(box)
        form.setSpacing(6)

        opacity_row = QHBoxLayout()
        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(0, 255)
        self._opacity_slider.setValue(200)
        self._opacity_slider.setToolTip(
            "Alpha de la zone sélectionnée (0 = transparent, 255 = opaque)"
        )
        self._opacity_label = QLabel("200")
        self._opacity_label.setMinimumWidth(28)
        opacity_row.addWidget(self._opacity_slider)
        opacity_row.addWidget(self._opacity_label)
        form.addRow("Opacité :", opacity_row)

        self._invert = QCheckBox(
            "Inverser — masquer le fond, garder la sélection visible"
        )
        form.addRow(self._invert)

        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(str(v))
        )
        self._opacity_slider.valueChanged.connect(self._on_change)
        self._invert.stateChanged.connect(self._on_change)

        return box

    def _build_actions_group(self) -> QGroupBox:
        box = QGroupBox()
        al = QVBoxLayout(box)
        al.setSpacing(6)

        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        self._progress.setVisible(False)
        al.addWidget(self._progress)

        btn_row = QHBoxLayout()
        self._run_sel_btn = QPushButton("▶  Run — Sélection")
        self._run_sel_btn.setToolTip("Lancer SAM3 sur les images sélectionnées")
        self._run_sel_btn.setMinimumHeight(28)
        self._run_sel_btn.clicked.connect(self._on_run_selected)

        self._run_batch_btn = QPushButton("▶▶  Run — Batch")
        self._run_batch_btn.setToolTip("Lancer SAM3 sur toutes les images de la liste")
        self._run_batch_btn.setMinimumHeight(28)
        self._run_batch_btn.clicked.connect(self._on_run_batch)

        btn_row.addWidget(self._run_sel_btn)
        btn_row.addWidget(self._run_batch_btn)
        al.addLayout(btn_row)

        self._cancel_btn = QPushButton("⏹  Annuler")
        self._cancel_btn.clicked.connect(self.cancel_requested)
        self._cancel_btn.setEnabled(False)
        al.addWidget(self._cancel_btn)

        return box

    def _build_log_group(self) -> QGroupBox:
        box = QGroupBox("Log SAM3")
        ll = QVBoxLayout(box)
        ll.setContentsMargins(4, 4, 4, 4)
        self.log_widget = LogWidget()
        ll.addWidget(self.log_widget)
        box.setMaximumHeight(200)
        return box

    # ------------------------------------------------------------------ #
    #  Slots
    # ------------------------------------------------------------------ #

    def _get_labels(self) -> list[str]:
        text = self._labels_edit.text().strip()
        return [lbl.strip() for lbl in text.split(",") if lbl.strip()]

    def _on_run_selected(self) -> None:
        labels = self._get_labels()
        if not labels:
            self.log_widget.append_log(
                "Aucun label saisi. Exemple : face, hands", "warning"
            )
            return
        self.run_selected_requested.emit(labels)

    def _on_run_batch(self) -> None:
        labels = self._get_labels()
        if not labels:
            self.log_widget.append_log(
                "Aucun label saisi. Exemple : face, hands", "warning"
            )
            return
        self.run_batch_requested.emit(labels)

    def _on_change(self, *_) -> None:
        cfg = ConfigManager.instance().config
        cfg.sam3_labels = self._labels_edit.text().strip()
        cfg.sam3_mask_opacity = self._opacity_slider.value()
        cfg.sam3_mask_invert = self._invert.isChecked()
        cfg.sam3_confidence = self._confidence.value()
        cfg.sam3_enabled = self._also_with_llm.isChecked()
        save_config()

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def load_from_config(self, config: AppConfig) -> None:
        self._labels_edit.setText(config.sam3_labels)
        self._opacity_slider.setValue(config.sam3_mask_opacity)
        self._opacity_label.setText(str(config.sam3_mask_opacity))
        self._invert.setChecked(config.sam3_mask_invert)
        self._confidence.setValue(config.sam3_confidence)
        self._also_with_llm.setChecked(config.sam3_enabled)

    def set_running(self, running: bool) -> None:
        self._run_sel_btn.setEnabled(not running)
        self._run_batch_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        self._progress.setVisible(running)
        if not running:
            self._progress.setValue(0)

    def update_progress(self, current: int, total: int) -> None:
        self._progress.setMaximum(total)
        self._progress.setValue(current)
        self._progress.setFormat(f"{current} / {total}")

    @property
    def labels_from_ui(self) -> list[str]:
        return self._get_labels()
