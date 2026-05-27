"""
多 Provider 架构测试脚本

测试功能：
1. Provider 注册和切换
2. 多模块模型配置
3. 向后兼容性
"""

import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

project_name = os.path.basename(current_dir)
sys.modules['Crucible'] = __import__(project_name, fromlist=[''])
sys.modules['Crucible.models'] = __import__('models', fromlist=[''])
sys.modules['Crucible.models.providers'] = __import__('models.providers', fromlist=[''])

def test_provider_creation():
    """测试 Provider 创建"""
    print("=" * 60)
    print("Test 1: Provider Creation")
    print("=" * 60)

    from models.providers import (
        ProviderConfig,
        ProviderType,
        create_provider,
        DashScopeProvider,
        OpenAIProvider,
        LocalProvider
    )

    dashscope_config = ProviderConfig(
        provider_type=ProviderType.DASHSCOPE,
        api_key="test-key",
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus"
    )
    dashscope = create_provider(dashscope_config)
    print(f"[OK] DashScope Provider created: {type(dashscope).__name__}")
    print(f"  - Model: {dashscope.config.model_name}")
    print(f"  - Vision support: {dashscope.supports_vision()}")

    openai_config = ProviderConfig(
        provider_type=ProviderType.OPENAI,
        api_key="test-key",
        api_base="https://api.openai.com/v1",
        model_name="gpt-4o"
    )
    openai = create_provider(openai_config)
    print(f"[OK] OpenAI Provider created: {type(openai).__name__}")
    print(f"  - Model: {openai.config.model_name}")
    print(f"  - Vision support: {openai.supports_vision()}")

    local_config = ProviderConfig(
        provider_type=ProviderType.LOCAL,
        api_base="http://localhost:11434",
        model_name="llama3"
    )
    local = create_provider(local_config)
    print(f"[OK] Local Provider created: {type(local).__name__}")
    print(f"  - Model: {local.config.model_name}")

    print()


def test_llm_manager():
    """测试 LLM Manager"""
    print("=" * 60)
    print("Test 2: LLM Manager")
    print("=" * 60)

    from models.llm_manager import llm_manager
    from models.providers import ProviderType, ProviderConfig

    openai_config = ProviderConfig(
        provider_type=ProviderType.OPENAI,
        api_key="test-openai-key",
        api_base="https://api.openai.com/v1",
        model_name="gpt-4o-mini"
    )
    llm_manager.register_provider("openai-fast", openai_config)

    llm_manager.register_module_provider("concept_extractor", "openai-fast")
    llm_manager.register_module_provider("fact_checker", "default")

    print("[OK] Provider registered")
    print(f"  - Registered providers: {[p['name'] for p in llm_manager.list_providers()]}")
    print(f"  - Module bindings: {llm_manager.list_module_bindings()}")

    default_info = llm_manager.get_provider_info()
    print(f"\n[OK] Default provider info:")
    print(f"  - Type: {default_info['type']}")
    print(f"  - Model: {default_info['model']}")

    concept_info = llm_manager.get_provider_info("concept_extractor")
    print(f"\n[OK] Concept extractor provider info:")
    print(f"  - Type: {concept_info['type']}")
    print(f"  - Model: {concept_info['model']}")

    print()


def test_backward_compatibility():
    """测试向后兼容性"""
    print("=" * 60)
    print("Test 3: Backward Compatibility")
    print("=" * 60)

    from models.llm_manager import llm_manager

    default_provider = llm_manager.get_provider()
    print(f"[OK] Default provider auto-loaded")
    print(f"  - Type: {default_provider.config.provider_type.value}")
    print(f"  - Model: {default_provider.config.model_name}")
    print(f"  - API Base: {default_provider.config.api_base}")

    print()


def test_module_integration():
    """测试模块集成"""
    print("=" * 60)
    print("Test 4: Module Integration (LLMCore, FactChecker)")
    print("=" * 60)

    from models.llm_core import LLMCore
    from models.fact_checker import FactChecker

    llm_core = LLMCore()
    fact_checker = FactChecker()

    print(f"[OK] LLMCore instance created")
    print(f"  - Module name: {llm_core._module_name}")

    print(f"[OK] FactChecker instance created")
    print(f"  - Module name: {fact_checker._module_name}")

    print()


def main():
    print("\n")
    print("============================================================")
    print("       Multi-Provider Architecture Test Suite")
    print("============================================================")
    print()

    try:
        test_provider_creation()
        test_llm_manager()
        test_backward_compatibility()
        test_module_integration()

        print("=" * 60)
        print("[SUCCESS] All tests passed!")
        print("=" * 60)
        print()
        print("Next steps:")
        print("  1. Configure your .env file (see .env.example)")
        print("  2. Run python config_providers_example.py to configure multi-provider")
        print("  3. Restart the application to load new configuration")
        print()

    except Exception as e:
        print(f"\n[FAILED] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
