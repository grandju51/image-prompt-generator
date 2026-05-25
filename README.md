# Prompt Image

Desktop application for generating text descriptions from images and videos using any OpenAI-compatible vision LLM (LM Studio, vLLM, Ollama with vision support, etc.).

## Features

- Process single images, multi-selected images, or entire folders (with optional recursion)
- Process video files via frame extraction (default) or native video input (experimental)
- Saves a `.txt` file next to each source file with the generated description
- Configurable LLM endpoint, model, and all sampling parameters
- Backend compatibility modes for different OpenAI-compatible servers
- Batch processing with progress tracking, per-item status, and retry-failed support
- Dark UI with thumbnail previews and live log output

## Requirements

- Python 3.10+
- A running OpenAI-compatible vision LLM server

## Installation

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate.bat    # Windows

# Install dependencies
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## Configuration

On first launch, configure the API connection in the right panel:

| Setting | Description |
|---|---|
| Base URL | Your server URL — `http://localhost:1234` or `http://localhost:1234/v1`, both work |
| Model | Model name as reported by the server |
| API Key | Optional — leave empty for local servers that don't require authentication |
| Payload mode | **Auto** (recommended) tries Data URI first; **Data URI** is the most compatible mode; **Raw Base64** is experimental |

Click **Test Connection** to verify the server is reachable and see available models.

## Usage

1. **Add files**: File > Add Images, Add Folder, or Add Video
2. **Configure**: set API URL, model, and desired generation parameters in the right panel
3. **Process**:
   - Select one or more items → **Process Selected** to run only those
   - **Start Batch** to process all pending items
4. Generated descriptions are saved as `.txt` files next to each source file
5. If any items fail, click **Retry Failed** to reprocess only those

## Supported Formats

| Type | Formats |
|---|---|
| Images | `jpg`, `jpeg`, `png`, `webp`, `bmp` |
| Videos | `mp4`, `mkv`, `mov`, `avi` |

## Video Processing

**Frame extraction (default)**: extracts frames at a configurable interval and sends them as images to the model. Compatible with all vision models.

**Native video (experimental)**: sends the full video file as base64. Only works with models/servers that explicitly support video input — enable at your own risk.

## File Behavior

| Policy | Behavior |
|---|---|
| Skip existing | If `.txt` already exists, skip writing (LLM result still shown in UI) |
| Overwrite | Always overwrite existing `.txt` files |
| Ask once per batch | Dialog appears before the batch starts — one decision applies to all conflicts |

## Project Structure

```
prompt_image/
├── main.py                 # Entry point
├── requirements.txt
├── README.md
└── app/
    ├── constants.py        # Enums and constants
    ├── config_manager.py   # Settings persistence
    ├── models/             # FileItem, BatchState
    ├── workers/            # QThread workers (batch, connection test)
    ├── api/                # LLM HTTP client, payload builder
    ├── processing/         # Image resize/encode, video frame extraction
    └── ui/                 # All PySide6 widgets
```
