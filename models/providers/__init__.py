"""
LLM Provider 模块
支持多种API Provider：DashScope、OpenAI、Claude、本地模型等
"""
from .base import (
    BaseLLMProvider,
    ProviderConfig,
    ProviderType,
    ProviderRegistry
)

from .dashscope import DashScopeProvider
from .openai import OpenAIProvider
from .claude import ClaudeProvider
from .local import LocalProvider

PROVIDER_CLASSES = {
    ProviderType.DASHSCOPE: DashScopeProvider,
    ProviderType.OPENAI: OpenAIProvider,
    ProviderType.CLAUDE: ClaudeProvider,
    ProviderType.LOCAL: LocalProvider,
}

def create_provider(config: ProviderConfig) -> BaseLLMProvider:
    """根据配置创建 Provider 实例"""
    provider_class = PROVIDER_CLASSES.get(config.provider_type)
    if not provider_class:
        raise ValueError(f"不支持的 Provider 类型: {config.provider_type}")
    return provider_class(config)

__all__ = [
    'BaseLLMProvider',
    'ProviderConfig',
    'ProviderType',
    'ProviderRegistry',
    'DashScopeProvider',
    'OpenAIProvider',
    'ClaudeProvider',
    'LocalProvider',
    'create_provider'
]
