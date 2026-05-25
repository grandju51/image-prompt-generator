from typing import List

import httpx

from app.config_manager import AppConfig, normalize_base_url
from app.api.payload_builder import PayloadBuilder
from app.constants import PayloadMode

_TIMEOUT = 180.0

# Status codes that trigger AUTO fallback to RAW_BASE64
_RETRY_STATUSES = {400, 415, 422}


class VisionLLMClient:
    """HTTP client for OpenAI-compatible vision endpoints. Qt-free."""

    def _headers(self, config: AppConfig) -> dict:
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        return headers

    def describe(self, b64: str, mime: str, config: AppConfig) -> str:
        mode = config.payload_mode
        try:
            return self._call([b64], mime, config, mode)
        except httpx.HTTPStatusError as e:
            body = _extract_body(e.response)
            if mode == PayloadMode.AUTO.value and e.response.status_code in _RETRY_STATUSES:
                try:
                    return self._call([b64], mime, config, PayloadMode.RAW_BASE64.value)
                except httpx.HTTPStatusError as e2:
                    raise RuntimeError(
                        f"HTTP {e2.response.status_code} (both DATA_URI and RAW_BASE64 failed): "
                        f"{_extract_body(e2.response)}"
                    ) from e2
            raise RuntimeError(f"HTTP {e.response.status_code}: {body}") from e

    def describe_multi(self, frames_b64: List[str], config: AppConfig) -> str:
        mode = config.payload_mode
        try:
            return self._call(frames_b64, "image/jpeg", config, mode)
        except httpx.HTTPStatusError as e:
            body = _extract_body(e.response)
            if mode == PayloadMode.AUTO.value and e.response.status_code in _RETRY_STATUSES:
                try:
                    return self._call(frames_b64, "image/jpeg", config, PayloadMode.RAW_BASE64.value)
                except httpx.HTTPStatusError as e2:
                    raise RuntimeError(
                        f"HTTP {e2.response.status_code} (both formats failed): "
                        f"{_extract_body(e2.response)}"
                    ) from e2
            raise RuntimeError(f"HTTP {e.response.status_code}: {body}") from e

    def describe_video_native(self, b64: str, config: AppConfig) -> str:
        video_part = {
            "type": "video_url",
            "video_url": {"url": f"data:video/mp4;base64,{b64}"},
        }
        messages = PayloadBuilder.build_messages(
            [video_part], config, text="Describe this video in detail."
        )
        return self._post(messages, config)

    def _call(self, frames_b64: List[str], mime: str, config: AppConfig, mode: str) -> str:
        image_parts = [PayloadBuilder.make_image_part(b64, mime, mode) for b64 in frames_b64]
        text = "Describe this image in detail." if len(frames_b64) == 1 else "Describe these video frames."
        messages = PayloadBuilder.build_messages(image_parts, config, text=text)
        return self._post(messages, config)

    def _post(self, messages: list, config: AppConfig) -> str:
        base = normalize_base_url(config.api_base_url)
        url = f"{base}/chat/completions"
        payload = {
            "model": config.model_name,
            "messages": messages,
            **PayloadBuilder.build_optional_params(config),
        }
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, json=payload, headers=self._headers(config))
        # Raise HTTPStatusError so callers can inspect status code for fallback logic
        resp.raise_for_status()
        data = resp.json()
        try:
            message = data["choices"][0]["message"]
            content = (message.get("content") or "").strip()
            if not content:
                # Reasoning/thinking models (Qwen3, DeepSeek-R1…) put the CoT in
                # reasoning_content and the final answer in content.
                # When max_tokens is too small the model runs out of budget before
                # writing the answer → content is empty.  Fall back gracefully.
                content = (
                    message.get("reasoning_content") or
                    message.get("thinking") or
                    ""
                ).strip()
                if content:
                    # Prepend a notice so the user knows what happened
                    content = "[reasoning fallback — increase max_tokens for a real answer]\n\n" + content
                else:
                    raise RuntimeError(
                        f"Model returned empty content (finish_reason="
                        f"{data['choices'][0].get('finish_reason')}). "
                        "Try increasing max_tokens."
                    )
            return content
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected API response format: {data}") from e


def _extract_body(response: httpx.Response) -> str:
    try:
        return response.text[:600] or "(empty body)"
    except Exception:
        return "(unreadable body)"
