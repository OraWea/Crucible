import os
import re
import logging
from typing import Dict, List, Optional
from Crucible.config import Config

logger = logging.getLogger(__name__)

class FSRouter:
    def __init__(self, vault_path: str = Config.OBSIDIAN_VAULT_PATH):
        self.vault_path = vault_path
        # 建立缓存，映射 "概念名" -> "文件绝对路径"
        self.concept_cache: Dict[str, str] = {}
        self.scan_vault()

    def scan_vault(self):
        """扫描本地 Obsidian 目录，解析所有 .md 文件名及 Frontmatter 中的别名"""
        logger.info(f"开始扫描 Obsidian 知识库: {self.vault_path}")
        self.concept_cache.clear()
        
        if not os.path.exists(self.vault_path):
            os.makedirs(self.vault_path, exist_ok=True)
            return

        # 遍历目录
        for root, dirs, files in os.walk(self.vault_path):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    # 1. 以文件名（不含扩展名）作为默认概念名
                    concept_name = os.path.splitext(file)[0]
                    self.concept_cache[concept_name.lower()] = file_path
                    
                    # 2. 读取文件头部 YAML Frontmatter 提取 alias/别名
                    aliases = self._parse_frontmatter_aliases(file_path)
                    for alias in aliases:
                        self.concept_cache[alias.lower()] = file_path

        logger.info(f"知识库扫描完成，索引了 {len(self.concept_cache)} 个概念路径。")

    def _parse_frontmatter_aliases(self, file_path: str) -> List[str]:
        """解析 markdown 头部 frontmatter 中的别名或标签"""
        aliases = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # 匹配 YAML 格式: 开头 --- 到第二个 ---
            match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
            if match:
                yaml_text = match.group(1)
                # 模糊提取 aliases 行
                alias_match = re.search(r'aliases:\s*\[?(.*?)\]?$', yaml_text, re.MULTILINE | re.IGNORECASE)
                if alias_match:
                    items = alias_match.group(1).split(',')
                    for item in items:
                        cleaned = item.strip().strip('"').strip("'")
                        if cleaned:
                            aliases.append(cleaned)
        except Exception as e:
            logger.warning(f"读取 Frontmatter 失败: {file_path}, {e}")
        return aliases

    def locate_concept_file(self, concept: str) -> Optional[str]:
        """
        查找并定位概念所对应的本地笔记路径。如果存在，返回绝对路径，否则返回 None。
        
        Args:
            concept: 概念名称 (如 'Transformer')
        """
        # 先利用缓存快速检索 (不区分大小写)
        key = concept.strip().lower()
        if key in self.concept_cache:
            path = self.concept_cache[key]
            if os.path.exists(path):
                return path
            else:
                # 缓存失效，重新扫描
                self.scan_vault()
                return self.concept_cache.get(key)
        
        # 缓存中未找到，重新扫描一次以防有新手动创建的文件
        self.scan_vault()
        return self.concept_cache.get(key)

    def get_concept_write_path(self, concept: str) -> str:
        """
        根据概念名称获取应该写入的文件路径。
        如果已存在则返回原路径；如果不存在，则在 vault 根目录下返回 `[概念名].md`
        """
        existing_path = self.locate_concept_file(concept)
        if existing_path:
            return existing_path
        
        # 安全化文件名，移除非法字符
        safe_concept = re.sub(r'[\\/*?:"<>|]', '_', concept).strip()
        return os.path.join(self.vault_path, f"{safe_concept}.md")

    def get_vault_tree_nodes(self) -> List[Dict]:
        """
        以树形结构数据列出所有的 markdown 文件（用于 PyQt6 界面展示）
        """
        nodes = []
        if not os.path.exists(self.vault_path):
            return nodes

        def recurse_dir(dir_path: str) -> List[Dict]:
            items = []
            try:
                for entry in os.scandir(dir_path):
                    if entry.is_dir():
                        children = recurse_dir(entry.path)
                        items.append({
                            "name": entry.name,
                            "type": "directory",
                            "path": entry.path,
                            "children": children
                        })
                    elif entry.is_file() and entry.name.endswith('.md'):
                        items.append({
                            "name": entry.name,
                            "type": "file",
                            "path": entry.path
                        })
            except Exception as e:
                logger.error(f"遍历目录 {dir_path} 出错: {e}")
            # 目录排前面，文件排后面，按名称排序
            items.sort(key=lambda x: (0 if x['type'] == 'directory' else 1, x['name'].lower()))
            return items

        return recurse_dir(self.vault_path)

# 实例化单例
fs_router = FSRouter()
