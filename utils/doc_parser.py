import os
import logging
from pypdf import PdfReader

logger = logging.getLogger(__name__)

class DocParser:
    def parse_file(self, file_path: str) -> str:
        """
        根据文件类型解析文本内容
        
        Args:
            file_path: 本地文档路径
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"未找到输入文档: {file_path}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.pdf':
            return self._parse_pdf(file_path)
        elif ext in ['.txt', '.md']:
            return self._parse_text(file_path)
        else:
            raise ValueError(f"不支持的文档类型: {ext}")

    def _parse_pdf(self, file_path: str) -> str:
        """解析 PDF 并提取文本"""
        try:
            logger.info(f"解析 PDF 文档中: {file_path}")
            reader = PdfReader(file_path)
            text_list = []
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_list.append(page_text)
            
            combined_text = "\n\n".join(text_list)
            logger.info(f"PDF 解析成功，共提取 {len(reader.pages)} 页，字数: {len(combined_text)}")
            return combined_text
        except Exception as e:
            logger.error(f"PDF 解析失败: {e}", exc_info=True)
            raise

    def _parse_text(self, file_path: str) -> str:
        """解析 TXT 或 MD 并提取文本"""
        try:
            logger.info(f"解析文本文件: {file_path}")
            # 尝试常见编码载入文本
            encodings = ['utf-8', 'gbk', 'gb18030', 'utf-16']
            for enc in encodings:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        text = f.read()
                    logger.info(f"成功使用 {enc} 编码读取文本。")
                    return text
                except UnicodeDecodeError:
                    continue
            raise UnicodeDecodeError("所有常用编码格式均解析文本失败，请确保文件是合法的文本内容。")
        except Exception as e:
            logger.error(f"文本读取失败: {e}", exc_info=True)
            raise

# 实例化单例
doc_parser = DocParser()
