from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.constants import FileType, ItemStatus
from app.models.file_item import FileItem


class PreviewPanel(QWidget):
    save_requested = Signal(str, object)   # text, FileItem
    regenerate_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_item: FileItem | None = None
        self._current_pixmap: QPixmap | None = None
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(2)

        # ── Vertical splitter: image on top, output on bottom ──────────
        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── Image / video display ───────────────────────────────────────
        self._stack = QStackedWidget()

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._image_label.setStyleSheet("background-color: #1E1E1E; border: 1px solid #3A3A3A;")
        self._stack.addWidget(self._image_label)          # page 0

        self._video_label = QLabel()
        self._video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._video_label.setWordWrap(True)
        self._video_label.setStyleSheet(
            "background-color: #1E1E1E; color: #CCCCCC; border: 1px solid #3A3A3A;"
        )
        self._stack.addWidget(self._video_label)          # page 1

        empty = QLabel("No file selected")
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setStyleSheet("background-color: #1E1E1E; color: #555555;")
        self._stack.addWidget(empty)                      # page 2
        self._stack.setCurrentIndex(2)

        splitter.addWidget(self._stack)

        # ── Output text area ────────────────────────────────────────────
        output_widget = QWidget()
        ol = QVBoxLayout(output_widget)
        ol.setContentsMargins(0, 4, 0, 0)
        ol.setSpacing(4)

        # Toolbar: label + buttons
        toolbar = QHBoxLayout()
        lbl = QLabel("Generated output")
        lbl.setStyleSheet("color: #888888; font-size: 10px;")
        toolbar.addWidget(lbl)
        toolbar.addStretch()
        self._regen_btn = QPushButton("Regenerate")
        self._regen_btn.setFixedHeight(24)
        self._regen_btn.clicked.connect(self.regenerate_requested)
        self._save_btn = QPushButton("Save Text")
        self._save_btn.setFixedHeight(24)
        self._save_btn.clicked.connect(self._on_save)
        toolbar.addWidget(self._regen_btn)
        toolbar.addWidget(self._save_btn)
        ol.addLayout(toolbar)

        self._output_edit = QTextEdit()
        self._output_edit.setPlaceholderText("Generated description will appear here…")
        ol.addWidget(self._output_edit)

        splitter.addWidget(output_widget)
        splitter.setSizes([560, 140])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        root.addWidget(splitter, 1)

        # Info bar
        self._info_label = QLabel("")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet("color: #666666; font-size: 10px;")
        root.addWidget(self._info_label)

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def show_item(self, item: object):
        """Called on list selection change — updates both image and output text."""
        if item is None:
            self._current_item = None
            self._current_pixmap = None
            self._stack.setCurrentIndex(2)
            self._info_label.setText("")
            self._output_edit.clear()
            self._output_edit.setStyleSheet("")
            return

        fi: FileItem = item
        self._current_item = fi

        if fi.file_type == FileType.IMAGE:
            self._load_image(fi)
        else:
            self._show_video_info(fi)

        self._populate_output(fi)

    def show_item_result(self, item: FileItem):
        """Called when a batch item completes — updates output text only."""
        if self._current_item and self._current_item.path == item.path:
            self._populate_output(item)

    def get_current_text(self) -> str:
        return self._output_edit.toPlainText()

    # ------------------------------------------------------------------ #
    #  Internal helpers
    # ------------------------------------------------------------------ #

    def _populate_output(self, fi: FileItem):
        if fi.status == ItemStatus.FAILED:
            self._output_edit.setStyleSheet("color: #FF6B6B;")
            self._output_edit.setPlainText(f"Error: {fi.error_message}")
        else:
            self._output_edit.setStyleSheet("")
            self._output_edit.setPlainText(fi.result_text)

    def _load_image(self, item: FileItem):
        px = QPixmap(str(item.path))
        self._current_pixmap = px if not px.isNull() else None
        self._stack.setCurrentIndex(0)
        # Defer first render so the widget has its final size from the layout engine
        QTimer.singleShot(0, self._render_image)
        if not px.isNull():
            self._info_label.setText(f"{item.path.name}  ·  {px.width()}×{px.height()} px")
        else:
            self._info_label.setText(f"{item.path.name}  (cannot load)")

    def _render_image(self):
        if not self._current_pixmap or self._current_pixmap.isNull():
            self._image_label.setText("Cannot load image")
            return
        w = self._image_label.width() - 8
        h = self._image_label.height() - 8
        if w <= 0 or h <= 0:
            return
        scaled = self._current_pixmap.scaled(
            w, h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(scaled)

    def _show_video_info(self, item: FileItem):
        from app.processing.video_processor import VideoProcessor
        info = VideoProcessor.get_video_info(item.path)
        if info:
            dur = info.get("duration", 0.0)
            mins, secs = divmod(int(dur), 60)
            text = (
                f"<b style='font-size:14px'>{item.path.name}</b><br><br>"
                f"{info.get('width')}×{info.get('height')}  ·  "
                f"{info.get('fps', 0):.1f} fps  ·  "
                f"{mins:02d}:{secs:02d}  ·  "
                f"{info.get('total_frames', '?')} frames"
            )
        else:
            text = f"<b>{item.path.name}</b><br>Video file"
        self._video_label.setText(text)
        self._stack.setCurrentIndex(1)
        self._info_label.setText(item.path.name)

    def _on_save(self):
        if self._current_item:
            self.save_requested.emit(self._output_edit.toPlainText(), self._current_item)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._stack.currentIndex() == 0:
            self._render_image()
