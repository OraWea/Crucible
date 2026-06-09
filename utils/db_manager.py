import sqlite3
import os
import datetime
import logging
from Crucible.config import Config

logger = logging.getLogger(__name__)

class DBManager:
    def __init__(self, db_path: str = Config.DATABASE_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        # 启用行字典访问方式，便于转化成 dict
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """初始化 SQLite 数据库及创建日志表"""
        try:
            # 确保父级目录存在
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # 创建 operation_logs 日志表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS operation_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        level TEXT NOT NULL,
                        module TEXT NOT NULL,
                        action TEXT NOT NULL,
                        detail TEXT,
                        duration REAL,
                        token_cost INTEGER
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_name TEXT NOT NULL,
                        source_type TEXT NOT NULL,
                        source_uri TEXT NOT NULL,
                        source_hash TEXT NOT NULL UNIQUE,
                        duration REAL,
                        source_note_path TEXT NOT NULL,
                        asr_engine TEXT,
                        vlm_model TEXT,
                        metadata_json TEXT DEFAULT '{}',
                        keyframes_json TEXT DEFAULT '[]',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                cursor.execute("PRAGMA table_info(sources)")
                source_columns = {row["name"] for row in cursor.fetchall()}
                if "metadata_json" not in source_columns:
                    cursor.execute("ALTER TABLE sources ADD COLUMN metadata_json TEXT DEFAULT '{}'")
                if "keyframes_json" not in source_columns:
                    cursor.execute("ALTER TABLE sources ADD COLUMN keyframes_json TEXT DEFAULT '[]'")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS segments (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_id INTEGER NOT NULL,
                        start_time REAL NOT NULL,
                        end_time REAL NOT NULL,
                        text TEXT NOT NULL,
                        timestamp_label TEXT NOT NULL,
                        sort_order INTEGER NOT NULL,
                        FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
                    )
                """)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS concept_mentions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_id INTEGER NOT NULL,
                        concept_name TEXT NOT NULL,
                        segment_id INTEGER,
                        timestamp_label TEXT NOT NULL,
                        source_note_path TEXT NOT NULL,
                        FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE,
                        FOREIGN KEY(segment_id) REFERENCES segments(id) ON DELETE SET NULL
                    )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_segments_text ON segments(text)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_concept_mentions_name ON concept_mentions(concept_name)")
                conn.commit()
            logger.info("SQLite 数据库初始化成功。")
        except Exception as e:
            logger.error(f"SQLite 初始化失败: {e}", exc_info=True)
            raise

    def add_log(self, level: str, module: str, action: str, detail: str = None, 
                duration: float = None, token_cost: int = None):
        """
        向数据库添加一条运行日志
        
        Args:
            level: 日志级别 (INFO, WARNING, ERROR, CRITICAL)
            module: 触发日志的模块名 (e.g. 'ASR', 'LLM_Core', 'GUI')
            action: 具体操作行为 (e.g. 'Transcribe_Start', 'Wiki_Weave_Success')
            detail: 详细描述或报错信息
            duration: 耗时秒数 (可选)
            token_cost: Token 消耗数 (可选)
        """
        try:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO operation_logs (timestamp, level, module, action, detail, duration, token_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timestamp, level, module, action, detail, duration, token_cost))
                conn.commit()
        except Exception as e:
            # 防止写入日志本身报错导致系统崩溃
            logger.error(f"写入操作日志到 SQLite 失败: {e}")

    def get_logs(self, limit: int = 100, level_filter: str = None, keyword: str = None) -> list:
        """
        检索日志记录 (为管理员提供审计查询)
        
        Args:
            limit: 最大返回行数
            level_filter: 过滤特定级别的日志 (如 'ERROR')
            keyword: 关键字模糊搜索 (匹配 action 或 detail)
        """
        try:
            query = "SELECT * FROM operation_logs WHERE 1=1"
            params = []
            
            if level_filter:
                query += " AND level = ?"
                params.append(level_filter)
                
            if keyword:
                query += " AND (action LIKE ? OR detail LIKE ?)"
                keyword_param = f"%{keyword}%"
                params.extend([keyword_param, keyword_param])
                
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = cursor.fetchall()
                # 转化为常规字典列表输出
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"查询操作日志失败: {e}")
            return []

    def clear_logs(self):
        """清空日志数据"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM operation_logs")
                conn.commit()
            logger.info("系统日志已清空。")
        except Exception as e:
            logger.error(f"清空日志失败: {e}")

# 单例实例化
db_manager = DBManager()
