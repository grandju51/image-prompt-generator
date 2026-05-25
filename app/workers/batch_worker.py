from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

from app.workers.base_worker import BaseWorker
from app.models.file_item import FileItem
from app.constants import ItemStatus, FileType, VideoMode
from app.config_manager import AppConfig


class BatchWorker(BaseWorker):
    def __init__(
        self,
        items: List[FileItem],
        config: AppConfig,
        resolved_policy: str,
        parent=None,
    ):
        super().__init__(parent)
        self.items = items
        self.config = config
        self.resolved_policy = resolved_policy  # "skip" or "overwrite" — never "ask_batch"

    def run(self):
        from app.processing.image_processor import ImageProcessor
        from app.processing.video_processor import VideoProcessor

        total = len(self.items)
        concurrency = max(1, getattr(self.config, "batch_concurrency", 1))

        completed = 0

        def process_one(item: FileItem):
            from app.api.llm_client import VisionLLMClient
            # Each thread gets its own client (httpx is not thread-safe across requests)
            client = VisionLLMClient()

            item.status = ItemStatus.PROCESSING
            self.item_started.emit(item)

            try:
                result = self._process_item(item, client, ImageProcessor, VideoProcessor)
                result = self._clean_result(result)
                self._save_result(item, result)
                item.status = ItemStatus.DONE
                item.result_text = result
                self.item_finished.emit(item, result)
            except Exception as e:
                item.status = ItemStatus.FAILED
                item.error_message = str(e)
                self.item_failed.emit(item, str(e))

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            # Submit items one by one, checking cancel before each submission
            future_to_item = {}
            for item in self.items:
                if self._cancel_flag:
                    self.log_message.emit("Batch cancelled — no new items submitted.", "info")
                    break
                future_to_item[executor.submit(process_one, item)] = item

            for future in as_completed(future_to_item):
                if self._cancel_flag:
                    break
                # Exceptions inside process_one are already handled (emitted as item_failed)
                try:
                    future.result()
                except Exception:
                    pass
                completed += 1
                self.progress.emit(completed, total)

        self.finished.emit()

    # ------------------------------------------------------------------ #
    #  Per-item processing (called from thread pool)
    # ------------------------------------------------------------------ #

    def _process_item(self, item, client, ImageProcessor, VideoProcessor) -> str:
        if item.file_type == FileType.IMAGE:
            return self._process_image(item, client, ImageProcessor)
        else:
            return self._process_video(item, client, ImageProcessor, VideoProcessor)

    def _process_image(self, item, client, ImageProcessor) -> str:
        target_size = self._get_target_size()
        b64, mime = ImageProcessor.prepare_for_api(item.path, target_size)
        self.log_message.emit(f"Sending {item.path.name}…", "info")
        return client.describe(b64, mime, self.config)

    def _process_video(self, item, client, ImageProcessor, VideoProcessor) -> str:
        if self.config.video_mode == VideoMode.NATIVE_VIDEO.value:
            try:
                return self._process_video_native(item, client, VideoProcessor)
            except Exception as e:
                self.log_message.emit(
                    f"Native video failed ({e}). Falling back to frame extraction.", "warning"
                )
        return self._process_video_frames(item, client, ImageProcessor, VideoProcessor)

    def _process_video_native(self, item, client, VideoProcessor) -> str:
        b64 = VideoProcessor.encode_video_native(item.path)
        self.log_message.emit(f"Sending {item.path.name} as native video (experimental)…", "info")
        return client.describe_video_native(b64, self.config)

    def _process_video_frames(self, item, client, ImageProcessor, VideoProcessor) -> str:
        params = {
            "interval_seconds": self.config.frame_every_n_seconds,
            "frame_step": self.config.frame_every_n_frames,
            "max_frames": self.config.frame_max_n,
        }
        frames = VideoProcessor.extract_frames(item.path, self.config.frame_mode, params)
        if not frames:
            raise RuntimeError(f"Could not extract any frames from {item.path.name}")
        self.log_message.emit(f"Extracted {len(frames)} frames from {item.path.name}", "info")
        target_size = self._get_target_size()
        frames_b64 = [ImageProcessor.ndarray_to_base64(f, target_size) for f in frames]
        return client.describe_multi(frames_b64, self.config)

    def _get_target_size(self) -> int:
        size = self.config.image_size
        if size == -1:
            return -1
        if size == 0:
            return self.config.image_size_custom
        return size

    def _clean_result(self, result: str) -> str:
        if self.config.use_output_markers and self.config.output_markers:
            from app.utils.text_cleaner import apply_markers
            return apply_markers(result, self.config.output_markers)
        return result

    def _save_result(self, item: FileItem, result: str):
        txt_path = item.path.with_suffix(".txt")
        if txt_path.exists() and self.resolved_policy == "skip":
            self.log_message.emit(f"Skipping existing {txt_path.name}", "info")
            return
        try:
            txt_path.write_text(result, encoding="utf-8")
            self.log_message.emit(f"Saved {txt_path.name}", "success")
        except Exception as e:
            raise RuntimeError(f"Could not write {txt_path.name}: {e}") from e
