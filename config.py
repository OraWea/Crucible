import os
from dotenv import load_dotenv

# 加载 .env 配置文件
load_dotenv()

class Config:
    # 基础路径配置
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Obsidian Vault 本地绝对路径 (默认保存在 Crucible/data/vault 中)
    OBSIDIAN_VAULT_PATH = os.environ.get('OBSIDIAN_VAULT_PATH') or os.path.join(BASE_DIR, 'data', 'vault')
    
    # 数据库路径 (仅用于存储系统操作日志与任务指标)
    DATABASE_PATH = os.environ.get('DATABASE_PATH') or os.path.join(BASE_DIR, 'data', 'crucible.db')
    
    # 临时文件夹与日志路径
    TEMP_DIR = os.path.join(BASE_DIR, 'temp')
    LOG_FILE = os.path.join(BASE_DIR, 'app.log')
    
    # ASR Whisper 模型设置
    WHISPER_MODEL_NAME = os.environ.get('WHISPER_MODEL_NAME') or 'base'
    WHISPER_DEVICE = os.environ.get('WHISPER_DEVICE') or 'cuda' # 有N卡且显存够推荐 'cuda'，否则 'cpu'
    
    # VLM 视觉大模型设置 (本地运行推荐 Qwen/Qwen2-VL-7B-Instruct，也可以使用 API 形式)
    VLM_MODEL_ID = os.environ.get('VLM_MODEL_ID') or 'Qwen/Qwen2-VL-7B-Instruct'
    VLM_DEVICE = os.environ.get('VLM_DEVICE') or 'cuda'
    
    # LLM (Qwen API/本地双模适配)
    # 本地加载大模型显存开销极大，因此在 MVP 阶段推荐使用 OpenAI 兼容格式的 API 进行开发与调试，
    # 可直接对接 LM Studio、Ollama、或 DashScope 等云端服务。
    LLM_API_KEY = os.environ.get('LLM_API_KEY') or 'your-api-key'
    LLM_API_BASE = os.environ.get('LLM_API_BASE') or 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME') or 'qwen-plus' # 可更换为 qwen2.5-72b-instruct 等
    
    # 支持处理的文件格式
    SUPPORTED_VIDEO_FORMATS = ['.mp4', '.mkv', '.avi', '.mov', '.webm']
    SUPPORTED_AUDIO_FORMATS = ['.mp3', '.wav', '.m4a', '.flac', '.aac']
    SUPPORTED_DOC_FORMATS = ['.pdf', '.txt', '.md']
    
    # 覆盖与安全设定
    ENABLE_BACKUP = True # 覆写旧笔记前是否创建本地备份备份
    BACKUP_DIR = os.path.join(BASE_DIR, 'data', 'backups')

    @staticmethod
    def init_paths():
        """初始化项目所需的各文件夹路径"""
        os.makedirs(Config.OBSIDIAN_VAULT_PATH, exist_ok=True)
        os.makedirs(os.path.dirname(Config.DATABASE_PATH), exist_ok=True)
        os.makedirs(Config.TEMP_DIR, exist_ok=True)
        os.makedirs(Config.BACKUP_DIR, exist_ok=True)
