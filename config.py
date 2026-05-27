import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    OBSIDIAN_VAULT_PATH = os.environ.get('OBSIDIAN_VAULT_PATH') or os.path.join(BASE_DIR, 'data', 'vault')

    DATABASE_PATH = os.environ.get('DATABASE_PATH') or os.path.join(BASE_DIR, 'data', 'crucible.db')

    TEMP_DIR = os.path.join(BASE_DIR, 'temp')
    LOG_FILE = os.path.join(BASE_DIR, 'app.log')

    WHISPER_MODEL_NAME = os.environ.get('WHISPER_MODEL_NAME') or 'base'
    WHISPER_DEVICE = os.environ.get('WHISPER_DEVICE') or 'cuda'

    VLM_MODEL_ID = os.environ.get('VLM_MODEL_ID') or 'Qwen/Qwen2-VL-7B-Instruct'
    VLM_DEVICE = os.environ.get('VLM_DEVICE') or 'cuda'

    # LLM Provider 配置
    # 主 Provider (默认使用阿里百炼，保持向后兼容)
    LLM_API_KEY = os.environ.get('LLM_API_KEY') or os.environ.get('OPENAI_API_KEY') or 'your-api-key'
    LLM_API_BASE = os.environ.get('LLM_API_BASE') or 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME') or 'qwen-plus'
    LLM_TIMEOUT = int(os.environ.get('LLM_TIMEOUT', '60'))
    LLM_MAX_TOKENS = int(os.environ.get('LLM_MAX_TOKENS', '2048')) if os.environ.get('LLM_MAX_TOKENS') else None

    # OpenAI Provider 配置 (可选)
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_API_BASE = os.environ.get('OPENAI_API_BASE') or 'https://api.openai.com/v1'
    OPENAI_MODEL_NAME = os.environ.get('OPENAI_MODEL_NAME') or 'gpt-4o'

    # Claude Provider 配置 (可选)
    CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')
    CLAUDE_API_BASE = os.environ.get('CLAUDE_API_BASE') or 'https://api.anthropic.com'
    CLAUDE_MODEL_NAME = os.environ.get('CLAUDE_MODEL_NAME') or 'claude-3-5-sonnet-20241022'

    # Ollama 配置 (可选)
    OLLAMA_API_BASE = os.environ.get('OLLAMA_API_BASE') or 'http://localhost:11434'
    OLLAMA_MODEL_NAME = os.environ.get('OLLAMA_MODEL_NAME') or 'llama3'

    # LM Studio 配置 (可选)
    LMSTUDIO_API_BASE = os.environ.get('LMSTUDIO_API_BASE') or 'http://localhost:1234/v1'
    LMSTUDIO_MODEL_NAME = os.environ.get('LMSTUDIO_MODEL_NAME') or 'local-model'

    # 模块级配置
    CONCEPT_EXTRACTOR_PROVIDER = os.environ.get('CONCEPT_EXTRACTOR_PROVIDER', 'default')
    CONCEPT_EXTRACTOR_MODEL = os.environ.get('CONCEPT_EXTRACTOR_MODEL')

    FACT_CHECKER_PROVIDER = os.environ.get('FACT_CHECKER_PROVIDER', 'default')
    FACT_CHECKER_MODEL = os.environ.get('FACT_CHECKER_MODEL')

    WIKI_MERGER_PROVIDER = os.environ.get('WIKI_MERGER_PROVIDER', 'default')
    WIKI_MERGER_MODEL = os.environ.get('WIKI_MERGER_MODEL')

    SUPPORTED_VIDEO_FORMATS = ['.mp4', '.mkv', '.avi', '.mov', '.webm']
    SUPPORTED_AUDIO_FORMATS = ['.mp3', '.wav', '.m4a', '.flac', '.aac']
    SUPPORTED_DOC_FORMATS = ['.pdf', '.txt', '.md']

    ENABLE_BACKUP = True
    BACKUP_DIR = os.path.join(BASE_DIR, 'data', 'backups')

    @staticmethod
    def init_paths():
        os.makedirs(Config.OBSIDIAN_VAULT_PATH, exist_ok=True)
        os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
        os.makedirs(Config.TEMP_DIR, exist_ok=True)
        os.makedirs(Config.BACKUP_DIR, exist_ok=True)
