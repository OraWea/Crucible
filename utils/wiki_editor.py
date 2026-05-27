import os
import shutil
import logging
import datetime
import tempfile
import re
from typing import Optional
from markdown_it import MarkdownIt
from Crucible.config import Config

logger = logging.getLogger(__name__)

class WikiEditor:
    def __init__(self, backup_dir: str = Config.BACKUP_DIR):
        self.backup_dir = backup_dir
        self.md_parser = MarkdownIt()
        os.makedirs(self.backup_dir, exist_ok=True)

    def read_wiki(self, file_path: str) -> str:
        """读取指定笔记的文本内容"""
        if not os.path.exists(file_path):
            return ""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"读取 Wiki 失败: {file_path}, {e}")
            return ""

    def backup_file(self, file_path: str) -> Optional[str]:
        """
        在修改前备份旧文件。备份文件存放在 Config.BACKUP_DIR 中，
        命名称格式为: [原文件名]_backup_[时间戳].md
        """
        if not os.path.exists(file_path):
            return None
        try:
            filename = os.path.basename(file_path)
            name_part, ext = os.path.splitext(filename)
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{name_part}_backup_{timestamp}{ext}"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            shutil.copy2(file_path, backup_path)
            logger.info(f"原文件已成功备份至: {backup_path}")
            return backup_path
        except Exception as e:
            logger.error(f"备份文件失败: {file_path}, {e}")
            return None

    def write_wiki_atomic(self, file_path: str, content: str) -> bool:
        """
        原子化写入 Markdown 文本内容。
        在写入前自动执行备份。先写入同目录下的临时文件，然后使用原子重命名替换原文件，
        以防止写入过程中断（如断电或崩溃）导致数据丢失。
        """
        try:
            # 1. 如果原文件已存在，执行安全备份
            if os.path.exists(file_path) and Config.ENABLE_BACKUP:
                self.backup_file(file_path)

            # 确定所在目录，创建目标目录
            target_dir = os.path.dirname(file_path)
            os.makedirs(target_dir, exist_ok=True)

            # 2. 写入临时文件 (在同一目录下，以保证可以在同一分区中执行原子替换)
            fd, temp_path = tempfile.mkstemp(dir=target_dir, prefix='.crucible_tmp_', suffix='.md')
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                # 3. 原子性替换 (在 Windows 上 os.replace 可以安全覆盖已存在的文件)
                os.replace(temp_path, file_path)
                logger.info(f"原子化写入 Wiki 成功: {file_path}")
                return True
            except Exception as write_err:
                # 出现写入错误，删除临时文件并抛出
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise write_err

        except Exception as e:
            logger.error(f"原子化写入 Wiki 失败: {file_path}, {e}", exc_info=True)
            return False

    def parse_ast(self, content: str) -> list:
        """
        使用 markdown-it-py 解析 Markdown 内容的 AST 标记结构。
        可用以在未来进行段落、标题分析等扩展。
        """
        try:
            tokens = self.md_parser.parse(content)
            return tokens
        except Exception as e:
            logger.error(f"解析 AST 标记树失败: {e}")
            return []

    def extract_wiki_links(self, content: str) -> list:
        """
        从笔记文本中正则解析出所有的 Obsidian 双向链接 (格式为 [[链接概念]])
        """
        # 匹配 [[双向链接]] 或是 [[双向链接|别名]]
        pattern = r'\[\[(.*?)\]\]'
        matches = re.findall(pattern, content)
        links = []
        for match in matches:
            # 如果包含管道符 '|' 别名，取实际的目标概念名
            concept = match.split('|')[0].strip()
            if concept and concept not in links:
                links.append(concept)
        return links

# 实例化单例
wiki_editor = WikiEditor()
