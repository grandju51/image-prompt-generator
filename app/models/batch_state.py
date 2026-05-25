from typing import List
from pathlib import Path

from app.models.file_item import FileItem
from app.constants import ItemStatus


class BatchState:
    def __init__(self):
        self.items: List[FileItem] = []

    def add_items(self, new_items: List[FileItem]):
        existing = {item.path for item in self.items}
        for item in new_items:
            if item.path not in existing:
                self.items.append(item)
                existing.add(item.path)

    def clear(self):
        self.items.clear()

    def pending_items(self) -> List[FileItem]:
        return [i for i in self.items if i.status == ItemStatus.PENDING]

    def failed_items(self) -> List[FileItem]:
        return [i for i in self.items if i.status == ItemStatus.FAILED]

    def reset_failed_to_pending(self):
        for item in self.items:
            if item.status == ItemStatus.FAILED:
                item.status = ItemStatus.PENDING
                item.error_message = ""

    def has_failures(self) -> bool:
        return any(i.status == ItemStatus.FAILED for i in self.items)
