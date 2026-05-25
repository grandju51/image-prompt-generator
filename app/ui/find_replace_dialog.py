from pathlib import Path
from typing import List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from app.models.file_item import FileItem


class FindReplaceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find & Replace in .txt files")
        self.setMinimumWidth(520)
        self._all_items: List[FileItem] = []
        self._selected_items: List[FileItem] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ── Find / Replace fields ──────────────────────────────────────
        fields = QGroupBox("Search")
        fl = QVBoxLayout(fields)

        row_find = QHBoxLayout()
        row_find.addWidget(QLabel("Find:"))
        self._find_edit = QLineEdit()
        self._find_edit.setPlaceholderText("Text to search for…")
        row_find.addWidget(self._find_edit, 1)
        fl.addLayout(row_find)

        row_replace = QHBoxLayout()
        row_replace.addWidget(QLabel("Replace:"))
        self._replace_edit = QLineEdit()
        self._replace_edit.setPlaceholderText("Replacement text (leave empty to delete)")
        row_replace.addWidget(self._replace_edit, 1)
        fl.addLayout(row_replace)

        self._case_cb = QCheckBox("Case-sensitive")
        fl.addWidget(self._case_cb)
        layout.addWidget(fields)

        # ── Scope ─────────────────────────────────────────────────────
        scope_box = QGroupBox("Scope")
        sl = QHBoxLayout(scope_box)
        self._scope_all = QRadioButton("All files in list")
        self._scope_sel = QRadioButton("Selected files only")
        self._scope_all.setChecked(True)
        sl.addWidget(self._scope_all)
        sl.addWidget(self._scope_sel)
        layout.addWidget(scope_box)

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._preview_btn = QPushButton("Preview")
        self._preview_btn.clicked.connect(self._run_preview)
        self._apply_btn = QPushButton("Apply")
        self._apply_btn.setDefault(True)
        self._apply_btn.clicked.connect(self._run_apply)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._preview_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._apply_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # ── Results log ───────────────────────────────────────────────
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(160)
        self._log.setPlaceholderText("Results will appear here after Preview or Apply…")
        layout.addWidget(self._log)

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def set_items(self, all_items: List[FileItem], selected_items: List[FileItem]):
        self._all_items = all_items
        self._selected_items = selected_items
        has_sel = bool(selected_items)
        self._scope_sel.setEnabled(has_sel)
        if not has_sel:
            self._scope_all.setChecked(True)

    # ------------------------------------------------------------------ #
    #  Internal
    # ------------------------------------------------------------------ #

    def _target_items(self) -> List[FileItem]:
        if self._scope_sel.isChecked() and self._selected_items:
            return self._selected_items
        return self._all_items

    def _get_params(self):
        find = self._find_edit.text()
        replace = self._replace_edit.text()
        case = self._case_cb.isChecked()
        return find, replace, case

    def _run_preview(self):
        find, replace, case = self._get_params()
        if not find:
            self._log.setPlainText("Nothing to search for.")
            return

        items = self._target_items()
        lines = []
        total_matches = 0
        for item in items:
            txt_path = item.path.with_suffix(".txt")
            if not txt_path.exists():
                continue
            try:
                text = txt_path.read_text(encoding="utf-8")
            except Exception as e:
                lines.append(f"[ERROR] {txt_path.name}: {e}")
                continue
            count = self._count_occurrences(text, find, case)
            if count:
                total_matches += count
                action = f"→ delete {count}" if not replace else f"→ replace {count}"
                lines.append(f"{txt_path.name}  ({count} match{'es' if count > 1 else ''})")

        if total_matches:
            lines.insert(0, f"Preview: {total_matches} match(es) across {len([l for l in lines if '→' not in l or '→' in l])} file(s)\n")
        else:
            lines = ["No matches found."]
        self._log.setPlainText("\n".join(lines))

    def _run_apply(self):
        find, replace, case = self._get_params()
        if not find:
            self._log.setPlainText("Nothing to search for.")
            return

        items = self._target_items()
        lines = []
        total_files = 0
        total_matches = 0

        for item in items:
            txt_path = item.path.with_suffix(".txt")
            if not txt_path.exists():
                continue
            try:
                text = txt_path.read_text(encoding="utf-8")
            except Exception as e:
                lines.append(f"[ERROR] read {txt_path.name}: {e}")
                continue

            count = self._count_occurrences(text, find, case)
            if not count:
                continue

            new_text = self._do_replace(text, find, replace, case)
            try:
                txt_path.write_text(new_text, encoding="utf-8")
                # Update in-memory result_text if already loaded
                if item.result_text:
                    item.result_text = new_text
            except Exception as e:
                lines.append(f"[ERROR] write {txt_path.name}: {e}")
                continue

            total_files += 1
            total_matches += count
            verb = "deleted" if not replace else "replaced"
            lines.append(f"{txt_path.name}  — {count} occurrence(s) {verb}")

        if total_matches:
            lines.insert(0, f"Done: {total_matches} replacement(s) in {total_files} file(s)\n")
        else:
            lines = ["No matches found — nothing changed."]
        self._log.setPlainText("\n".join(lines))

    @staticmethod
    def _count_occurrences(text: str, find: str, case: bool) -> int:
        if case:
            return text.count(find)
        return text.lower().count(find.lower())

    @staticmethod
    def _do_replace(text: str, find: str, replace: str, case: bool) -> str:
        if case:
            return text.replace(find, replace)
        # Case-insensitive replace preserving original case structure
        import re
        return re.sub(re.escape(find), replace, text, flags=re.IGNORECASE)
