"""
多模型 Provider 配置示例

这个文件展示了如何配置多个不同的 LLM Provider，
并为不同模块指定专属的模型。
"""
from Crucible.models.llm_manager import llm_manager
from Crucible.models.providers import (
    ProviderType,
    ProviderConfig,
    create_provider
)

def setup_multi_provider_config():
    """
    配置多个 Provider 的示例

    使用场景：
    - 概念提取使用高性能模型（如 GPT-4o）
    - 事实检查使用快速便宜的模型（如 GPT-3.5-turbo）
    - 视觉分析使用专门的视觉模型（如 Claude 3.5 Sonnet）
    - 本地开发使用 Ollama 节省成本
    """
    # 1. 配置阿里百炼（默认）
    dashscope_config = ProviderConfig(
        provider_type=ProviderType.DASHSCOPE,
        api_key="your-dashscope-api-key",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus",
        timeout=60,
        max_tokens=2048,
        temperature=0.2
    )
    llm_manager.register_provider("dashscope", dashscope_config, set_default=True)

    # 2. 配置 OpenAI
    openai_config = ProviderConfig(
        provider_type=ProviderType.OPENAI,
        api_key="your-openai-api-key",
        api_base="https://api.openai.com/v1",
        model_name="gpt-4o",
        timeout=60,
        max_tokens=4096,
        temperature=0.2
    )
    llm_manager.register_provider("openai-gpt4", openai_config)

    # 3. 配置 Claude
    claude_config = ProviderConfig(
        provider_type=ProviderType.CLAUDE,
        api_key="your-anthropic-api-key",
        api_base="https://api.anthropic.com",
        model_name="claude-3-5-sonnet-20241022",
        timeout=60,
        max_tokens=4096,
        temperature=0.2
    )
    llm_manager.register_provider("claude", claude_config)

    # 4. 配置本地 Ollama
    ollama_config = ProviderConfig(
        provider_type=ProviderType.LOCAL,
        api_base="http://localhost:11434",
        model_name="llama3",
        timeout=120,
        temperature=0.2
    )
    llm_manager.register_provider("ollama", ollama_config)

    # 5. 配置本地 LM Studio
    lmstudio_config = ProviderConfig(
        provider_type=ProviderType.LOCAL,
        api_base="http://localhost:1234/v1",
        model_name="local-model",
        timeout=120,
        temperature=0.2
    )
    llm_manager.register_provider("lmstudio", lmstudio_config)

    # 6. 为不同模块绑定专属 Provider
    llm_manager.register_module_provider("concept_extractor", "openai-gpt4")
    llm_manager.register_module_provider("fact_checker", "dashscope")
    llm_manager.register_module_provider("wiki_merger", "claude")

    print("已配置多 Provider 环境：")
    print("-" * 60)
    for provider_info in llm_manager.list_providers():
        print(f"  • {provider_info['name']}: {provider_info['type']} - {provider_info['model']}")

    print("\n模块绑定关系：")
    print("-" * 60)
    for module, provider in llm_manager.list_module_bindings().items():
        print(f"  • {module} -> {provider}")

def setup_simple_config():
    """
    简单配置示例 - 保持向后兼容
    只使用阿里百炼，不需要额外配置
    """
    pass

if __name__ == "__main__":
    setup_multi_provider_config()

    print("\n当前 Provider 信息：")
    print("-" * 60)
    print(llm_manager.get_provider_info())
