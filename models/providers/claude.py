"""
Anthropic Claude API Provider 实现
支持 Claude 3 系列模型
"""
import logging
import requests
from typing import List, Dict, Any, Optional
from .base import BaseLLMProvider, ProviderConfig, ProviderType

logger = logging.getLogger(__name__)

class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude API Provider"""

    VISION_MODELS = {'claude-3-opus-20240229', 'claude-3-sonnet-20240229',
                    'claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022'}

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.session = requests.Session()

    def chat(self, messages: List[Dict[str, str]],
             system_prompt: Optional[str] = None,
             temperature: Optional[float] = None,
             **kwargs) -> str:
        """调用 Claude Messages API"""
        if system_prompt:
            system_message = system_prompt
        else:
            system_message = kwargs.pop("system", None)

        all_messages = []
        system_block = None

        if system_message:
            system_block = {"type": "text", "text": system_message}

        for msg in messages:
            role = "user" if msg["role"] == "user" else "assistant"
            all_messages.append({
                "role": role,
                "content": msg["content"]
            })

        payload = {
            "model": self.config.model_name,
            "messages": all_messages,
            "temperature": self._get_effective_temperature(temperature),
            "max_tokens": self.config.max_tokens or 4096
        }

        if system_block:
            payload["system"] = system_block

        payload.update(kwargs)

        try:
            response = self.session.post(
                f"{self.config.api_base}/v1/messages",
                json=payload,
                headers={
                    "x-api-key": self.config.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                    "anthropic-dangerous-direct-browser-access": "true"
                },
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                raise RuntimeError(f"Claude API 响应错误 ({response.status_code}): {response.text}")

            resp_json = response.json()
            return resp_json['content'][0]['text'].strip()

        except Exception as e:
            logger.error(f"Claude API 调用失败: {e}", exc_info=True)
            raise e

    def supports_vision(self) -> bool:
        """Claude 3 系列支持视觉功能"""
        return self.config.model_name in self.VISION_MODELS

    def vision_chat(self, image_base64: str,
                   prompt: str,
                   system_prompt: Optional[str] = None,
                   **kwargs) -> str:
        """调用 Claude 视觉模型"""
        if not self.supports_vision():
            raise ValueError(f"模型 {self.config.model_name} 不支持视觉功能")

        image_content = {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": image_base64
            }
        }

        text_content = {
            "type": "text",
            "text": prompt
        }

        messages = [{
            "role": "user",
            "content": [image_content, text_content]
        }]

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self._get_effective_temperature(kwargs.get("temperature")),
            "max_tokens": self.config.max_tokens or 4096
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = self.session.post(
                f"{self.config.api_base}/v1/messages",
                json=payload,
                headers={
                    "x-api-key": self.config.api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                    "anthropic-dangerous-direct-browser-access": "true"
                },
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                raise RuntimeError(f"Claude Vision API 错误 ({response.status_code}): {response.text}")

            resp_json = response.json()
            return resp_json['content'][0]['text'].strip()

        except Exception as e:
            logger.error(f"Claude Vision API 调用失败: {e}", exc_info=True)
            raise e
