from __future__ import annotations

from pathlib import Path
from typing import List

from PySide6.QtCore import QThread, Signal

from app.config_manager import AppConfig
from app.models.file_item import FileItem
from app.processing.sam_processor import SamProcessor

# Shared processor instance — keep loaded across runs to avoid reloading on every batch
_shared_processor = SamProcessor()


class SamWorker(QThread):
    item_started = Signal(object)       # FileItem
    item_finished = Signal(object, list)  # FileItem, list[Path]
    item_failed = Signal(object, str)   # FileItem, error_msg
    progress = Signal(int, int)         # current, total
    log_message = Signal(str, str)      # message, level

    def __init__(self, items: List[FileItem], labels: List[str], cfg: AppConfig):
        super().__init__()
        self._items = items
        self._labels = labels
        self._cfg = cfg
        self._cancelled = False

    def request_cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        cfg = self._cfg
        global _shared_processor

        needs_reload = (
            not _shared_processor.is_loaded()
            or _shared_processor.needs_reload(
                cfg.sam3_model_dir,
                cfg.sam3_model_file,
                cfg.sam3_device,
            )
        )

        if needs_reload:
            self.log_message.emit("Loading SAM3 model… (first run may take a while)", "info")
            try:
                _shared_processor.load(
                    model_dir=cfg.sam3_model_dir,
                    model_file=cfg.sam3_model_file,
                    device=cfg.sam3_device,
                )
                self.log_message.emit("SAM3 model loaded.", "success")
            except Exception as exc:
                self.log_message.emit(f"Failed to load SAM3: {exc}", "error")
                return

        total = len(self._items)
        for i, item in enumerate(self._items):
            if self._cancelled:
                self.log_message.emit("Cancelled.", "warning")
                break

            self.item_started.emit(item)
            self.progress.emit(i, total)

            try:
                paths = _shared_processor.generate_masks(
                    image_path=item.path,
                    labels=self._labels,
                    opacity=cfg.sam3_mask_opacity,
                    invert=cfg.sam3_mask_invert,
                    confidence=cfg.sam3_confidence,
                )
                self.item_finished.emit(item, paths)
                if paths:
                    names = ", ".join(p.name for p in paths)
                    self.log_message.emit(f"{item.path.name} → {names}", "success")
                else:
                    self.log_message.emit(f"{item.path.name}: no segments found", "warning")
            except Exception as exc:
                self.item_failed.emit(item, str(exc))
                self.log_message.emit(f"FAILED {item.path.name}: {exc}", "error")

        self.progress.emit(total, total)
