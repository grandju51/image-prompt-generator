from typing import Any, Dict, List

from app.config_manager import AppConfig
from app.constants import PayloadMode


class PayloadBuilder:
    """Builds OpenAI-compatible request body/messages. No Qt, no HTTP headers."""

    @staticmethod
    def make_image_part(b64: str, mime: str, mode: str) -> Dict[str, Any]:
        if mode == PayloadMode.RAW_BASE64.value:
            # Experimental: raw base64 string in url field — not universally supported
            return {"type": "image_url", "image_url": {"url": b64}}
        else:
            # DATA_URI (default) or AUTO: standard data URI format
            return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}

    @staticmethod
    def build_messages(
        image_parts: List[Dict[str, Any]],
        config: AppConfig,
        text: str = "Describe this image.",
    ) -> List[Dict[str, Any]]:
        content: List[Dict[str, Any]] = [{"type": "text", "text": text}] + image_parts
        messages: List[Dict[str, Any]] = []
        if config.system_prompt.strip():
            messages.append({"role": "system", "content": config.system_prompt})
        messages.append({"role": "user", "content": content})
        return messages

    @staticmethod
    def build_optional_params(config: AppConfig) -> Dict[str, Any]:
        """Only include generation params that are explicitly enabled."""
        params: Dict[str, Any] = {
            "temperature": config.temperature,
            "top_p": config.top_p,
        }
        if config.use_max_tokens:
            params["max_tokens"] = config.max_tokens
        if config.use_top_k:
            params["top_k"] = config.top_k
        if config.use_repetition_penalty:
            params["repetition_penalty"] = config.repetition_penalty
        return params
