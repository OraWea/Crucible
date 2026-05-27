"""
LLM Provider 抽象基类和配置管理
支持多种API Provider：DashScope、OpenAI、Claude、本地模型等
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import os
from dotenv import load_dotenv

load_dotenv()

class ProviderType(Enum):
    DASHSCOPE = "dashscope"
    OPENAI = "openai"
    CLAUDE = "claude"
    LOCAL = "local"
    CUSTOM = "custom"

@dataclass
class ProviderConfig:
    """单个Provider的配置"""
    provider_type: ProviderType
    api_key: Optional[str] = None
    api_base: str = ""
    model_name: str = ""
    timeout: int = 60
    max_tokens: Optional[int] = None
    temperature: float = 0.2
    extra_headers: Dict[str, str] = field(default_factory=dict)
    extra_params: Dict[str, Any] = field(default_factory=dict)

class BaseLLMProvider(ABC):
    """LLM Provider 抽象基类"""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._validate_config()

    def _validate_config(self):
        """验证配置完整性"""
        if self.config.provider_type != ProviderType.LOCAL:
            if not self.config.api_key:
                raise ValueError(f"{self.__class__.__name__}: API Key is required")

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]],
             system_prompt: Optional[str] = None,
             temperature: Optional[float] = None,
             **kwargs) -> str:
        """
        统一的聊天接口

        Args:
            messages: 对话消息列表
            system_prompt: 系统提示词（可选）
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            str: 模型生成的回复内容
        """
        pass

    @abstractmethod
    def supports_vision(self) -> bool:
        """检查是否支持视觉/多模态功能"""
        pass

    def _build_messages(self, prompt: str,
                        system_prompt: Optional[str] = None) -> List[Dict[str, str]]:
        """构建消息格式"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _get_effective_temperature(self, temperature: Optional[float]) -> float:
        """获取有效的温度参数"""
        return temperature if temperature is not None else self.config.temperature


class ProviderRegistry:
    """Provider 注册表"""

    _providers: Dict[str, ProviderConfig] = {}
    _default_provider: str = "default"

    @classmethod
    def register(cls, name: str, config: ProviderConfig):
        """注册一个Provider"""
        cls._providers[name] = config
        if len(cls._providers) == 1:
            cls._default_provider = name

    @classmethod
    def get(cls, name: str = None) -> Optional[ProviderConfig]:
        """获取Provider配置"""
        if name is None:
            name = cls._default_provider
        return cls._providers.get(name)

    @classmethod
    def get_all(cls) -> Dict[str, ProviderConfig]:
        """获取所有注册的Provider"""
        return cls._providers.copy()

    @classmethod
    def set_default(cls, name: str):
        """设置默认Provider"""
        if name in cls._providers:
            cls._default_provider = name
        else:
            raise ValueError(f"Provider '{name}' not registered")

    @classmethod
    def load_from_env(cls):
        """从环境变量加载默认Provider配置（DashScope 保持向后兼容）"""
        default_config = ProviderConfig(
            provider_type=ProviderType.DASHSCOPE,
            api_key=os.getenv('LLM_API_KEY', 'your-api-key'),
            api_base=os.getenv('LLM_API_BASE', 'https://dashscope.aliyuncs.com/compatible-mode/v1'),
            model_name=os.getenv('LLM_MODEL_NAME', 'qwen-plus'),
            timeout=int(os.getenv('LLM_TIMEOUT', '60')),
            max_tokens=int(os.getenv('LLM_MAX_TOKENS', '2048')) if os.getenv('LLM_MAX_TOKENS') else None
        )
        cls.register("default", default_config)
