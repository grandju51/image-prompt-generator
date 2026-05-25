import base64
from io import BytesIO
from pathlib import Path
from typing import Tuple

import numpy as np
from PIL import Image


class ImageProcessor:
    """Image preparation for API transmission. Qt-free."""

    @staticmethod
    def prepare_for_api(path: Path, target_size: int) -> Tuple[str, str]:
        """Open image, optionally resize, encode as JPEG base64. Returns (b64, mime)."""
        with Image.open(path) as img:
            img = img.convert("RGB")
            if target_size > 0:
                img = ImageProcessor._resize(img, target_size)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return b64, "image/jpeg"

    @staticmethod
    def ndarray_to_base64(arr: np.ndarray, target_size: int) -> str:
        """Convert a BGR numpy array (from OpenCV) to JPEG base64."""
        import cv2
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        if target_size > 0:
            img = ImageProcessor._resize(img, target_size)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    @staticmethod
    def generate_thumbnail(path: Path, size: int = 96) -> object:
        """Generate a QPixmap thumbnail. Lazy Qt import so module stays testable without Qt."""
        from PySide6.QtGui import QPixmap, QImage
        try:
            with Image.open(path) as img:
                img = img.convert("RGBA")
                img.thumbnail((size, size), Image.LANCZOS)
                buf = BytesIO()
                img.save(buf, format="PNG")
            qimg = QImage.fromData(buf.getvalue())
            return QPixmap.fromImage(qimg)
        except Exception:
            px = QPixmap(size, size)
            px.fill()
            return px

    @staticmethod
    def _resize(img: Image.Image, target: int) -> Image.Image:
        w, h = img.size
        if w <= 0 or h <= 0 or target <= 0:
            return img
        scale = target / max(w, h)
        if scale >= 1.0:
            return img
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        return img.resize((new_w, new_h), Image.LANCZOS)
