import os
import logging
import time
import datetime
import re
from typing import Dict, Any, List
from Crucible.utils.db_manager import db_manager
from Crucible.utils.fs_router import fs_router
from Crucible.utils.wiki_editor import wiki_editor
from Crucible.models.api_client import ProviderUnavailableError, llm_client, parse_json_response, strip_code_fence

logger = logging.getLogger(__name__)

class LLMCore:
    def __init__(self):
        self.client = llm_client

    @property
    def api_key(self) -> str:
        return self.client.api_key

    @api_key.setter
    def api_key(self, value: str) -> None:
        self.client.configure(api_key=value)

    def _call_api(self, prompt: str, system_prompt: str = "你是一个智能的个人第二大脑知识库助手。") -> str:
        """底层封装的 API 调用接口"""
        return self.client.chat(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            timeout=60,
        )

    def extract_concepts(self, raw_input_text: str) -> List[Dict[str, Any]]:
        """
        阶段一：从输入文本中抽取核心学术名词和技术点
        
        Returns:
            List[Dict]: 概念结构列表，如 [{'concept': 'Transformer', 'definition': '...', ...}]
        """
        logger.info("开始执行 [阶段一: 核心概念抽取]...")
        db_manager.add_log("INFO", "LLM", "Extract_Start", f"输入字数: {len(raw_input_text)}")
        
        start_time = time.time()
        
        system_prompt = "你是一个专业的知识图谱抽取专家。你擅长从各种类型的文本、音频转录和图像描述中识别出核心主题和知识概念。"
        vault_structure = fs_router.get_vault_structure_summary()
        organization_rules = fs_router.read_organization_rules()
        
        prompt = f"""请分析以下非结构化文本，提取出其中讨论的所有核心主题、概念、人物、专有名词或关键知识点。
内容可能涉及学术、技术、游戏、生活、娱乐、文化等任何领域，请尽量全面地提取。
对于每个关键概念，必须提取出其详细释义、包含的要点（Key Points），以及涉及的任何代码块或公式（如无则留空）。
你还需要根据当前 Obsidian 知识库目录结构与整理规则，为每个概念建议一个相对 vault 根目录的 Markdown 写入路径 `target_path`。

当前知识库结构：
{vault_structure}

知识库整理规则：
\"\"\"
{organization_rules}
\"\"\"

输入文本：
\"\"\"
{raw_input_text}
\"\"\"

请严格以 JSON 格式输出，不要包含任何 Markdown 格式包裹（直接返回纯 JSON 数组，如 `[...]`），格式结构如下：
[
  {{
    "concept": "概念/名词名称（必须简短、精准，例如 'Transformer' 或 '后撤步'）",
    "definition": "对该概念在文中的详细中文定义与解释",
    "key_points": ["核心要点1", "核心要点2", "核心要点3"],
    "code_or_formula": "提取的相关代码块或公式（若无则填空字符串）",
    "target_path": "建议写入的 Markdown 相对路径，例如 Concepts/Transformer.md 或 Sources/视频标题.md"
  }}
]

如果文本内容确实没有可提取的有意义主题（如纯噪音），则返回空数组 []。
"""
        raw_response = ""
        try:
            raw_response = self._call_api(prompt, system_prompt)
            
            concepts = parse_json_response(raw_response)
            if not isinstance(concepts, list):
                raise ValueError("概念抽取结果必须是 JSON 数组")

            if not concepts:
                fallback_concepts = self._extract_fallback_concepts(raw_input_text)
                if fallback_concepts:
                    logger.warning("LLM 返回空概念，已使用本地启发式概念兜底。")
                    db_manager.add_log("WARNING", "LLM", "Extract_Fallback", f"本地兜底提取 {len(fallback_concepts)} 个概念")
                    return fallback_concepts
            
            duration = time.time() - start_time
            logger.info(f"概念提取完成，共识别出 {len(concepts)} 个核心概念，用时 {duration:.2f}s")
            db_manager.add_log("INFO", "LLM", "Extract_Success", f"抽取完成，获取到 {len(concepts)} 个概念", duration=duration)
            
            return concepts
            
        except ProviderUnavailableError as e:
            logger.warning("LLM Provider 不可用，概念抽取降级为空结果: %s", e)
            fallback_concepts = self._extract_fallback_concepts(raw_input_text)
            db_manager.add_log("WARNING", "LLM", "Extract_Downgrade", f"Provider 不可用，本地兜底提取 {len(fallback_concepts)} 个概念")
            return fallback_concepts
        except Exception as e:
            logger.error(f"解析概念 JSON 失败，模型原始输出为:\n{raw_response}")
            db_manager.add_log("ERROR", "LLM", "Extract_Failure", f"JSON解析错误: {e}")
            raise

    def _extract_fallback_concepts(self, raw_input_text: str, max_items: int = 5) -> List[Dict[str, Any]]:
        """在云端/本地 LLM 不可用或返回空数组时，做保守主题兜底。"""
        text = raw_input_text or ""
        source_name = self._metadata_value(text, "source_name")
        candidates: Dict[str, int] = {}

        title_candidate = self._concept_from_title(source_name)
        if title_candidate:
            candidates[title_candidate] = candidates.get(title_candidate, 0) + 20

        body = re.sub(r"【来源元数据】.*?(?=【来源时间戳片段】|【视频声音转写内容】|$)", "", text, flags=re.S)
        body = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", " ", body)
        body = re.sub(r"source_[a-z_]+:\s*.*", " ", body)

        for match in re.findall(r"\b[A-Za-z][A-Za-z0-9+#.\-]{2,}\b", body):
            cleaned = match.strip(".-")
            if cleaned.lower() in {"http", "https", "mp4", "wav", "m4a", "ocr", "fps"}:
                continue
            candidates[cleaned] = candidates.get(cleaned, 0) + 8

        for match in re.findall(r"[\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9·\-]{1,15}", body):
            cleaned = self._clean_chinese_candidate(match)
            if not cleaned:
                continue
            candidates[cleaned] = candidates.get(cleaned, 0) + min(len(cleaned), 8)

        ranked = sorted(candidates.items(), key=lambda item: (-item[1], len(item[0])))
        concepts = []
        for name, _score in ranked:
            if any(name in existing["concept"] or existing["concept"] in name for existing in concepts):
                continue
            evidence = self._evidence_sentences(body, name)
            concepts.append({
                "concept": name,
                "definition": f"从来源内容中自动识别出的主题：{name}。该条为本地兜底结果，建议人工复核和补充。",
                "key_points": evidence or ["由本地启发式规则从来源标题或转写片段中识别。"],
                "code_or_formula": "",
                "target_path": f"Concepts/{fs_router.sanitize_filename(name)}",
            })
            if len(concepts) >= max_items:
                break
        return concepts

    def _metadata_value(self, text: str, key: str) -> str:
        match = re.search(rf"^{re.escape(key)}:\s*(.+)$", text or "", re.MULTILINE)
        return match.group(1).strip() if match else ""

    def _concept_from_title(self, source_name: str) -> str:
        title = os.path.splitext(os.path.basename(source_name or ""))[0]
        title = re.sub(r"^[0-9a-fA-F]{16,}_", "", title)
        title = re.sub(r"^\[.*?\]", "", title)
        title = re.sub(r"(生成|一个|一段|简短|科普|视频|音频|文件|讲解|介绍|的)", "", title)
        title = re.sub(r"[_\-\s]+", "", title).strip(" _-，。,.")
        return title[:24] if len(title) >= 2 else ""

    def _clean_chinese_candidate(self, value: str) -> str:
        cleaned = re.sub(r"(这个|我们|可以|通过|进行|来源|时间戳|视频|声音|内容|片段|画面|分析|文字|描述|暂无|文件|成功|提取)", "", value)
        cleaned = cleaned.strip(" ，。,.、:：；;（）()[]【】")
        if len(cleaned) < 2 or len(cleaned) > 12:
            return ""
        if re.fullmatch(r"[一二三四五六七八九十]+", cleaned):
            return ""
        return cleaned

    def _evidence_sentences(self, text: str, concept_name: str) -> List[str]:
        sentences = re.split(r"[。！？!?；;\n]", text or "")
        evidence = []
        for sentence in sentences:
            cleaned = sentence.strip(" -:：\t")
            if concept_name in cleaned and 4 <= len(cleaned) <= 120:
                evidence.append(cleaned)
            if len(evidence) >= 3:
                break
        return evidence

    def merge_and_write_wiki(self, concept_data: Dict[str, Any], source_filename: str) -> str:
        """
        阶段二：将新知识合并入 Obsidian 本地旧笔记，并执行双向链接织网
        
        Args:
            concept_data: 单个概念的数据字典 (由 extract_concepts 产生)
            source_filename: 来源文件名，用来标记来源元数据
        """
        concept_name = concept_data["concept"]
        definition = concept_data["definition"]
        key_points = "\n".join([f"- {kp}" for kp in concept_data.get("key_points", [])])
        code_or_formula = concept_data.get("code_or_formula", "")
        
        logger.info(f"开始执行 [阶段二: 智能合并笔记] -> 概念: {concept_name}")
        
        # 1. 定位本地文件系统中的路径
        target_path = concept_data.get("target_path", "")
        file_path = fs_router.locate_concept_file(concept_name) or fs_router.resolve_note_path(target_path, concept_name)
        old_content = ""
        
        if os.path.exists(file_path):
            old_content = wiki_editor.read_wiki(file_path)
            logger.info(f"检测到概念 '{concept_name}' 已有本地旧笔记，大小: {len(old_content)} 字符。")
        else:
            logger.info(f"概念 '{concept_name}' 在知识库中是新笔记。")

        # 2. 构造合并提示词
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_knowledge_summary = f"""【新提取知识摘要】
概念定义: {definition}
核心要点:
{key_points}
代码或公式: 
{code_or_formula}
"""

        system_prompt = "你是一个个人知识库 (Obsidian 第二大脑) 整理专家。你非常擅长将新知识原子化地合入旧笔记，并编织双向链接。"
        
        prompt = f"""你的任务是将新提取的关于“{concept_name}”的知识，无缝融合合并到它已有的旧笔记中。

【新提取的知识】：
{new_knowledge_summary}

【已有的旧笔记内容】：
{old_content if old_content else "（无旧笔记，请从头开始创建）"}

【合并与编织守则】：
1. 【保留用户痕迹】：如果旧笔记中包含用户自己写的总结、大纲或个人感想，必须全部保留，严禁擅自删改。
2. 【无缝插入与合并】：将新知识（新定义、新要点、公式、代码）与旧笔记的对应章节合并。如果是全新笔记，请建立结构化的 Markdown 笔记大纲。
3. 【双链织网】：在笔记的各段落中，如果提到了其他技术词汇或已被提取的核心概念，**必须**使用 Obsidian 双向链接格式 `[[概念名称]]` 进行包裹，以便构建网状结构图（例如：提到注意力机制，写成 `[[注意力机制]]`）。
4. 【YAML Frontmatter】：笔记头部必须保留或创建标准的 YAML 头部，格式如下：
---
concept: {concept_name}
updated_at: "{timestamp}"
source: "{source_filename}"
target_path: "{fs_router.get_relative_path(file_path)}"
tags: [knowledge-node, auto-updated]
---

🔴【核心指令】：你的回答中，必须且只能包含合并后的纯净 Markdown 格式内容，绝对不要包含任何前言、总结、致谢、解释或 ```markdown 包裹。直接从 YAML 头部（即第一行 '---'）开始输出。
"""
        try:
            start_time = time.time()
            merged_content = self._call_api(prompt, system_prompt)
            
            merged_content = strip_code_fence(merged_content, "markdown")

            # 3. 原子化安全覆写本地磁盘
            success = wiki_editor.write_wiki_atomic(file_path, merged_content)
            
            duration = time.time() - start_time
            if success:
                db_manager.add_log("INFO", "LLM", "Wiki_Weave_Success", 
                                   f"合并更新 Wiki 成功: {concept_name} -> {os.path.basename(file_path)}", 
                                   duration=duration)
                # 重新扫描路由缓存
                fs_router.scan_vault()
                return merged_content
            else:
                raise IOError(f"原子覆写本地文件失败: {file_path}")
                
        except ProviderUnavailableError as e:
            logger.warning("LLM Provider 不可用，使用保守模板写入概念笔记: %s", e)
            fallback_content = self._build_fallback_concept_note(
                concept_name=concept_name,
                definition=definition,
                key_points=concept_data.get("key_points", []),
                code_or_formula=code_or_formula,
                source_filename=source_filename,
                file_path=file_path,
                timestamp=timestamp,
            )
            success = wiki_editor.write_wiki_atomic(file_path, fallback_content)
            if not success:
                raise IOError(f"原子覆写本地文件失败: {file_path}") from e
            fs_router.scan_vault()
            db_manager.add_log("WARNING", "LLM", "Wiki_Weave_Downgrade", f"Provider 不可用，已写入保守模板: {concept_name}")
            return fallback_content
        except Exception as e:
            logger.error(f"合并笔记失败: {concept_name}, {e}")
            db_manager.add_log("ERROR", "LLM", "Wiki_Weave_Failure", f"合并失败: {concept_name}, {e}")
            raise

    def _build_fallback_concept_note(
        self,
        *,
        concept_name: str,
        definition: str,
        key_points: List[str],
        code_or_formula: str,
        source_filename: str,
        file_path: str,
        timestamp: str,
    ) -> str:
        """Provider 不可用时生成可追溯、可编辑的保守概念页。"""
        points = "\n".join(f"- {item}" for item in key_points if item) or "- 待补充"
        code_block = ""
        if code_or_formula:
            code_block = f"\n## 代码或公式\n\n{code_or_formula.strip()}\n"
        return f"""---
concept: {concept_name}
updated_at: "{timestamp}"
source: "{source_filename}"
target_path: "{fs_router.get_relative_path(file_path)}"
tags: [knowledge-node, fallback-generated]
---

# {concept_name}

## 定义

{definition or "待补充"}

## 要点

{points}
{code_block}
## 来源

- [[{source_filename}]]
"""

# 实例化单例
llm_core = LLMCore()
