import dataclasses
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def normalize_base_url(url: str) -> str:
    """Strip trailing slashes and any /v1 suffix, then append /v1 exactly once."""
    url = url.rstrip("/")
    if url.endswith("/v1"):
        url = url[:-3]
    return url.rstrip("/") + "/v1"


@dataclass
class AppConfig:
    # API connection
    api_base_url: str = "http://localhost:1234/v1"
    api_key: str = ""
    model_name: str = "local-model"
    payload_mode: str = "auto"

    # Generation parameters
    temperature: float = 0.7
    top_p: float = 0.95
    use_top_k: bool = False
    top_k: int = 40
    use_repetition_penalty: bool = False
    repetition_penalty: float = 1.1
    use_max_tokens: bool = True
    max_tokens: int = 1024
    system_prompt: str = "Describe this image in detail as an AI image generation prompt."

    # Image transmission
    image_size: int = 512   # preset value, -1 = original, 0 = custom
    image_size_custom: int = 512

    # Video processing
    video_mode: str = "frame_extraction"
    frame_mode: str = "every_n_seconds"
    frame_every_n_seconds: float = 2.0
    frame_every_n_frames: int = 30
    frame_max_n: int = 8

    # File behavior
    overwrite_policy: str = "skip"
    batch_concurrency: int = 1

    # Output cleanup — strip everything before the first matching marker
    use_output_markers: bool = False
    output_markers: list = field(default_factory=list)

    # UI state (persisted across restarts)
    last_open_dir: str = ""
    window_geometry: list = field(default_factory=list)
    splitter_sizes: list = field(default_factory=list)


class ConfigManager:
    _instance: Optional["ConfigManager"] = None

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "prompt_image"
        self.config_path = self.config_dir / "config.json"
        self.config = AppConfig()
        self.load()

    @classmethod
    def instance(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self):
        if not self.config_path.exists():
            return
        try:
            raw = json.loads(self.config_path.read_text(encoding="utf-8"))
            known = {f.name for f in dataclasses.fields(AppConfig)}
            filtered = {k: v for k, v in raw.items() if k in known}
            self.config = dataclasses.replace(self.config, **filtered)
        except Exception:
            pass

    def save(self):
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.config_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(dataclasses.asdict(self.config), indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, self.config_path)
        except Exception:
            pass


def get_config() -> AppConfig:
    return ConfigManager.instance().config


def save_config():
    ConfigManager.instance().save()
