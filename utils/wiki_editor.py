import os
import shutil
import logging
import datetime
import tempfile
import re
import hashlib
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional
from urllib.parse import quote
from markdown_it import MarkdownIt
from Crucible.config import Config

logger = logging.getLogger(__name__)

class WikiEditor:
    PREVIEW_CACHE_LIMIT = 32

    def __init__(self, backup_dir: str = Config.BACKUP_DIR):
        self.backup_dir = backup_dir
        self.md_parser = MarkdownIt("commonmark", {"html": False})
        self._preview_cache: OrderedDict[str, str] = OrderedDict()
        self._preview_cache_lock = threading.RLock()
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
        links = []
        for item in self.extract_wiki_link_items(content):
            target = item["target"]
            if target and target not in links:
                links.append(target)
        return links

    def extract_wiki_link_items(self, content: str) -> List[Dict[str, str]]:
        """解析 [[Note]]、[[Note|Alias]]、[[Note#Heading|Label]]。"""
        items = []
        for match in re.findall(r'\[\[(.*?)\]\]', content or ""):
            raw_target, alias = (match.split("|", 1) + [""])[:2] if "|" in match else (match, "")
            target, anchor = (raw_target.split("#", 1) + [""])[:2] if "#" in raw_target else (raw_target, "")
            target = target.strip()
            anchor = anchor.strip()
            alias = alias.strip()
            items.append({
                "raw": match.strip(),
                "target": target,
                "anchor": anchor,
                "alias": alias,
                "label": alias or anchor or target,
            })
        return items

    def read_frontmatter(self, content: str) -> Dict[str, Any]:
        """读取简单 YAML frontmatter，支持标量和一维列表。"""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n?', content or "", re.DOTALL)
        if not match:
            return {}
        data: Dict[str, Any] = {}
        for line in match.group(1).splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                data[key] = [
                    item.strip().strip('"').strip("'")
                    for item in value[1:-1].split(",")
                    if item.strip()
                ]
            else:
                data[key] = value.strip('"').strip("'")
        return data

    def render_markdown_preview(self, content: str) -> str:
        """将 Markdown 渲染为 HTML，并把 Obsidian 双链转换为可点击链接。"""
        content = content or ""
        cache_key = self._preview_cache_key(content)
        cached = self._get_preview_cache(cache_key)
        if cached is not None:
            return cached

        def replace_link(match):
            item = self.extract_wiki_link_items(f"[[{match.group(1)}]]")[0]
            href = quote(item["raw"], safe="")
            return f"[{item['label']}](crucible://note/{href})"

        normalized = re.sub(r'\[\[(.*?)\]\]', replace_link, content)
        rendered = self._sanitize_rendered_html(self.md_parser.render(normalized))
        self._set_preview_cache(cache_key, rendered)
        return rendered

    def _preview_cache_key(self, content: str) -> str:
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return f"{len(content)}:{digest}"

    def _get_preview_cache(self, key: str) -> Optional[str]:
        with self._preview_cache_lock:
            value = self._preview_cache.get(key)
            if value is None:
                return None
            self._preview_cache.move_to_end(key)
            return value

    def _set_preview_cache(self, key: str, html: str) -> None:
        with self._preview_cache_lock:
            self._preview_cache[key] = html
            self._preview_cache.move_to_end(key)
            while len(self._preview_cache) > self.PREVIEW_CACHE_LIMIT:
                self._preview_cache.popitem(last=False)

    def _sanitize_rendered_html(self, html: str) -> str:
        """限制 Markdown 链接协议，原生 HTML 已由 markdown-it 禁用。"""
        allowed = ("http://", "https://", "mailto:", "crucible://note/", "#")

        def clean_href(match):
            quote_char = match.group(1)
            href = match.group(2).strip()
            if href.startswith(allowed):
                return f'href={quote_char}{href}{quote_char}'
            return f'href={quote_char}#{quote_char}'

        return re.sub(r'href=(["\'])(.*?)\1', clean_href, html, flags=re.IGNORECASE)

    def update_frontmatter_fields(self, content: str, fields: Dict[str, Any]) -> str:
        """更新或创建 Markdown YAML frontmatter 中的简单标量字段。"""
        field_lines = [f"{key}: {value}" for key, value in fields.items()]
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n?', content, re.DOTALL)

        if not match:
            return "---\n" + "\n".join(field_lines) + "\n---\n\n" + content.lstrip()

        yaml_text = match.group(1)
        body = content[match.end():]
        for key, value in fields.items():
            pattern = rf'^{re.escape(key)}:\s*.*$'
            replacement = f"{key}: {value}"
            if re.search(pattern, yaml_text, flags=re.MULTILINE):
                yaml_text = re.sub(pattern, replacement, yaml_text, flags=re.MULTILINE)
            else:
                yaml_text = yaml_text.rstrip() + f"\n{replacement}"

        return f"---\n{yaml_text.strip()}\n---\n{body}"

    def update_frontmatter_list_fields(self, content: str, fields: Dict[str, list]) -> str:
        """合并更新 frontmatter 中的一维字符串列表字段。"""
        scalar_fields = {}
        for key, values in fields.items():
            existing_values = self._read_frontmatter_list(content, key)
            merged = []
            for value in existing_values + [str(item) for item in values if item]:
                if value not in merged:
                    merged.append(value)
            quoted = [f'"{item.replace(chr(34), chr(92) + chr(34))}"' for item in merged]
            scalar_fields[key] = "[" + ", ".join(quoted) + "]"
        return self.update_frontmatter_fields(content, scalar_fields)

    def _read_frontmatter_list(self, content: str, key: str) -> list:
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n?', content, re.DOTALL)
        if not match:
            return []
        yaml_text = match.group(1)
        field_match = re.search(rf'^{re.escape(key)}:\s*\[(.*?)\]\s*$', yaml_text, re.MULTILINE)
        if not field_match:
            return []
        raw_items = field_match.group(1).split(",")
        return [item.strip().strip('"').strip("'") for item in raw_items if item.strip()]

# 实例化单例
wiki_editor = WikiEditor()
