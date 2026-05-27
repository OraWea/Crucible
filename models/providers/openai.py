"""
OpenAI 兼容 API Provider 实现
支持 OpenAI 官方 API 以及兼容 OpenAI 格式的其他服务（如本地部署）
"""
import logging
import requests
from typing import List, Dict, Any, Optional
from .base import BaseLLMProvider, ProviderConfig, ProviderType

logger = logging.getLogger(__name__)

class OpenAIProvider(BaseLLMProvider):
    """OpenAI 兼容 API Provider"""

    VISION_MODELS = {'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-4-vision-preview'}

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.session = requests.Session()

    def chat(self, messages: List[Dict[str, str]],
             system_prompt: Optional[str] = None,
             temperature: Optional[float] = None,
             **kwargs) -> str:
        """调用 OpenAI Chat Completions API"""
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        payload = {
            "model": self.config.model_name,
            "messages": all_messages,
            "temperature": self._get_effective_temperature(temperature)
        }

        if self.config.max_tokens:
            payload["max_tokens"] = self.config.max_tokens

        payload.update(kwargs)

        try:
            response = self.session.post(
                f"{self.config.api_base}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                raise RuntimeError(f"OpenAI API 响应错误 ({response.status_code}): {response.text}")

            resp_json = response.json()
            return resp_json['choices'][0]['message']['content'].strip()

        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}", exc_info=True)
            raise e

    def supports_vision(self) -> bool:
        """检查是否支持视觉功能"""
        return any(model in self.config.model_name.lower()
                  for model in self.VISION_MODELS)

    def vision_chat(self, image_base64: str,
                   prompt: str,
                   system_prompt: Optional[str] = None,
                   **kwargs) -> str:
        """调用 OpenAI 视觉模型"""
        if not self.supports_vision():
            raise ValueError(f"模型 {self.config.model_name} 不支持视觉功能")

        content = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_base64}"
                }
            },
            {
                "type": "text",
                "text": prompt
            }
        ]

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": content})

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self._get_effective_temperature(kwargs.get("temperature"))
        }

        try:
            response = self.session.post(
                f"{self.config.api_base}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                raise RuntimeError(f"OpenAI Vision API 错误 ({response.status_code}): {response.text}")

            resp_json = response.json()
            return resp_json['choices'][0]['message']['content'].strip()

        except Exception as e:
            logger.error(f"OpenAI Vision API 调用失败: {e}", exc_info=True)
            raise e
