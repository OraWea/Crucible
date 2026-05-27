"""
阿里云 DashScope (百炼) Provider 实现
向后兼容原有的阿里百炼API配置
"""
import logging
import requests
from typing import List, Dict, Any, Optional
from .base import BaseLLMProvider, ProviderConfig, ProviderType

logger = logging.getLogger(__name__)

class DashScopeProvider(BaseLLMProvider):
    """阿里云 DashScope API Provider"""

    VLM_MODELS = {'qwen-vl-plus', 'qwen-vl-max', 'qwen2-vl-2b-instruct',
                  'qwen2-vl-7b-instruct', 'qwen2-vl-72b-instruct'}

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.session = requests.Session()

    def chat(self, messages: List[Dict[str, str]],
             system_prompt: Optional[str] = None,
             temperature: Optional[float] = None,
             **kwargs) -> str:
        """调用 DashScope Chat Completion API"""
        if system_prompt and messages and messages[0]["role"] != "system":
            messages = [{"role": "system", "content": system_prompt}] + messages
        elif system_prompt:
            messages[0]["content"] = system_prompt

        payload = {
            "model": self.config.model_name,
            "input": {"messages": messages},
            "parameters": {
                "temperature": self._get_effective_temperature(temperature),
                "result_format": "message"
            }
        }

        if self.config.max_tokens:
            payload["parameters"]["max_tokens"] = self.config.max_tokens

        payload["parameters"].update(kwargs)

        try:
            response = self.session.post(
                f"{self.config.api_base}/services/aigc/text-generation/generation",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                raise RuntimeError(f"DashScope API 响应错误 ({response.status_code}): {response.text}")

            resp_json = response.json()
            return resp_json['output']['text'].strip()

        except Exception as e:
            logger.error(f"DashScope API 调用失败: {e}", exc_info=True)
            raise e

    def chat_completions(self, messages: List[Dict[str, str]],
                         system_prompt: Optional[str] = None,
                         temperature: Optional[float] = None,
                         **kwargs) -> str:
        """调用 OpenAI 兼容的 Chat Completions API 端点"""
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
                raise RuntimeError(f"DashScope Chat Completions 错误 ({response.status_code}): {response.text}")

            resp_json = response.json()
            return resp_json['choices'][0]['message']['content'].strip()

        except Exception as e:
            logger.error(f"DashScope Chat Completions 调用失败: {e}", exc_info=True)
            raise e

    def supports_vision(self) -> bool:
        """DashScope 支持视觉模型"""
        return self.config.model_name.lower() in self.VLM_MODELS

    def vision_chat(self, image_base64: str,
                    prompt: str,
                    system_prompt: Optional[str] = None,
                    **kwargs) -> str:
        """调用 DashScope 视觉模型"""
        if not self.supports_vision():
            raise ValueError(f"模型 {self.config.model_name} 不支持视觉功能")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({
            "role": "user",
            "content": [
                {"image": f"data:image/jpeg;base64,{image_base64}"},
                {"text": prompt}
            ]
        })

        payload = {
            "model": self.config.model_name,
            "input": {"messages": messages},
            "parameters": {
                "temperature": self._get_effective_temperature(kwargs.get("temperature")),
                "result_format": "message"
            }
        }

        try:
            response = self.session.post(
                f"{self.config.api_base}/services/aigc/multimodal-generation/generation",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                raise RuntimeError(f"DashScope Vision API 错误 ({response.status_code}): {response.text}")

            resp_json = response.json()
            return resp_json['output']['text'].strip()

        except Exception as e:
            logger.error(f"DashScope Vision API 调用失败: {e}", exc_info=True)
            raise e
