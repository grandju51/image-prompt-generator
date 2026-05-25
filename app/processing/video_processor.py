import base64
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np


class VideoProcessor:
    """Video frame extraction and metadata. Qt-free."""

    @staticmethod
    def extract_frames(path: Path, mode: str, params: Dict) -> List[np.ndarray]:
        """Extract frames from a video file as BGR numpy arrays."""
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video file: {path}")

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            max_frames = max(1, int(params.get("max_frames", 8)))

            if mode == "every_n_seconds":
                interval = max(0.1, float(params.get("interval_seconds", 2.0)))
                step = max(1, int(interval * fps))
                indices = list(range(0, total, step))

            elif mode == "every_n_frames":
                step = max(1, int(params.get("frame_step", 30)))
                indices = list(range(0, total, step))

            else:  # max_n_frames — distribute evenly
                n = min(max_frames, max(1, total))
                if n == 1:
                    indices = [0]
                else:
                    indices = [int(i * (total - 1) / (n - 1)) for i in range(n)]

            indices = indices[:max_frames]

            frames: List[np.ndarray] = []
            for idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, float(idx))
                ret, frame = cap.read()
                if ret and frame is not None:
                    frames.append(frame)

            return frames
        finally:
            cap.release()

    @staticmethod
    def encode_video_native(path: Path) -> str:
        """Experimental: base64-encode the entire video file for native video input."""
        return base64.b64encode(path.read_bytes()).decode("ascii")

    @staticmethod
    def get_video_info(path: Path) -> Dict:
        """Return basic metadata dict for a video file."""
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            return {}
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total / fps if fps > 0 else 0.0
            return {
                "fps": fps,
                "total_frames": total,
                "width": width,
                "height": height,
                "duration": duration,
            }
        finally:
            cap.release()
