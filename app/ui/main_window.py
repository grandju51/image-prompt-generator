from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
)

from app.config_manager import ConfigManager, save_config
from app.constants import IMAGE_FORMATS, ItemStatus, VIDEO_FORMATS
from app.models.file_item import FileItem
from app.ui.control_panel import ControlPanel
from app.ui.file_list_panel import FileListPanel
from app.ui.find_replace_dialog import FindReplaceDialog
from app.ui.preview_panel import PreviewPanel
from app.workers.batch_worker import BatchWorker
from app.workers.connection_tester_worker import ConnectionTester


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._config_mgr = ConfigManager.instance()
        self._batch_worker: Optional[BatchWorker] = None
        self._conn_tester: Optional[ConnectionTester] = None

        # Debounce config saves triggered by settings changes
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(save_config)

        self.setWindowTitle("Prompt Image  —  Vision LLM Desktop")
        self.resize(1280, 820)
        self._setup_ui()
        self._setup_menu()
        self._connect_signals()
        self._control.load_settings()
        self._restore_geometry()

    # ------------------------------------------------------------------ #
    #  UI construction
    # ------------------------------------------------------------------ #

    def _setup_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._file_panel = FileListPanel()
        self._file_panel.setMinimumWidth(200)

        self._preview = PreviewPanel()

        self._control = ControlPanel()
        self._control.setMinimumWidth(300)

        splitter.addWidget(self._file_panel)
        splitter.addWidget(self._preview)
        splitter.addWidget(self._control)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([270, 640, 370])
        self._splitter = splitter

        self.setCentralWidget(splitter)
        self.setStatusBar(QStatusBar())

    def _setup_menu(self):
        bar = self.menuBar()

        file_menu = bar.addMenu("File")
        for label, shortcut, slot in [
            ("Add Images…", "Ctrl+O", self._add_images),
            ("Add Folder…", "Ctrl+Shift+O", self._add_folder),
            ("Add Video…", "", self._add_video),
        ]:
            a = QAction(label, self)
            if shortcut:
                a.setShortcut(shortcut)
            a.triggered.connect(slot)
            file_menu.addAction(a)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        batch_menu = bar.addMenu("Batch")
        for label, slot in [
            ("Start Batch", self._start_batch),
            ("Process Selected", self._process_selected),
            ("Retry Failed", self._retry_failed),
            ("Cancel", self._cancel_batch),
        ]:
            a = QAction(label, self)
            a.triggered.connect(slot)
            batch_menu.addAction(a)

        edit_menu = bar.addMenu("Edit")
        find_replace_a = QAction("Find && Replace…", self)
        find_replace_a.setShortcut("Ctrl+H")
        find_replace_a.triggered.connect(self._open_find_replace)
        edit_menu.addAction(find_replace_a)

        help_menu = bar.addMenu("Help")
        about_a = QAction("About", self)
        about_a.triggered.connect(self._show_about)
        help_menu.addAction(about_a)

    def _connect_signals(self):
        self._file_panel.selection_changed.connect(self._preview.show_item)

        self._preview.save_requested.connect(self._save_output_to_file)
        self._preview.regenerate_requested.connect(self._process_selected)

        self._control.start_batch_requested.connect(self._start_batch)
        self._control.cancel_requested.connect(self._cancel_batch)
        self._control.retry_failed_requested.connect(self._retry_failed)
        self._control.process_selected_requested.connect(self._process_selected)
        self._control.test_connection_requested.connect(self._test_connection)
        self._control.settings_changed.connect(self._on_settings_changed)

    # ------------------------------------------------------------------ #
    #  File loading
    # ------------------------------------------------------------------ #

    def _add_images(self):
        cfg = self._config_mgr.config
        exts = " ".join(f"*.{e}" for e in sorted(IMAGE_FORMATS))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", cfg.last_open_dir, f"Images ({exts});;All Files (*)"
        )
        if paths:
            cfg.last_open_dir = str(Path(paths[0]).parent)
            save_config()
            self._file_panel.add_files([Path(p) for p in paths])

    def _add_folder(self):
        cfg = self._config_mgr.config
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", cfg.last_open_dir)
        if not folder:
            return
        cfg.last_open_dir = folder
        save_config()

        reply = QMessageBox.question(
            self, "Subfolders",
            "Include subfolders recursively?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        recursive = reply == QMessageBox.StandardButton.Yes
        pattern = "**/*" if recursive else "*"

        all_formats = IMAGE_FORMATS | VIDEO_FORMATS
        paths = sorted(
            p for p in Path(folder).glob(pattern)
            if p.is_file() and p.suffix.lower().lstrip(".") in all_formats
        )
        if paths:
            self._file_panel.add_files(paths)
            self.statusBar().showMessage(f"Added {len(paths)} file(s) from {folder}")
        else:
            QMessageBox.information(
                self, "No Files Found",
                "No supported image or video files found in the selected folder."
            )

    def _add_video(self):
        cfg = self._config_mgr.config
        exts = " ".join(f"*.{e}" for e in sorted(VIDEO_FORMATS))
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Videos", cfg.last_open_dir, f"Videos ({exts});;All Files (*)"
        )
        if paths:
            cfg.last_open_dir = str(Path(paths[0]).parent)
            save_config()
            self._file_panel.add_files([Path(p) for p in paths])

    # ------------------------------------------------------------------ #
    #  Batch control
    # ------------------------------------------------------------------ #

    def _start_batch(self):
        if self._batch_worker and self._batch_worker.isRunning():
            return
        items = [i for i in self._file_panel.all_items() if i.status == ItemStatus.PENDING]
        if not items:
            QMessageBox.information(self, "Nothing to Process",
                                    "No pending items. Add files or use Retry Failed.")
            return
        self._launch_batch(items)

    def _process_selected(self):
        if self._batch_worker and self._batch_worker.isRunning():
            return
        items = self._file_panel.selected_items()
        if not items:
            return
        for item in items:
            item.status = ItemStatus.PENDING
            item.error_message = ""
        self._file_panel._list.viewport().update()
        self._launch_batch(items)

    def _retry_failed(self):
        if self._batch_worker and self._batch_worker.isRunning():
            return
        failed = [i for i in self._file_panel.all_items() if i.status == ItemStatus.FAILED]
        if not failed:
            return
        for item in failed:
            item.status = ItemStatus.PENDING
            item.error_message = ""
        self._file_panel._list.viewport().update()
        self._control.disable_retry_button()
        self._launch_batch(failed)

    def _launch_batch(self, items: List[FileItem]):
        cfg = self._config_mgr.config
        resolved_policy = cfg.overwrite_policy

        # Resolve ASK_BATCH before starting the worker (worker never sees ask_batch)
        if resolved_policy == "ask_batch":
            conflicts = [i for i in items if i.path.with_suffix(".txt").exists()]
            if conflicts:
                answer = QMessageBox.question(
                    self, "Existing .txt Files",
                    f"{len(conflicts)} file(s) already have .txt results.\nOverwrite them?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                resolved_policy = "overwrite" if answer == QMessageBox.StandardButton.Yes else "skip"
            else:
                resolved_policy = "skip"

        self._batch_worker = BatchWorker(items, cfg, resolved_policy)
        w = self._batch_worker
        w.item_started.connect(self._file_panel.update_item_status)
        w.item_started.connect(
            lambda i: self._control.log_widget.append_log(f"Processing {i.path.name}…", "info")
        )
        w.item_finished.connect(self._file_panel.update_item_status)
        w.item_finished.connect(self._on_item_finished)
        w.item_failed.connect(self._file_panel.update_item_status)
        w.item_failed.connect(
            lambda i, e: self._control.log_widget.append_log(f"FAILED {i.path.name}: {e}", "error")
        )
        w.item_failed.connect(lambda i, e: self._control.enable_retry_button())
        w.progress.connect(self._control.update_progress)
        w.log_message.connect(self._control.log_widget.append_log)
        w.finished.connect(self._on_batch_finished)
        w.start()

        self._control.set_batch_running(True)
        self.statusBar().showMessage(f"Processing {len(items)} item(s)…")

    def _cancel_batch(self):
        if self._batch_worker and self._batch_worker.isRunning():
            self._batch_worker.request_cancel()
            self._control.log_widget.append_log("Cancel requested — stopping after current item.", "warning")

    def _on_item_finished(self, item: FileItem, result: str):
        self._file_panel.update_item_status(item)
        self._preview.show_item_result(item)
        self._file_panel.refresh_filter()

    def _on_batch_finished(self):
        self._control.set_batch_running(False)
        items = self._file_panel.all_items()
        done = sum(1 for i in items if i.status == ItemStatus.DONE)
        failed = sum(1 for i in items if i.status == ItemStatus.FAILED)
        self.statusBar().showMessage(f"Batch complete — {done} done, {failed} failed.")
        self._file_panel._update_status()

    # ------------------------------------------------------------------ #
    #  Connection test
    # ------------------------------------------------------------------ #

    def _test_connection(self):
        if self._conn_tester and self._conn_tester.isRunning():
            return
        self._control.set_testing_connection()
        self._control.log_widget.append_log("Testing connection…", "info")
        self._conn_tester = ConnectionTester(self._config_mgr.config)
        self._conn_tester.result.connect(self._control.show_connection_result)
        self._conn_tester.result.connect(
            lambda ok, msg, _: self._control.log_widget.append_log(
                f"Connection test: {msg}", "success" if ok else "error"
            )
        )
        self._conn_tester.start()

    # ------------------------------------------------------------------ #
    #  Output save
    # ------------------------------------------------------------------ #

    def _save_output_to_file(self, text: str, item: FileItem):
        txt_path = item.path.with_suffix(".txt")
        try:
            txt_path.write_text(text, encoding="utf-8")
            item.result_text = text
            self._control.log_widget.append_log(f"Saved {txt_path.name}", "success")
            self._file_panel.refresh_filter()
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Could not save file:\n{e}")

    def _open_find_replace(self):
        dlg = FindReplaceDialog(self)
        dlg.set_items(self._file_panel.all_items(), self._file_panel.selected_items())
        dlg.exec()
        # Refresh search filter and preview after any replacements
        self._file_panel.refresh_filter()
        selected = self._file_panel.selected_items()
        if len(selected) == 1:
            self._preview.show_item(selected[0])

    # ------------------------------------------------------------------ #
    #  Misc
    # ------------------------------------------------------------------ #

    def _on_settings_changed(self, _config):
        self._save_timer.start(500)

    def _show_about(self):
        QMessageBox.about(
            self, "About Prompt Image",
            "<b>Prompt Image</b><br>"
            "Vision LLM Desktop Tool<br><br>"
            "Select images or videos, generate text descriptions using any<br>"
            "OpenAI-compatible vision LLM (LM Studio, vLLM, …), and save<br>"
            "the results as <code>.txt</code> files next to the source files.<br><br>"
            "Dependencies: PySide6 · httpx · Pillow · opencv-python · numpy",
        )

    def _restore_geometry(self):
        cfg = self._config_mgr.config
        if len(cfg.window_geometry) == 4:
            self.setGeometry(*cfg.window_geometry)
        if len(cfg.splitter_sizes) == 3:
            self._splitter.setSizes(cfg.splitter_sizes)

    def closeEvent(self, event):
        cfg = self._config_mgr.config
        geo = self.geometry()
        cfg.window_geometry = [geo.x(), geo.y(), geo.width(), geo.height()]
        cfg.splitter_sizes = self._splitter.sizes()
        save_config()
        if self._batch_worker and self._batch_worker.isRunning():
            self._batch_worker.request_cancel()
            self._batch_worker.wait(3000)
        super().closeEvent(event)
