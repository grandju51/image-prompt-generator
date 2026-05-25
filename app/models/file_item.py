from dataclasses import dataclass, field
from pathlib import Path

from app.constants import ItemStatus, FileType


@dataclass
class FileItem:
    path: Path
    file_type: FileType
    status: ItemStatus = ItemStatus.PENDING
    result_text: str = ""
    error_message: str = ""
    thumbnail: object = field(default=None, repr=False)  # QPixmap | None

    def get_prompt_text(self) -> str:
        """Return prompt from memory, or read from the matching .txt file on disk."""
        if self.result_text:
            return self.result_text
        txt = self.path.with_suffix(".txt")
        if txt.exists():
            try:
                return txt.read_text(encoding="utf-8")
            except Exception:
                return ""
        return ""
