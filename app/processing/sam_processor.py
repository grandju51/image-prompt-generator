from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image

# Ensure the embedded sam3 package is importable
_SAM3_PKG = Path(__file__).parent.parent / "sam3"
_SAM3_BPE = _SAM3_PKG / "assets" / "bpe_simple_vocab_16e6.txt.gz"
_APP_DIR = str(Path(__file__).parent.parent.parent)
if _APP_DIR not in sys.path:
    sys.path.insert(0, _APP_DIR)


class SamProcessor:
    def __init__(self):
        self._processor = None
        self._loaded_key: Optional[tuple] = None

    def load(self, model_dir: str, model_file: str, device: str = "auto") -> None:
        import torch
        from app.sam3.model_builder import build_sam3_image_model
        from app.sam3.model.sam3_image_processor import Sam3Processor as _Sam3Processor

        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"

        checkpoint = Path(model_dir) / model_file
        if not checkpoint.exists():
            raise FileNotFoundError(
                f"SAM3 checkpoint not found: {checkpoint}\n"
                f"Check the model directory and file name in Options → SAM3 Segmentation."
            )

        model = build_sam3_image_model(
            bpe_path=str(_SAM3_BPE),
            device=device,
            eval_mode=True,
            checkpoint_path=str(checkpoint),
            load_from_HF=False,
            enable_segmentation=True,
            enable_inst_interactivity=False,
        )
        # Move all registered parameters/buffers
        model = model.to(device)
        # The decoder's coord cache is NOT a registered buffer — it's hardcoded to
        # "cuda" at init (decoder.py line 280). Move it explicitly.
        import torch
        for module in model.modules():
            if hasattr(module, "compilable_cord_cache") and module.compilable_cord_cache is not None:
                h, w = module.compilable_cord_cache
                module.compilable_cord_cache = (h.to(device), w.to(device))
            if hasattr(module, "coord_cache"):
                module.coord_cache = {
                    k: (v[0].to(device), v[1].to(device))
                    for k, v in module.coord_cache.items()
                }
        self._processor = _Sam3Processor(model, device=device)
        self._loaded_key = (model_dir, model_file, device)

    def is_loaded(self) -> bool:
        return self._processor is not None

    def needs_reload(self, model_dir: str, model_file: str, device: str) -> bool:
        return self._loaded_key != (model_dir, model_file, device)

    def generate_masks(
        self,
        image_path: Path,
        labels: List[str],
        opacity: int = 200,
        invert: bool = False,
        confidence: float = 0.5,
    ) -> List[Path]:
        if self._processor is None:
            raise RuntimeError("SAM3 model not loaded. Call load() first.")

        image = Image.open(image_path).convert("RGB")
        h, w = image.size[1], image.size[0]
        combined = np.zeros((h, w), dtype=np.uint8)

        for label in labels:
            label = label.strip()
            if not label:
                continue

            state = self._processor.set_image(image)
            self._processor.reset_all_prompts(state)
            self._processor.set_confidence_threshold(confidence, state)
            state = self._processor.set_text_prompt(label, state)

            masks = state.get("masks")
            if masks is None or masks.numel() == 0:
                continue

            masks = masks.float()
            if masks.ndim == 4:
                masks = masks.squeeze(1)

            merged = masks.amax(dim=0)
            mask_np = (merged.clamp(0, 1).cpu().numpy() * 255).astype(np.uint8)
            combined = np.maximum(combined, mask_np)

        if invert:
            combined = 255 - combined

        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[:, :, 0] = 255
        rgba[:, :, 1] = 255
        rgba[:, :, 2] = 255
        rgba[:, :, 3] = (combined > 127).astype(np.uint8) * opacity

        out_path = image_path.parent / f"{image_path.stem}-masklabel.png"
        Image.fromarray(rgba, "RGBA").save(out_path, "PNG")
        return [out_path]
