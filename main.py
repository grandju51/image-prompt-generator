import sys


# ──────────────────────────────────────────────────────────────────────────────
#  GUI
# ──────────────────────────────────────────────────────────────────────────────

def _run_gui():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPalette
    from PySide6.QtWidgets import QApplication

    from app.config_manager import ConfigManager, save_config
    from app.ui.main_window import MainWindow

    def _dark_palette(app):
        p = QPalette()
        p.setColor(QPalette.ColorRole.Window,          QColor("#2B2B2B"))
        p.setColor(QPalette.ColorRole.WindowText,      QColor("#CCCCCC"))
        p.setColor(QPalette.ColorRole.Base,            QColor("#1E1E1E"))
        p.setColor(QPalette.ColorRole.AlternateBase,   QColor("#2B2B2B"))
        p.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#3C3F41"))
        p.setColor(QPalette.ColorRole.ToolTipText,     QColor("#CCCCCC"))
        p.setColor(QPalette.ColorRole.Text,            QColor("#CCCCCC"))
        p.setColor(QPalette.ColorRole.Button,          QColor("#3C3F41"))
        p.setColor(QPalette.ColorRole.ButtonText,      QColor("#CCCCCC"))
        p.setColor(QPalette.ColorRole.BrightText,      QColor("#FFFFFF"))
        p.setColor(QPalette.ColorRole.Link,            QColor("#4A90E2"))
        p.setColor(QPalette.ColorRole.Highlight,       QColor("#4A90E2"))
        p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text,       QColor("#666666"))
        p.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#666666"))
        app.setPalette(p)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Prompt Image")
    app.setOrganizationName("prompt_image")
    app.setStyle("Fusion")
    _dark_palette(app)
    ConfigManager.instance()
    try:
        w = MainWindow()
        w.show()
        result = app.exec()
    finally:
        save_config()
    sys.exit(result)


# ──────────────────────────────────────────────────────────────────────────────
#  CLI subcommands
# ──────────────────────────────────────────────────────────────────────────────

def _add_api_args(p):
    """Common API/generation arguments reused by batch and describe."""
    p.add_argument("--url",          metavar="URL",  help="API base URL (e.g. http://localhost:1234/v1)")
    p.add_argument("--model",        metavar="NAME", help="Model name")
    p.add_argument("--api-key",      metavar="KEY",  help="API key (Bearer token)")
    p.add_argument("--payload-mode", metavar="MODE", choices=["auto", "data_uri", "raw_base64"],
                   help="Image encoding mode (default: auto)")
    p.add_argument("--system-prompt",metavar="TEXT", help="System prompt sent to the model")
    p.add_argument("--temperature",  metavar="T",    type=float, help="Sampling temperature (0.0–2.0)")
    p.add_argument("--top-p",        metavar="P",    type=float, help="Top-P (0.0–1.0)")
    p.add_argument("--max-tokens",   metavar="N",    type=int,   help="Max output tokens")
    p.add_argument("--image-size",   metavar="PX",   type=int,
                   help="Resize longest side before sending. -1 = original, 0 = custom value in config")
    p.add_argument("--marker",       metavar="TEXT", action="append", dest="markers",
                   help="Output cleanup marker (repeatable). Strip everything before the first match.")


def _cfg_from_args(args):
    from app.cli.runner import get_config
    overrides = {}
    if getattr(args, "url",          None): overrides["api_base_url"]    = args.url
    if getattr(args, "model",        None): overrides["model_name"]      = args.model
    if getattr(args, "api_key",      None): overrides["api_key"]         = args.api_key
    if getattr(args, "payload_mode", None): overrides["payload_mode"]    = args.payload_mode
    if getattr(args, "system_prompt",None): overrides["system_prompt"]   = args.system_prompt
    if getattr(args, "temperature",  None): overrides["temperature"]     = args.temperature
    if getattr(args, "top_p",        None): overrides["top_p"]           = args.top_p
    if getattr(args, "max_tokens",   None): overrides["max_tokens"]      = args.max_tokens

    if getattr(args, "image_size",   None) is not None:
        overrides["image_size"] = args.image_size
    if getattr(args, "markers",      None):
        overrides["use_output_markers"] = True
        overrides["output_markers"]     = args.markers
    return get_config(**overrides)


def _progress(done, total, path, ok, msg):
    tag = "SKIP" if (ok and msg.startswith("SKIP")) else ("OK  " if ok else "ERR ")
    print(f"  [{done}/{total}] {tag}  {path.name}")
    if not ok:
        print(f"         {msg}", file=sys.stderr)


# ── batch ────────────────────────────────────────────────────────────────────

def cmd_batch(args):
    from app.cli.runner import collect_paths, process_batch
    cfg = _cfg_from_args(args)
    paths = collect_paths(args.source, recursive=args.recursive)
    if not paths:
        print("No supported files found.", file=sys.stderr); sys.exit(1)
    print(f"Processing {len(paths)} file(s)  (concurrency={args.concurrency})…")
    r = process_batch(paths, cfg, overwrite=args.overwrite,
                      concurrency=args.concurrency, progress_cb=_progress)
    print(f"\nDone — {len(r['ok'])} OK, {len(r['errors'])} error(s).")
    if r["errors"]: sys.exit(1)


# ── describe ─────────────────────────────────────────────────────────────────

def cmd_describe(args):
    from pathlib import Path
    from app.cli.runner import describe_one
    cfg = _cfg_from_args(args)
    p = Path(args.file)
    if not p.exists():
        print(f"File not found: {p}", file=sys.stderr); sys.exit(1)
    print(f"Processing {p.name}…")
    try:
        result = describe_one(p, cfg)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)

    if args.save:
        txt = p.with_suffix(".txt")
        txt.write_text(result, encoding="utf-8")
        print(f"Saved → {txt}")
    else:
        print("\n" + result)


# ── find-replace ─────────────────────────────────────────────────────────────

def cmd_find_replace(args):
    from app.cli.runner import find_replace
    r = find_replace(
        folder=args.folder,
        find=args.find,
        replace=args.replace or "",
        case_sensitive=args.case_sensitive,
        recursive=args.recursive,
        dry_run=args.dry_run,
    )
    mode = "[DRY RUN] " if args.dry_run else ""
    print(f"{mode}{r['total_hits']} occurrence(s) in {r['changed']} file(s).")
    for d in r["details"]:
        if "error" in d:
            print(f"  ERROR  {d['file']}: {d['error']}")
        else:
            verb = "would replace" if args.dry_run else "replaced"
            print(f"  {d['occurrences']:>4}×  {verb}  {d['file']}")
    if r["changed"] == 0:
        print("No matches found.")


# ── search ───────────────────────────────────────────────────────────────────

def cmd_search(args):
    from app.cli.runner import search_prompts
    results = search_prompts(
        folder=args.folder,
        query=args.query,
        recursive=args.recursive,
        case_sensitive=args.case_sensitive,
    )
    if not results:
        print("No matches."); return
    print(f"{len(results)} file(s) match '{args.query}':\n")
    for r in results:
        from pathlib import Path
        print(f"  {Path(r['path']).name}")
        if args.snippet:
            print(f"    {r['snippet'][:160]}")


# ── test ─────────────────────────────────────────────────────────────────────

def cmd_test(args):
    from app.cli.runner import test_connection
    r = test_connection(url=args.url or "", model=args.model or "")
    status = "OK " if r["ok"] else "ERR"
    print(f"[{status}] {r['message']}")
    if r["models"]:
        print("  Models: " + ", ".join(r["models"][:10]))


# ── config ───────────────────────────────────────────────────────────────────

def cmd_config(args):
    if args.set:
        from app.cli.runner import set_config_value
        for pair in args.set:
            if "=" not in pair:
                print(f"Invalid format (expected key=value): {pair}", file=sys.stderr)
                continue
            k, v = pair.split("=", 1)
            print(set_config_value(k.strip(), v.strip()))
    else:
        import json
        from app.cli.runner import config_as_dict
        print(json.dumps(config_as_dict(), indent=2))


# ──────────────────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="python main.py",
        description="Image Prompt Generator — Vision LLM tool.",
    )
    sub = parser.add_subparsers(dest="cmd")

    # ── batch ────────────────────────────────────────────────────────────────
    p_batch = sub.add_parser("batch", help="Process all images/videos in a file or folder.")
    p_batch.add_argument("source", help="File or folder path.")
    p_batch.add_argument("-r", "--recursive",   action="store_true", help="Include subfolders.")
    p_batch.add_argument("-c", "--concurrency", type=int, default=1, metavar="N",
                         help="Parallel requests (default: 1).")
    p_batch.add_argument("--overwrite", action="store_true", help="Overwrite existing .txt files.")
    _add_api_args(p_batch)

    # ── describe ─────────────────────────────────────────────────────────────
    p_desc = sub.add_parser("describe", help="Process a single image or video.")
    p_desc.add_argument("file", help="Path to the image or video file.")
    p_desc.add_argument("--save", action="store_true",
                        help="Save result as .txt next to the source file (default: print to stdout).")
    _add_api_args(p_desc)

    # ── find-replace ─────────────────────────────────────────────────────────
    p_fr = sub.add_parser("find-replace", help="Find and replace text across all .txt prompt files.")
    p_fr.add_argument("folder",  help="Folder containing .txt files.")
    p_fr.add_argument("--find",  required=True, metavar="TEXT", help="Text to search for.")
    p_fr.add_argument("--replace", metavar="TEXT", default="",
                      help="Replacement text. Omit to delete the matched text.")
    p_fr.add_argument("-r", "--recursive",    action="store_true", help="Search subfolders.")
    p_fr.add_argument("--case-sensitive",     action="store_true")
    p_fr.add_argument("--dry-run",            action="store_true",
                      help="Show what would change without writing anything.")

    # ── search ───────────────────────────────────────────────────────────────
    p_srch = sub.add_parser("search", help="Filter files by prompt content.")
    p_srch.add_argument("folder", help="Folder to search.")
    p_srch.add_argument("query",
                        help="Phrase to find. Use word1+word2 to require both words (AND mode).")
    p_srch.add_argument("-r", "--recursive",  action="store_true")
    p_srch.add_argument("--case-sensitive",   action="store_true")
    p_srch.add_argument("--snippet",          action="store_true",
                        help="Show a short extract from each matching prompt.")

    # ── test ─────────────────────────────────────────────────────────────────
    p_test = sub.add_parser("test", help="Test the API connection and list available models.")
    p_test.add_argument("--url",   metavar="URL",  help="API base URL")
    p_test.add_argument("--model", metavar="NAME", help="Model name (informational only)")

    # ── config ───────────────────────────────────────────────────────────────
    p_cfg = sub.add_parser("config", help="Show or edit the persistent configuration.")
    p_cfg.add_argument("--set", nargs="+", metavar="key=value",
                       help="Set one or more config values (e.g. --set temperature=0.8 top_p=0.9)")

    args = parser.parse_args()

    if args.cmd == "batch":        cmd_batch(args)
    elif args.cmd == "describe":   cmd_describe(args)
    elif args.cmd == "find-replace": cmd_find_replace(args)
    elif args.cmd == "search":     cmd_search(args)
    elif args.cmd == "test":       cmd_test(args)
    elif args.cmd == "config":     cmd_config(args)
    else:
        _run_gui()


if __name__ == "__main__":
    main()
