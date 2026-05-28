import json
import logging
from typing import Any, Dict, List, Optional

import requests

from Crucible.config import Config

logger = logging.getLogger(__name__)


def strip_code_fence(text: str, fence_hint: Optional[str] = None) -> str:
    """移除模型常见的 ```json / ```markdown 包裹。"""
    cleaned = (text or "").strip()
    if not cleaned.startswith("```"):
        return cleaned

    lines = cleaned.splitlines()
    if not lines:
        return ""

    first_line = lines[0].strip().lower()
    expected = f"```{fence_hint.lower()}" if fence_hint else "```"
    if first_line == "```" or first_line.startswith(expected):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def parse_json_response(text: str) -> Any:
    """解析模型 JSON 输出，并兼容被代码块包裹的情况。"""
    return json.loads(strip_code_fence(text, "json"))


class OpenAICompatibleClient:
    """最小 OpenAI-compatible Chat Completions 客户端。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: int = 60,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.api_base = (api_base or Config.LLM_API_BASE).rstrip("/")
        self.model_name = model_name or Config.LLM_MODEL_NAME
        self.timeout = timeout

    def configure(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
        vlm_model_name: Optional[str] = None,
        fact_checker_model_name: Optional[str] = None,
    ) -> None:
        Config.update_llm_runtime(
            api_key=api_key,
            api_base=api_base,
            model_name=model_name,
            provider=provider,
            vlm_model_name=vlm_model_name,
            fact_checker_model_name=fact_checker_model_name,
        )
        if api_key is not None:
            self.api_key = api_key
        if api_base is not None:
            self.api_base = api_base.rstrip("/")
        if model_name is not None:
            self.model_name = model_name

    def configure_from_provider(
        self,
        provider: str,
        *,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_name: Optional[str] = None,
        vlm_model_name: Optional[str] = None,
        fact_checker_model_name: Optional[str] = None,
    ) -> None:
        preset = Config.get_provider_preset(provider)
        resolved_api_base = api_base or preset["api_base"]
        resolved_model = model_name or preset["model"]
        resolved_vlm_model = vlm_model_name or preset.get("vlm_model") or resolved_model
        self.configure(
            api_key=api_key,
            api_base=resolved_api_base,
            model_name=resolved_model,
            provider=provider,
            vlm_model_name=resolved_vlm_model,
            fact_checker_model_name=fact_checker_model_name or resolved_model,
        )

    def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        timeout: Optional[int] = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model_name or self.model_name,
            "messages": messages,
            "temperature": temperature,
        }

        try:
            response = requests.post(
                f"{self.api_base}/chat/completions",
                json=payload,
                headers=headers,
                timeout=timeout or self.timeout,
            )
            if response.status_code != 200:
                raise RuntimeError(f"API 响应错误 ({response.status_code}): {response.text}")

            body = response.json()
            return body["choices"][0]["message"]["content"].strip()
        except Exception:
            logger.exception("调用 OpenAI-compatible 接口失败")
            raise


llm_client = OpenAICompatibleClient()
