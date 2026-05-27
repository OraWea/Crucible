"""
LLM Manager - 统一调度器
管理多个 Provider，支持按模块选择不同模型
"""
import logging
import sys
import os
from typing import Dict, Optional, List, Any

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.providers import (
    ProviderConfig,
    ProviderType,
    ProviderRegistry,
    create_provider,
    BaseLLMProvider
)

logger = logging.getLogger(__name__)

class LLMManager:
    """
    LLM 统一调度管理器

    支持功能：
    - 多 Provider 注册与管理
    - 按任务类型自动选择最优 Provider
    - 向后兼容原有配置
    - 模块级模型配置
    """

    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._module_providers: Dict[str, str] = {}
        self._init_default_providers()

    def _init_default_providers(self):
        """初始化默认 Provider（从环境变量加载）"""
        ProviderRegistry.load_from_env()
        default_config = ProviderRegistry.get("default")
        if default_config:
            provider = create_provider(default_config)
            self._providers["default"] = provider
            logger.info(f"默认 Provider 已加载: {default_config.provider_type.value} - {default_config.model_name}")

    def register_provider(self, name: str, config: ProviderConfig, set_default: bool = False):
        """
        注册一个新的 Provider

        Args:
            name: Provider 名称
            config: Provider 配置
            set_default: 是否设为默认
        """
        provider = create_provider(config)
        self._providers[name] = provider
        ProviderRegistry.register(name, config)

        if set_default:
            ProviderRegistry.set_default(name)

        logger.info(f"Provider 已注册: {name} ({config.provider_type.value}) - {config.model_name}")

    def register_module_provider(self, module_name: str, provider_name: str):
        """
        为特定模块注册专属的 Provider

        Args:
            module_name: 模块名称 (如 'fact_checker', 'concept_extractor')
            provider_name: 已注册的 Provider 名称
        """
        if provider_name not in self._providers:
            raise ValueError(f"Provider '{provider_name}' 未注册")
        self._module_providers[module_name] = provider_name
        logger.info(f"模块 '{module_name}' 已绑定到 Provider '{provider_name}'")

    def get_provider(self, module_name: Optional[str] = None) -> BaseLLMProvider:
        """
        获取 Provider

        Args:
            module_name: 模块名称，如果指定则返回该模块专属的 Provider

        Returns:
            BaseLLMProvider 实例
        """
        if module_name and module_name in self._module_providers:
            provider_name = self._module_providers[module_name]
            return self._providers[provider_name]

        return self._providers.get("default")

    def chat(self, prompt: str,
             system_prompt: Optional[str] = None,
             module: Optional[str] = None,
             temperature: Optional[float] = None,
             **kwargs) -> str:
        """
        统一的聊天接口

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词
            module: 指定模块（使用该模块对应的 Provider）
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            str: 模型回复
        """
        provider = self.get_provider(module)
        messages = provider._build_messages(prompt, system_prompt)
        return provider.chat(messages, temperature=temperature, **kwargs)

    def chat_with_messages(self, messages: List[Dict[str, str]],
                           module: Optional[str] = None,
                           temperature: Optional[float] = None,
                           **kwargs) -> str:
        """
        使用已有消息列表进行对话

        Args:
            messages: 消息列表
            module: 指定模块
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            str: 模型回复
        """
        provider = self.get_provider(module)
        return provider.chat(messages, temperature=temperature, **kwargs)

    def vision_chat(self, image_base64: str,
                   prompt: str,
                   module: Optional[str] = None,
                   system_prompt: Optional[str] = None,
                   **kwargs) -> str:
        """
        视觉对话接口

        Args:
            image_base64: 图片的 base64 编码
            prompt: 提示词
            module: 指定模块
            system_prompt: 系统提示词
            **kwargs: 其他参数

        Returns:
            str: 模型回复
        """
        provider = self.get_provider(module)
        if not provider.supports_vision():
            raise ValueError(f"Provider '{module or 'default'}' 不支持视觉功能")
        return provider.vision_chat(image_base64, prompt, system_prompt, **kwargs)

    def get_provider_info(self, module: Optional[str] = None) -> Dict[str, Any]:
        """获取 Provider 信息"""
        provider = self.get_provider(module)
        return {
            "name": module or "default",
            "type": provider.config.provider_type.value,
            "model": provider.config.model_name,
            "api_base": provider.config.api_base,
            "supports_vision": provider.supports_vision()
        }

    def list_providers(self) -> List[Dict[str, Any]]:
        """列出所有已注册的 Provider"""
        return [
            {
                "name": name,
                "type": provider.config.provider_type.value,
                "model": provider.config.model_name,
                "api_base": provider.config.api_base,
                "supports_vision": provider.supports_vision()
            }
            for name, provider in self._providers.items()
        ]

    def list_module_bindings(self) -> Dict[str, str]:
        """列出模块绑定关系"""
        return self._module_providers.copy()

    @staticmethod
    def create_config(provider_type: ProviderType,
                     api_key: str = None,
                     api_base: str = None,
                     model_name: str = None,
                     **kwargs) -> ProviderConfig:
        """创建 Provider 配置的便捷方法"""
        return ProviderConfig(
            provider_type=provider_type,
            api_key=api_key,
            api_base=api_base or "",
            model_name=model_name or "",
            **kwargs
        )


llm_manager = LLMManager()
