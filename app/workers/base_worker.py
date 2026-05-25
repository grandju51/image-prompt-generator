from PySide6.QtCore import QThread, Signal


class BaseWorker(QThread):
    progress = Signal(int, int)          # current, total
    item_started = Signal(object)        # FileItem
    item_finished = Signal(object, str)  # FileItem, result_text
    item_failed = Signal(object, str)    # FileItem, error_message
    log_message = Signal(str, str)       # message, level
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancel_flag = False

    def request_cancel(self):
        self._cancel_flag = True

    def _check_cancel(self):
        if self._cancel_flag:
            raise InterruptedError("Cancelled by user")
