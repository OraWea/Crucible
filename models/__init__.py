"""
Models 模块
包含 LLM 处理、视觉分析、语音识别等核心功能模块
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.llm_core import llm_core, LLMCore
from models.fact_checker import fact_checker, FactChecker
from models.llm_manager import llm_manager, LLMManager
from models.providers import (
    BaseLLMProvider,
    ProviderConfig,
    ProviderType,
    ProviderRegistry,
    DashScopeProvider,
    OpenAIProvider,
    ClaudeProvider,
    LocalProvider,
    create_provider
)

__all__ = [
    'llm_core',
    'LLMCore',
    'fact_checker',
    'FactChecker',
    'llm_manager',
    'LLMManager',
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
