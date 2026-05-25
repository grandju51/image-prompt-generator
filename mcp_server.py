"""
MCP server for Image Prompt Generator.

Expose all app capabilities as tools for any MCP-compatible agent
(Claude Code, etc.).  No Qt required — pure processing only.

Usage:
    python mcp_server.py

Add to ~/.claude/settings.json:
    {
      "mcpServers": {
        "image-prompt-generator": {
          "command": "python3",
          "args": ["/absolute/path/to/mcp_server.py"]
        }
      }
    }
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("image-prompt-generator")


# ──────────────────────────────────────────────────────────────────────────────
#  Processing tools
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def describe_image(
    path: str,
    url: str = "",
    model: str = "",
    api_key: str = "",
    system_prompt: str = "",
    temperature: float = 0.0,
    max_tokens: int = 0,
    image_size: int = 0,
    payload_mode: str = "",
    save: bool = True,
) -> str:
    """
    Describe a single image or video using the configured vision LLM.

    Args:
        path:          Absolute path to an image (jpg/png/webp/bmp) or video (mp4/mkv/mov/avi).
        url:           API base URL override (e.g. http://localhost:1234/v1).
        model:         Model name override.
        api_key:       API key override (Bearer token).
        system_prompt: System prompt override.
        temperature:   Sampling temperature override (0.0 = use saved config).
        max_tokens:    Max output tokens override (0 = use saved config).
        image_size:    Resize longest side before sending (px). -1 = original. 0 = use saved config.
        payload_mode:  "auto" | "data_uri" | "raw_base64" (empty = use saved config).
        save:          If true (default), save result as .txt next to the source file.
    Returns the generated description text.
    """
    from pathlib import Path
    from app.cli.runner import describe_one, get_config

    overrides = {}
    if url:           overrides["api_base_url"] = url
    if model:         overrides["model_name"]   = model
    if api_key:       overrides["api_key"]       = api_key
    if system_prompt: overrides["system_prompt"] = system_prompt
    if temperature:   overrides["temperature"]   = temperature
    if max_tokens:    overrides["max_tokens"]    = max_tokens; overrides["use_max_tokens"] = True
    if image_size:    overrides["image_size"]    = image_size
    if payload_mode:  overrides["payload_mode"]  = payload_mode

    cfg = get_config(**overrides)
    p = Path(path)
    result = describe_one(p, cfg)

    if save:
        p.with_suffix(".txt").write_text(result, encoding="utf-8")

    return result


@mcp.tool()
def describe_folder(
    folder: str,
    recursive: bool = False,
    overwrite: bool = False,
    concurrency: int = 1,
    url: str = "",
    model: str = "",
    api_key: str = "",
    system_prompt: str = "",
    temperature: float = 0.0,
    max_tokens: int = 0,
    image_size: int = 0,
    payload_mode: str = "",
) -> str:
    """
    Process all images and videos in a folder, saving descriptions as .txt files.

    Args:
        folder:        Absolute path to the folder.
        recursive:     Include subfolders (default: false).
        overwrite:     Overwrite existing .txt files (default: skip).
        concurrency:   Parallel requests (default: 1, increase for faster batch).
        url:           API base URL override.
        model:         Model name override.
        api_key:       API key override.
        system_prompt: System prompt override.
        temperature:   Sampling temperature override (0.0 = use saved config).
        max_tokens:    Max output tokens override (0 = use saved config).
        image_size:    Resize longest side before sending (px). -1 = original.
        payload_mode:  "auto" | "data_uri" | "raw_base64".
    Returns a processing summary.
    """
    from app.cli.runner import collect_paths, get_config, process_batch

    overrides = {}
    if url:           overrides["api_base_url"] = url
    if model:         overrides["model_name"]   = model
    if api_key:       overrides["api_key"]       = api_key
    if system_prompt: overrides["system_prompt"] = system_prompt
    if temperature:   overrides["temperature"]   = temperature
    if max_tokens:    overrides["max_tokens"]    = max_tokens; overrides["use_max_tokens"] = True
    if image_size:    overrides["image_size"]    = image_size
    if payload_mode:  overrides["payload_mode"]  = payload_mode

    cfg = get_config(**overrides)
    paths = collect_paths(folder, recursive=recursive)
    if not paths:
        return "No supported files found."

    results = process_batch(paths, cfg, overwrite=overwrite, concurrency=concurrency)
    ok = len(results["ok"])
    lines = [f"Processed {ok}/{len(paths)} file(s)."]
    for e in results["errors"]:
        lines.append(f"  ERROR  {e['path']}: {e['error']}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
#  .txt file tools
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_prompt_files(folder: str, recursive: bool = False) -> str:
    """
    List all image/video files in a folder and show whether each has a .txt prompt.

    Args:
        folder:    Absolute path to the folder.
        recursive: Include subfolders.
    """
    from app.cli.runner import collect_paths
    paths = collect_paths(folder, recursive=recursive)
    if not paths:
        return "No supported files found."

    has_txt = sum(1 for p in paths if p.with_suffix(".txt").exists())
    lines = [f"{len(paths)} file(s) — {has_txt} with .txt, {len(paths) - has_txt} without.\n"]
    for p in paths:
        marker = "✓" if p.with_suffix(".txt").exists() else "·"
        lines.append(f"  {marker}  {p.name}")
    return "\n".join(lines)


@mcp.tool()
def read_prompt(path: str) -> str:
    """
    Return the content of the .txt prompt file associated with an image or video.

    Args:
        path: Absolute path to the image/video file (or directly to a .txt file).
    """
    from pathlib import Path
    p = Path(path)
    txt = p if p.suffix == ".txt" else p.with_suffix(".txt")
    if not txt.exists():
        return f"No .txt file found for {p.name}"
    return txt.read_text(encoding="utf-8")


@mcp.tool()
def write_prompt(path: str, text: str) -> str:
    """
    Write (or overwrite) the .txt prompt file associated with an image or video.

    Args:
        path: Absolute path to the image/video file (or directly to a .txt file).
        text: Text content to write.
    """
    from pathlib import Path
    p = Path(path)
    txt = p if p.suffix == ".txt" else p.with_suffix(".txt")
    txt.write_text(text, encoding="utf-8")
    return f"Saved {txt.name} ({len(text)} chars)"


@mcp.tool()
def search_prompts(
    folder: str,
    query: str,
    recursive: bool = False,
    case_sensitive: bool = False,
    show_snippets: bool = True,
) -> str:
    """
    Filter files whose .txt prompt matches the query.
    Use word1+word2+word3 to require all words (AND mode).
    Exact phrase match when no + is present.

    Args:
        folder:         Folder to search.
        query:          Search phrase. Use + to separate AND terms (e.g. "girl+forest+sunset").
        recursive:      Include subfolders.
        case_sensitive: Default: false.
        show_snippets:  Show a short extract from each matching prompt (default: true).
    """
    from app.cli.runner import search_prompts as _search
    from pathlib import Path

    results = _search(folder, query, recursive=recursive, case_sensitive=case_sensitive)
    if not results:
        return f"No matches for '{query}'."

    lines = [f"{len(results)} file(s) match '{query}':\n"]
    for r in results:
        lines.append(f"  {Path(r['path']).name}")
        if show_snippets:
            lines.append(f"    {r['snippet'][:200]}")
    return "\n".join(lines)


@mcp.tool()
def find_replace_in_prompts(
    folder: str,
    find: str,
    replace: str = "",
    case_sensitive: bool = False,
    recursive: bool = False,
    dry_run: bool = False,
) -> str:
    """
    Find and replace (or delete) text across all .txt prompt files in a folder.

    Args:
        folder:         Folder containing .txt files.
        find:           Text to search for.
        replace:        Replacement. Leave empty to delete the matched text.
        case_sensitive: Default: false.
        recursive:      Search subfolders.
        dry_run:        Preview what would change without writing anything.
    """
    from app.cli.runner import find_replace

    r = find_replace(folder, find, replace, case_sensitive, recursive, dry_run)
    mode = "[DRY RUN] " if dry_run else ""
    lines = [f"{mode}{r['total_hits']} occurrence(s) across {r['changed']} file(s)."]
    for d in r["details"]:
        if "error" in d:
            lines.append(f"  ERROR  {d['file']}: {d['error']}")
        else:
            verb = "would replace" if dry_run else "replaced"
            lines.append(f"  {d['occurrences']:>4}×  {verb}  {d['file']}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
#  Config & connection tools
# ──────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def test_connection(url: str = "", model: str = "") -> str:
    """
    Test the API connection by calling GET /v1/models.

    Args:
        url:   API base URL to test (empty = use saved config).
        model: Model name (informational, not used for the test itself).
    """
    from app.cli.runner import test_connection as _test
    r = _test(url=url, model=model)
    status = "OK" if r["ok"] else "ERROR"
    lines = [f"[{status}] {r['message']}"]
    if r["models"]:
        lines.append("Available models:")
        for m in r["models"]:
            lines.append(f"  - {m}")
    return "\n".join(lines)


@mcp.tool()
def get_config() -> str:
    """Return the current configuration as JSON."""
    import json
    from app.cli.runner import config_as_dict
    return json.dumps(config_as_dict(), indent=2)


@mcp.tool()
def set_config(settings: str) -> str:
    """
    Update one or more persistent config values.

    Args:
        settings: Key=value pairs separated by newlines or commas.
                  Example: "temperature=0.8, top_p=0.9, model_name=llava"
    Known keys: api_base_url, model_name, api_key, payload_mode, system_prompt,
                temperature, top_p, use_top_k, top_k, use_repetition_penalty,
                repetition_penalty, use_max_tokens, max_tokens, image_size,
                image_size_custom, video_mode, frame_mode, frame_every_n_seconds,
                frame_every_n_frames, frame_max_n, overwrite_policy, batch_concurrency,
                use_output_markers, output_markers.
    """
    from app.cli.runner import set_config_value
    # Accept "key=value" lines or comma-separated
    import re
    pairs = re.split(r"[,\n]+", settings)
    results = []
    for pair in pairs:
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            results.append(f"Skipped (no '='): {pair}")
            continue
        k, v = pair.split("=", 1)
        results.append(set_config_value(k.strip(), v.strip()))
    return "\n".join(results)


if __name__ == "__main__":
    mcp.run()
