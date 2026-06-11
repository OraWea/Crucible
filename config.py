import json
import os
try:
    from dotenv import load_dotenv
    # 加载 .env 配置文件
    load_dotenv()
except ImportError:
    pass

class Config:
    # 基础路径配置
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Obsidian Vault 本地绝对路径 (默认保存在 Crucible/data/vault 中)
    OBSIDIAN_VAULT_PATH = os.environ.get('OBSIDIAN_VAULT_PATH') or os.path.join(BASE_DIR, 'data', 'vault')
    
    # 数据库路径 (仅用于存储系统操作日志与任务指标)
    DATABASE_PATH = os.environ.get('DATABASE_PATH') or os.path.join(BASE_DIR, 'data', 'crucible.db')
    LOCAL_SETTINGS_PATH = os.environ.get('LOCAL_SETTINGS_PATH') or os.path.join(BASE_DIR, 'data', 'local_settings.json')
    
    # 临时文件夹与日志路径
    TEMP_DIR = os.path.join(BASE_DIR, 'temp')
    LOG_FILE = os.path.join(BASE_DIR, 'app.log')

    # yt-dlp 在线媒体下载配置。Cookies 文件可用浏览器导出，路径不要提交到仓库。
    YTDLP_COOKIES_FILE = os.environ.get('YTDLP_COOKIES_FILE') or os.environ.get('BILIBILI_COOKIES_FILE') or ''
    YTDLP_USER_AGENT = os.environ.get('YTDLP_USER_AGENT') or (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    )
    
    # ASR Whisper 模型设置
    WHISPER_MODEL_NAME = os.environ.get('WHISPER_MODEL_NAME') or 'base'
    WHISPER_DEVICE = os.environ.get('WHISPER_DEVICE') or 'cuda' # 有N卡且显存够推荐 'cuda'，否则 'cpu'
    
    # VLM 视觉大模型设置 (本地路径或 HuggingFace Hub ID，也可以使用 API 形式)
    # 默认指向本地已下载的 Qwen2-VL-2B-Instruct 权重目录
    VLM_MODEL_ID = os.environ.get('VLM_MODEL_ID') or os.path.join(BASE_DIR, 'Qwen2-VL-2B-Instruct')
    VLM_DEVICE = os.environ.get('VLM_DEVICE') or 'cuda'
    
    # LLM (Qwen API/本地双模适配)
    # 本地加载大模型显存开销极大，因此在 MVP 阶段推荐使用 OpenAI 兼容格式的 API 进行开发与调试，
    # 可直接对接 LM Studio、Ollama、或 DashScope 等云端服务。
    LLM_API_KEY = os.environ.get('LLM_API_KEY') or 'your-api-key'
    LLM_API_BASE = os.environ.get('LLM_API_BASE') or 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME') or 'qwen-plus' # 可更换为 qwen2.5-72b-instruct 等
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER') or 'dashscope'
    VLM_MODEL_NAME = os.environ.get('VLM_MODEL_NAME') or os.environ.get('LLM_MODEL_NAME') or 'qwen-vl-plus'
    FACT_CHECKER_MODEL_NAME = os.environ.get('FACT_CHECKER_MODEL_NAME') or os.environ.get('LLM_MODEL_NAME') or 'qwen-plus'

    PROVIDER_PRESETS = {
        'openai': {
            'label': 'OpenAI',
            'api_base': 'https://api.openai.com/v1',
            'model': 'gpt-4o-mini',
            'vlm_model': 'gpt-4o-mini',
        },
        'dashscope': {
            'label': 'DashScope / Qwen',
            'api_base': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'model': 'qwen-plus',
            'vlm_model': 'qwen-vl-plus',
        },
        'deepseek': {
            'label': 'DeepSeek',
            'api_base': 'https://api.deepseek.com',
            'model': 'deepseek-chat',
            'vlm_model': 'deepseek-chat',
        },
        'moonshot': {
            'label': 'Moonshot / Kimi',
            'api_base': 'https://api.moonshot.cn/v1',
            'model': 'moonshot-v1-8k',
            'vlm_model': 'moonshot-v1-8k',
        },
        'zhipu': {
            'label': 'Zhipu / GLM',
            'api_base': 'https://open.bigmodel.cn/api/paas/v4',
            'model': 'glm-4-flash',
            'vlm_model': 'glm-4v-flash',
        },
        'openrouter': {
            'label': 'OpenRouter',
            'api_base': 'https://openrouter.ai/api/v1',
            'model': 'openai/gpt-4o-mini',
            'vlm_model': 'openai/gpt-4o-mini',
        },
        'ollama': {
            'label': 'Ollama (local)',
            'api_base': 'http://127.0.0.1:11434/v1',
            'model': 'qwen2.5:7b',
            'vlm_model': 'llava:7b',
        },
        'lmstudio': {
            'label': 'LM Studio (local)',
            'api_base': 'http://127.0.0.1:1234/v1',
            'model': 'local-model',
            'vlm_model': 'local-model',
        },
        'custom': {
            'label': 'Custom OpenAI-compatible',
            'api_base': LLM_API_BASE,
            'model': LLM_MODEL_NAME,
            'vlm_model': VLM_MODEL_NAME,
        },
    }
    LOCAL_PROVIDERS = {'ollama', 'lmstudio'}
    
    # 支持处理的文件格式
    SUPPORTED_VIDEO_FORMATS = ['.mp4', '.mkv', '.avi', '.mov', '.webm']
    SUPPORTED_AUDIO_FORMATS = ['.mp3', '.wav', '.m4a', '.flac', '.aac']
    SUPPORTED_DOC_FORMATS = ['.pdf', '.txt', '.md']
    
    # 覆盖与安全设定
    ENABLE_BACKUP = True # 覆写旧笔记前是否创建本地备份备份
    BACKUP_DIR = os.path.join(BASE_DIR, 'data', 'backups')
    TRASH_DIR = os.path.join(BACKUP_DIR, 'trash')

    @staticmethod
    def is_local_provider(provider: str = None) -> bool:
        """判断 Provider 是否为本地 OpenAI-compatible 服务。"""
        return (provider or Config.LLM_PROVIDER) in Config.LOCAL_PROVIDERS

    @staticmethod
    def has_valid_api_key(api_key: str = None, provider: str = None) -> bool:
        """判断 API Key 是否可用于云端模型调用。"""
        if Config.is_local_provider(provider):
            return True
        value = api_key if api_key is not None else Config.LLM_API_KEY
        return bool(value and value.strip() and value.strip() != 'your-api-key')

    @staticmethod
    def mask_secret(value: str = None) -> str:
        """脱敏展示 API Key 或其他敏感短文本。"""
        if not value:
            return ""
        cleaned = str(value).strip()
        if not cleaned:
            return ""
        if len(cleaned) <= 8:
            return "***"
        return f"{cleaned[:4]}...{cleaned[-4:]}"

    @staticmethod
    def redact_secrets(text: str) -> str:
        """从日志/错误消息中移除当前运行期 API Key。"""
        message = "" if text is None else str(text)
        api_key = (Config.LLM_API_KEY or "").strip()
        if api_key and api_key != "your-api-key":
            message = message.replace(api_key, Config.mask_secret(api_key))
        return message.replace("your-api-key", "<placeholder-api-key>")

    @staticmethod
    def init_paths():
        """初始化项目所需的各文件夹路径"""
        os.makedirs(Config.OBSIDIAN_VAULT_PATH, exist_ok=True)
        os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
        os.makedirs(os.path.dirname(Config.LOCAL_SETTINGS_PATH), exist_ok=True)
        os.makedirs(Config.TEMP_DIR, exist_ok=True)
        os.makedirs(Config.BACKUP_DIR, exist_ok=True)
        os.makedirs(Config.TRASH_DIR, exist_ok=True)

    @staticmethod
    def update_llm_runtime(
        api_key: str = None,
        api_base: str = None,
        model_name: str = None,
        provider: str = None,
        vlm_model_name: str = None,
        fact_checker_model_name: str = None,
        vlm_model_id: str = None,
    ):
        """更新运行期 LLM 配置，供 GUI 临时覆盖使用。"""
        if api_key is not None:
            Config.LLM_API_KEY = api_key
        if api_base is not None:
            Config.LLM_API_BASE = api_base
        if model_name is not None:
            Config.LLM_MODEL_NAME = model_name
        if provider is not None:
            Config.LLM_PROVIDER = provider
        if vlm_model_name is not None:
            Config.VLM_MODEL_NAME = vlm_model_name
        if fact_checker_model_name is not None:
            Config.FACT_CHECKER_MODEL_NAME = fact_checker_model_name
        if vlm_model_id is not None:
            Config.VLM_MODEL_ID = vlm_model_id

    @staticmethod
    def load_local_settings():
        """载入本地运行配置；该文件应被 git 忽略，可保存真实 API Key。"""
        if not os.path.exists(Config.LOCAL_SETTINGS_PATH):
            return

        try:
            with open(Config.LOCAL_SETTINGS_PATH, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            return

        Config.update_llm_runtime(
            api_key=settings.get("api_key"),
            api_base=settings.get("api_base"),
            model_name=settings.get("llm_model"),
            provider=settings.get("provider"),
            vlm_model_name=settings.get("vlm_model"),
            fact_checker_model_name=settings.get("fact_model"),
            vlm_model_id=settings.get("vlm_model_id"),
        )
        if settings.get("vault_path"):
            Config.OBSIDIAN_VAULT_PATH = settings["vault_path"]
        if settings.get("whisper_model"):
            Config.WHISPER_MODEL_NAME = settings["whisper_model"]
        if settings.get("whisper_device"):
            Config.WHISPER_DEVICE = settings["whisper_device"]

    @staticmethod
    def save_local_settings(
        provider: str,
        api_base: str,
        llm_model: str,
        vlm_model: str,
        fact_model: str,
        api_key: str = None,
        whisper_model: str = None,
        whisper_device: str = None,
        vlm_model_id: str = None,
    ):
        """保存 GUI 中的模型配置到本地配置文件。"""
        os.makedirs(os.path.dirname(Config.LOCAL_SETTINGS_PATH), exist_ok=True)
        if whisper_model is not None:
            Config.WHISPER_MODEL_NAME = whisper_model
        if whisper_device is not None:
            Config.WHISPER_DEVICE = whisper_device
        if vlm_model_id is not None:
            Config.VLM_MODEL_ID = vlm_model_id

        settings = {
            "provider": provider,
            "api_base": api_base,
            "llm_model": llm_model,
            "vlm_model": vlm_model,
            "fact_model": fact_model,
            "vault_path": Config.OBSIDIAN_VAULT_PATH,
            "whisper_model": Config.WHISPER_MODEL_NAME,
            "whisper_device": Config.WHISPER_DEVICE,
            "vlm_model_id": Config.VLM_MODEL_ID,
        }
        if api_key:
            settings["api_key"] = api_key
        elif os.path.exists(Config.LOCAL_SETTINGS_PATH):
            try:
                with open(Config.LOCAL_SETTINGS_PATH, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if existing.get("api_key"):
                    settings["api_key"] = existing["api_key"]
            except Exception:
                settings.pop("api_key", None)

        with open(Config.LOCAL_SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)

    @staticmethod
    def get_provider_options():
        """返回 GUI 可展示的 Provider 选项。"""
        return [(key, value['label']) for key, value in Config.PROVIDER_PRESETS.items()]

    @staticmethod
    def get_provider_preset(provider: str):
        """按 Provider key 获取 OpenAI-compatible 预设。"""
        if provider == 'custom':
            return {
                'label': 'Custom OpenAI-compatible',
                'api_base': Config.LLM_API_BASE,
                'model': Config.LLM_MODEL_NAME,
                'vlm_model': Config.VLM_MODEL_NAME,
            }
        return Config.PROVIDER_PRESETS.get(provider, Config.PROVIDER_PRESETS['custom'])


Config.load_local_settings()
