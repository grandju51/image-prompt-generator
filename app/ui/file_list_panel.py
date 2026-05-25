from pathlib import Path
from typing import List

from PySide6.QtCore import QObject, QRunnable, QSize, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.constants import FileType, IMAGE_FORMATS, ItemStatus, THUMBNAIL_SIZE, VIDEO_FORMATS
from app.models.file_item import FileItem
from app.ui.thumbnail_delegate import ThumbnailDelegate


class _ThumbnailSignals(QObject):
    done = Signal(object, object)  # FileItem, QPixmap


class _ThumbnailRunnable(QRunnable):
    def __init__(self, item: FileItem):
        super().__init__()
        self.item = item
        self.signals = _ThumbnailSignals()

    def run(self):
        from app.processing.image_processor import ImageProcessor

        if self.item.file_type == FileType.IMAGE:
            pixmap = ImageProcessor.generate_thumbnail(self.item.path, THUMBNAIL_SIZE)
        else:
            pixmap = self._video_thumbnail(self.item.path)
        self.signals.done.emit(self.item, pixmap)

    @staticmethod
    def _video_thumbnail(path: Path) -> QPixmap:
        try:
            import cv2
            from io import BytesIO

            from PIL import Image

            cap = cv2.VideoCapture(str(path))
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return QPixmap()
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            img.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            return QPixmap.fromImage(qimg)
        except Exception:
            return QPixmap()


class FileListPanel(QWidget):
    selection_changed = Signal(object)  # FileItem | None
    files_added = Signal(list)          # list[FileItem]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._item_map: dict = {}  # Path -> QListWidgetItem
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_filter)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Search bar ────────────────────────────────────────────────
        search_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Filter prompts — exact phrase, or word1+word2+word3")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(lambda: self._search_timer.start(300))

        search_row.addWidget(self._search_edit, 1)
        layout.addLayout(search_row)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.setItemDelegate(ThumbnailDelegate())
        self._list.setIconSize(QSize(THUMBNAIL_SIZE, THUMBNAIL_SIZE))
        self._list.setSpacing(2)
        self._list.setUniformItemSizes(True)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)

        btn_row = QHBoxLayout()
        sel_all = QPushButton("Select All")
        sel_all.clicked.connect(self._list.selectAll)
        clear_btn = QPushButton("Clear List")
        clear_btn.clicked.connect(self._clear_list)
        btn_row.addWidget(sel_all)
        btn_row.addWidget(clear_btn)

        self._status_label = QLabel("No files loaded")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addLayout(btn_row)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._status_label)

    def add_files(self, paths: List[Path]):
        new_items: List[FileItem] = []
        for p in paths:
            if p in self._item_map:
                continue
            ext = p.suffix.lower().lstrip(".")
            if ext in IMAGE_FORMATS:
                ftype = FileType.IMAGE
            elif ext in VIDEO_FORMATS:
                ftype = FileType.VIDEO
            else:
                continue

            item = FileItem(path=p, file_type=ftype)
            q_item = QListWidgetItem()
            q_item.setData(Qt.ItemDataRole.UserRole, item)
            q_item.setSizeHint(QSize(260, THUMBNAIL_SIZE + 12))
            self._list.addItem(q_item)
            self._item_map[p] = q_item
            new_items.append(item)
            self._start_thumbnail(item)

        if new_items:
            self.files_added.emit(new_items)
            self._update_status()

    def _start_thumbnail(self, item: FileItem):
        runnable = _ThumbnailRunnable(item)
        runnable.signals.done.connect(self._on_thumbnail_ready)
        QThreadPool.globalInstance().start(runnable)

    def _on_thumbnail_ready(self, item: FileItem, pixmap: QPixmap):
        item.thumbnail = pixmap
        if item.path in self._item_map:
            self._list.viewport().update()

    def update_item_status(self, item: FileItem):
        if item.path in self._item_map:
            self._list.viewport().update()
            self._update_status()

    def _on_selection_changed(self):
        selected = self._list.selectedItems()
        if len(selected) == 1:
            self.selection_changed.emit(selected[0].data(Qt.ItemDataRole.UserRole))
        else:
            self.selection_changed.emit(None)

    def _clear_list(self):
        self._list.clear()
        self._item_map.clear()
        self.selection_changed.emit(None)
        self._update_status()

    def selected_items(self) -> List[FileItem]:
        return [
            i.data(Qt.ItemDataRole.UserRole)
            for i in self._list.selectedItems()
            if i.data(Qt.ItemDataRole.UserRole) is not None
        ]

    def all_items(self) -> List[FileItem]:
        result = []
        for idx in range(self._list.count()):
            data = self._list.item(idx).data(Qt.ItemDataRole.UserRole)
            if data:
                result.append(data)
        return result

    def _apply_filter(self):
        query = self._search_edit.text().strip()
        visible = 0
        total = 0

        # Auto-detect AND mode: "word1+word2" → all terms must appear anywhere
        # Exact mode: no + → the whole phrase must appear in order
        and_mode = "+" in query

        for idx in range(self._list.count()):
            q_item = self._list.item(idx)
            fi: FileItem = q_item.data(Qt.ItemDataRole.UserRole)
            total += 1
            if not query:
                q_item.setHidden(False)
                visible += 1
                continue

            text = fi.get_prompt_text().lower()
            if and_mode:
                terms = [t.strip().lower() for t in query.split("+") if t.strip()]
                match = all(t in text for t in terms)
            else:
                match = query.lower() in text

            q_item.setHidden(not match)
            if match:
                visible += 1

        if query:
            self._status_label.setText(f"{visible}/{total} files match")
        else:
            self._update_status()

    def refresh_filter(self):
        """Re-apply current filter (call after .txt files are written/changed)."""
        self._apply_filter()

    def _update_status(self):
        items = self.all_items()
        total = len(items)
        if total == 0:
            self._status_label.setText("No files loaded")
            return
        done = sum(1 for i in items if i.status == ItemStatus.DONE)
        failed = sum(1 for i in items if i.status == ItemStatus.FAILED)
        processing = sum(1 for i in items if i.status == ItemStatus.PROCESSING)
        extra = f"  ·  {processing} running" if processing else ""
        self._status_label.setText(f"{total} files  ·  {done} done  ·  {failed} failed{extra}")
