"""
本地模型 Provider 实现
支持 Ollama、LM Studio 等本地部署的 OpenAI 兼容 API
"""
import logging
import requests
from typing import List, Dict, Any, Optional
from .base import BaseLLMProvider, ProviderConfig, ProviderType

logger = logging.getLogger(__name__)

class LocalProvider(BaseLLMProvider):
    """本地模型 API Provider（Ollama / LM Studio）"""

    VISION_MODELS = {'llava', 'bakllava', 'qwen2-vl'}

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.session = requests.Session()
        self._detect_local_type()

    def _detect_local_type(self):
        """检测本地服务类型（Ollama 或 LM Studio）"""
        if "ollama" in self.config.api_base.lower():
            self._local_type = "ollama"
        elif "lmstudio" in self.config.api_base.lower() or "lm-studio" in self.config.api_base.lower():
            self._local_type = "lmstudio"
        else:
            self._local_type = "generic"

    def chat(self, messages: List[Dict[str, str]],
             system_prompt: Optional[str] = None,
             temperature: Optional[float] = None,
             **kwargs) -> str:
        """调用本地模型 API"""
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        if self._local_type == "ollama":
            return self._chat_ollama(all_messages, temperature, **kwargs)
        else:
            return self._chat_generic(all_messages, system_prompt, temperature, **kwargs)

    def _chat_generic(self, messages: List[Dict[str, str]],
                     system_prompt: Optional[str],
                     temperature: Optional[float],
                     **kwargs) -> str:
        """通用 OpenAI 兼容格式"""
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": self._get_effective_temperature(temperature)
        }

        if self.config.max_tokens:
            payload["max_tokens"] = self.config.max_tokens

        payload.update(kwargs)

        try:
            response = self.session.post(
                f"{self.config.api_base}/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                raise RuntimeError(f"Local API 响应错误 ({response.status_code}): {response.text}")

            resp_json = response.json()
            return resp_json['choices'][0]['message']['content'].strip()

        except Exception as e:
            logger.error(f"Local API 调用失败: {e}", exc_info=True)
            raise e

    def _chat_ollama(self, messages: List[Dict[str, str]],
                    temperature: Optional[float],
                    **kwargs) -> str:
        """Ollama 专用格式"""
        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self._get_effective_temperature(temperature)
            }
        }

        if self.config.max_tokens:
            payload["options"]["num_predict"] = self.config.max_tokens

        payload["options"].update(kwargs)

        try:
            response = self.session.post(
                f"{self.config.api_base}/api/chat",
                json=payload,
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                raise RuntimeError(f"Ollama API 响应错误 ({response.status_code}): {response.text}")

            resp_json = response.json()
            return resp_json['message']['content'].strip()

        except Exception as e:
            logger.error(f"Ollama API 调用失败: {e}", exc_info=True)
            raise e

    def supports_vision(self) -> bool:
        """检查是否支持视觉功能"""
        model_lower = self.config.model_name.lower()
        return any(vision_model in model_lower for vision_model in self.VISION_MODELS)

    def vision_chat(self, image_base64: str,
                   prompt: str,
                   system_prompt: Optional[str] = None,
                   **kwargs) -> str:
        """调用本地视觉模型"""
        if not self.supports_vision():
            raise ValueError(f"模型 {self.config.model_name} 不支持视觉功能")

        if self._local_type == "ollama":
            return self._vision_chat_ollama(image_base64, prompt, system_prompt, **kwargs)
        else:
            return self._vision_chat_generic(image_base64, prompt, system_prompt, **kwargs)

    def _vision_chat_generic(self, image_base64: str,
                            prompt: str,
                            system_prompt: Optional[str],
                            **kwargs) -> str:
        """通用视觉格式"""
        content = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
            },
            {"type": "text", "text": prompt}
        ]

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content})

        return self._chat_generic(messages, system_prompt, kwargs.get("temperature"), **kwargs)

    def _vision_chat_ollama(self, image_base64: str,
                           prompt: str,
                           system_prompt: Optional[str],
                           **kwargs) -> str:
        """Ollama 视觉格式"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "image": image_base64
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        })

        payload = {
            "model": self.config.model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self._get_effective_temperature(kwargs.get("temperature"))
            }
        }

        try:
            response = self.session.post(
                f"{self.config.api_base}/api/chat",
                json=payload,
                timeout=self.config.timeout
            )

            if response.status_code != 200:
                raise RuntimeError(f"Ollama Vision API 错误 ({response.status_code}): {response.text}")

            resp_json = response.json()
            return resp_json['message']['content'].strip()

        except Exception as e:
            logger.error(f"Ollama Vision API 调用失败: {e}", exc_info=True)
            raise e

    @staticmethod
    def create_ollama_config(model_name: str = "llama3",
                            api_base: str = "http://localhost:11434") -> ProviderConfig:
        """快速创建 Ollama 配置"""
        return ProviderConfig(
            provider_type=ProviderType.LOCAL,
            api_base=api_base,
            model_name=model_name,
            timeout=120
        )

    @staticmethod
    def create_lmstudio_config(model_name: str = "local-model",
                              api_base: str = "http://localhost:1234/v1") -> ProviderConfig:
        """快速创建 LM Studio 配置"""
        return ProviderConfig(
            provider_type=ProviderType.LOCAL,
            api_base=api_base,
            model_name=model_name,
            timeout=120
        )
