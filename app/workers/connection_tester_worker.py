import httpx
from PySide6.QtCore import Signal

from app.workers.base_worker import BaseWorker
from app.config_manager import AppConfig, normalize_base_url


class ConnectionTester(BaseWorker):
    # success, human-readable message, list of model IDs
    result = Signal(bool, str, list)

    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self.config = config

    def run(self):
        base = normalize_base_url(self.config.api_base_url)
        url = f"{base}/models"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(url, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                models: list = []
                if isinstance(data, dict):
                    if "data" in data:
                        models = [m.get("id", str(m)) for m in data["data"] if isinstance(m, dict)]
                    elif "models" in data:
                        models = [str(m) for m in data["models"]]
                elif isinstance(data, list):
                    models = [str(m) for m in data]

                preview = ", ".join(models[:5])
                suffix = f" (+{len(models) - 5} more)" if len(models) > 5 else ""
                label = f"Connected — {len(models)} model(s): {preview}{suffix}" if models else "Connected"
                self.result.emit(True, label, models)
            else:
                self.result.emit(False, f"HTTP {resp.status_code}: {resp.text[:300]}", [])

        except httpx.ConnectError:
            self.result.emit(False, f"Connection refused at {url}", [])
        except httpx.TimeoutException:
            self.result.emit(False, f"Timeout connecting to {url}", [])
        except Exception as e:
            self.result.emit(False, str(e), [])

        self.finished.emit()
