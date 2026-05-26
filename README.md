# Prompt Image

Desktop application for generating text descriptions from images and videos using any OpenAI-compatible vision LLM (LM Studio, vLLM, Ollama, etc.), with optional SAM3 segmentation masking.

## Features

- Process single images, multi-selected images, or entire folders (with optional recursion)
- Process video files via frame extraction (default) or native video input (experimental)
- Saves a `.txt` file next to each source file with the generated description
- Configurable LLM endpoint, model, and all sampling parameters
- **SAM3 segmentation**: generate RGBA mask layers from text labels ("face,hands", "logo,text", etc.)
- **Combined workflow**: LLM caption → unload VRAM → SAM3 masking, sequentially in one click
- Batch processing with progress tracking, per-item status, and retry-failed support
- CLI and MCP server for headless/agent use
- Dark UI with thumbnail previews and live log output

## Requirements

- Python **3.11+** (required for SAM3 compatibility with Qt)
- A running OpenAI-compatible vision LLM server (for caption features)
- CUDA GPU recommended for SAM3 (CPU supported but slower)

## Installation

```bash
# Create venv with Python 3.11
python3.11 -m venv .venv
source .venv/bin/activate        # Linux / macOS

# Base dependencies
pip install -r requirements.txt

# PyTorch with CUDA (recommended for SAM3)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

## Running

```bash
.venv/bin/python main.py
```

## SAM3 Segmentation

SAM3 generates transparent PNG mask layers from text labels. All specified labels are merged into a single output file: `{image}-masklabel.png`.

### Setup

1. Download the SAM3 model (`sam3.pt`) and place it in a folder of your choice
2. In **Options → SAM3 Segmentation**, set the model directory and filename
3. Open the **SAM Masking** tab in the main window

### Usage

- Type labels in the input field: `face, hands` or `lips, eyes, hair`
- Click **Run — Sélection** for selected files, **Run — Batch** for all files
- Enable **"Lancer SAM3 automatiquement avec le batch LLM"** to auto-run after LLM caption

### Output

| Input | Output |
|---|---|
| `photo.jpg` + labels `"face,hands"` | `photo-masklabel.png` (RGBA, white mask) |

White pixels = selected area (configurable opacity), transparent = background.
Invert mode: mask the background, keep selection visible.

## CLI

```bash
# Caption a single image
.venv/bin/python main.py describe photo.jpg --save

# SAM3 masking
.venv/bin/python main.py mask photo.jpg "lips,eyes,hair" --device cuda

# Process a folder
.venv/bin/python main.py batch /data/photos -c 4
.venv/bin/python main.py mask /data/photos "face,hands" -r

# Full help
.venv/bin/python main.py --help
```

See `USAGE.txt` for complete CLI and MCP documentation.

## MCP Server

```bash
.venv/bin/python mcp_server.py
```

Add to `~/.claude/settings.json`:
```json
{
  "mcpServers": {
    "image-prompt-generator": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["/absolute/path/to/mcp_server.py"]
    }
  }
}
```

Available tools: `describe_image`, `describe_folder`, `generate_masks`, `generate_masks_folder`, `list_prompt_files`, `read_prompt`, `write_prompt`, `search_prompts`, `find_replace_in_prompts`, `test_connection`, `get_config`, `set_config`.

## Configuration

On first launch, configure the API connection in the right panel:

| Setting | Description |
|---|---|
| Base URL | Your server URL — `http://localhost:1234` or `http://localhost:1234/v1` |
| Model | Model name as reported by the server |
| API Key | Optional — leave empty for local servers |
| Payload mode | **Auto** (recommended) |

Click **Test Connection** to verify.

## Supported Formats

| Type | Formats |
|---|---|
| Images | `jpg`, `jpeg`, `png`, `webp`, `bmp` |
| Videos | `mp4`, `mkv`, `mov`, `avi` |

## Project Structure

```
prompt_image/
├── main.py                 # Entry point (GUI + CLI)
├── mcp_server.py           # MCP server
├── requirements.txt
├── USAGE.txt               # Full CLI & MCP documentation
└── app/
    ├── config_manager.py   # Settings persistence
    ├── constants.py
    ├── api/                # LLM HTTP client
    ├── cli/                # Headless processing core (runner.py)
    ├── models/             # FileItem, BatchState
    ├── processing/         # Image/video processing, SAM3 processor
    ├── sam3/               # Embedded SAM3 model (standalone, no ComfyUI)
    ├── workers/            # QThread workers (batch, SAM3, connection test)
    └── ui/                 # PySide6 widgets (main window, SAM panel, settings)
```
