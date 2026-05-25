"""
Headless processing core — no Qt, shared by CLI and MCP server.
"""
import re
from pathlib import Path
from typing import Callable, List, Optional

from app.config_manager import AppConfig, ConfigManager, save_config
from app.constants import IMAGE_FORMATS, VIDEO_FORMATS


# ──────────────────────────────────────────────────────────────────────────────
#  Config helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_config(**overrides) -> AppConfig:
    """Return the persisted config, applying any keyword overrides."""
    cfg = ConfigManager.instance().config
    for k, v in overrides.items():
        if v is not None and v != "" and hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg


def config_as_dict() -> dict:
    cfg = ConfigManager.instance().config
    import dataclasses
    return dataclasses.asdict(cfg)


def set_config_value(key: str, value: str) -> str:
    cfg = ConfigManager.instance().config
    if not hasattr(cfg, key):
        return f"Unknown config key: {key}"
    current = getattr(cfg, key)
    # Cast to the same type as the current value
    try:
        if isinstance(current, bool):
            parsed = value.lower() in ("1", "true", "yes")
        elif isinstance(current, int):
            parsed = int(value)
        elif isinstance(current, float):
            parsed = float(value)
        elif isinstance(current, list):
            parsed = [v.strip() for v in value.split(",") if v.strip()]
        else:
            parsed = value
        setattr(cfg, key, parsed)
        save_config()
        return f"{key} = {parsed!r}"
    except (ValueError, TypeError) as e:
        return f"Could not set {key}: {e}"


# ──────────────────────────────────────────────────────────────────────────────
#  File discovery
# ──────────────────────────────────────────────────────────────────────────────

def collect_paths(source: str, recursive: bool = False) -> List[Path]:
    p = Path(source)
    if p.is_file():
        return [p]
    pattern = "**/*" if recursive else "*"
    all_formats = IMAGE_FORMATS | VIDEO_FORMATS
    return sorted(
        f for f in p.glob(pattern)
        if f.is_file() and f.suffix.lower().lstrip(".") in all_formats
    )


# ──────────────────────────────────────────────────────────────────────────────
#  Processing
# ──────────────────────────────────────────────────────────────────────────────

def describe_one(path: Path, cfg: AppConfig) -> str:
    """Process a single image or video and return the generated text."""
    from app.api.llm_client import VisionLLMClient
    from app.processing.image_processor import ImageProcessor
    from app.processing.video_processor import VideoProcessor

    client = VisionLLMClient()
    ext = path.suffix.lower().lstrip(".")
    target = cfg.image_size if cfg.image_size != 0 else cfg.image_size_custom

    if ext in IMAGE_FORMATS:
        b64, mime = ImageProcessor.prepare_for_api(path, target)
        result = client.describe(b64, mime, cfg)
    else:
        params = {
            "interval_seconds": cfg.frame_every_n_seconds,
            "frame_step": cfg.frame_every_n_frames,
            "max_frames": cfg.frame_max_n,
        }
        frames = VideoProcessor.extract_frames(path, cfg.frame_mode, params)
        if not frames:
            raise RuntimeError(f"No frames extracted from {path.name}")
        frames_b64 = [ImageProcessor.ndarray_to_base64(f, target) for f in frames]
        result = client.describe_multi(frames_b64, cfg)

    if cfg.use_output_markers and cfg.output_markers:
        from app.utils.text_cleaner import apply_markers
        result = apply_markers(result, cfg.output_markers)

    return result


def process_batch(
    paths: List[Path],
    cfg: AppConfig,
    overwrite: bool = False,
    concurrency: int = 1,
    progress_cb: Optional[Callable] = None,
) -> dict:
    """Process a list of files. Returns {"ok": [...], "errors": [...]}."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict = {"ok": [], "errors": []}
    total = len(paths)
    completed = 0

    def _one(path: Path):
        txt = path.with_suffix(".txt")
        if txt.exists() and not overwrite:
            return path, True, f"SKIP {path.name}"
        text = describe_one(path, cfg)
        txt.write_text(text, encoding="utf-8")
        return path, True, text

    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        futures = {ex.submit(_one, p): p for p in paths}
        for future in as_completed(futures):
            path = futures[future]
            completed += 1
            try:
                _, ok, msg = future.result()
                results["ok"].append({"path": str(path), "text": msg})
                ok, msg_cb = True, msg
            except Exception as e:
                msg_cb = str(e)
                ok = False
                results["errors"].append({"path": str(path), "error": msg_cb})
            if progress_cb:
                progress_cb(completed, total, path, ok, msg_cb)

    return results


# ──────────────────────────────────────────────────────────────────────────────
#  Search / filter
# ──────────────────────────────────────────────────────────────────────────────

def search_prompts(
    folder: str,
    query: str,
    recursive: bool = False,
    case_sensitive: bool = False,
) -> List[dict]:
    """
    Filter files whose .txt prompt matches the query.
    Use word1+word2 for AND mode (all words must appear).
    Returns list of {"path": ..., "txt": ..., "snippet": ...}.
    """
    paths = collect_paths(folder, recursive=recursive)
    and_mode = "+" in query
    flags = 0 if case_sensitive else re.IGNORECASE

    results = []
    for p in paths:
        txt_path = p.with_suffix(".txt")
        if not txt_path.exists():
            continue
        try:
            text = txt_path.read_text(encoding="utf-8")
        except Exception:
            continue

        if and_mode:
            terms = [t.strip() for t in query.split("+") if t.strip()]
            match = all(re.search(re.escape(t), text, flags) for t in terms)
        else:
            match = bool(re.search(re.escape(query), text, flags))

        if match:
            snippet = text[:200].replace("\n", " ")
            results.append({"path": str(p), "txt": str(txt_path), "snippet": snippet})

    return results


# ──────────────────────────────────────────────────────────────────────────────
#  Find & replace
# ──────────────────────────────────────────────────────────────────────────────

def find_replace(
    folder: str,
    find: str,
    replace: str = "",
    case_sensitive: bool = False,
    recursive: bool = False,
    dry_run: bool = False,
) -> dict:
    """Find and replace across .txt files. Returns {"changed": N, "details": [...]}."""
    root = Path(folder)
    pattern = "**/*.txt" if recursive else "*.txt"
    flags = 0 if case_sensitive else re.IGNORECASE

    changed = 0
    total_hits = 0
    details = []

    for txt in sorted(root.glob(pattern)):
        try:
            text = txt.read_text(encoding="utf-8")
        except Exception as e:
            details.append({"file": txt.name, "error": str(e)})
            continue

        count = len(re.findall(re.escape(find), text, flags))
        if not count:
            continue

        new_text = re.sub(re.escape(find), replace, text, flags=flags)
        if not dry_run:
            txt.write_text(new_text, encoding="utf-8")
        changed += 1
        total_hits += count
        details.append({"file": txt.name, "occurrences": count, "dry_run": dry_run})

    return {"changed": changed, "total_hits": total_hits, "details": details}


# ──────────────────────────────────────────────────────────────────────────────
#  Connection test
# ──────────────────────────────────────────────────────────────────────────────

def test_connection(url: str = "", model: str = "") -> dict:
    """GET /v1/models and return {"ok": bool, "message": str, "models": [...]}."""
    import httpx
    from app.config_manager import normalize_base_url

    cfg = get_config(api_base_url=url or None, model_name=model or None)
    base = normalize_base_url(cfg.api_base_url)
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    try:
        resp = httpx.get(f"{base}/models", headers=headers, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        models = [m.get("id", str(m)) for m in data.get("data", [])]
        return {"ok": True, "message": f"Connected — {len(models)} model(s)", "models": models}
    except httpx.HTTPStatusError as e:
        return {"ok": False, "message": f"HTTP {e.response.status_code}: {e.response.text[:200]}", "models": []}
    except Exception as e:
        return {"ok": False, "message": str(e), "models": []}
