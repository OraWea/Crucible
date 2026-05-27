import os
import logging
import json
import time
import requests
import datetime
from typing import Dict, Any, List, Tuple
from Crucible.config import Config
from Crucible.utils.db_manager import db_manager
from Crucible.utils.fs_router import fs_router
from Crucible.utils.wiki_editor import wiki_editor

logger = logging.getLogger(__name__)

class LLMCore:
    def __init__(self):
        self.api_key = Config.LLM_API_KEY
        self.api_base = Config.LLM_API_BASE
        self.model_name = Config.LLM_MODEL_NAME

    def _call_api(self, prompt: str, system_prompt: str = "你是一个智能的个人第二大脑知识库助手。") -> str:
        """底层封装的 API 调用接口"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        try:
            response = requests.post(f"{self.api_base}/chat/completions", json=payload, headers=headers, timeout=60)
            if response.status_code != 200:
                raise RuntimeError(f"LLM API 响应错误 ({response.status_code}): {response.text}")
            
            resp_json = response.json()
            return resp_json['choices'][0]['message']['content'].strip()
        except Exception as e:
            logger.error(f"调用 LLM 接口失败: {e}", exc_info=True)
            raise e

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
        
        prompt = f"""请分析以下非结构化文本，提取出其中讨论的所有核心主题、概念、人物、专有名词或关键知识点。
内容可能涉及学术、技术、游戏、生活、娱乐、文化等任何领域，请尽量全面地提取。
对于每个关键概念，必须提取出其详细释义、包含的要点（Key Points），以及涉及的任何代码块或公式（如无则留空）。

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
    "code_or_formula": "提取的相关代码块或公式（若无则填空字符串）"
  }}
]

如果文本内容确实没有可提取的有意义主题（如纯噪音），则返回空数组 []。
"""
        raw_response = ""
        try:
            raw_response = self._call_api(prompt, system_prompt)
            
            # 清理可能被模型误添加的 ```json 代码块包裹
            cleaned_response = raw_response.strip()
            if cleaned_response.startswith("```"):
                lines = cleaned_response.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:-1]
                cleaned_response = "\n".join(lines).strip()
            
            concepts = json.loads(cleaned_response)
            
            duration = time.time() - start_time
            logger.info(f"概念提取完成，共识别出 {len(concepts)} 个核心概念，用时 {duration:.2f}s")
            db_manager.add_log("INFO", "LLM", "Extract_Success", f"抽取完成，获取到 {len(concepts)} 个概念", duration=duration)
            
            return concepts
            
        except Exception as e:
            logger.error(f"解析概念 JSON 失败，模型原始输出为:\n{raw_response}")
            db_manager.add_log("ERROR", "LLM", "Extract_Failure", f"JSON解析错误: {e}")
            raise e

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
        file_path = fs_router.get_concept_write_path(concept_name)
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
tags: [knowledge-node, auto-updated]
---

🔴【核心指令】：你的回答中，必须且只能包含合并后的纯净 Markdown 格式内容，绝对不要包含任何前言、总结、致谢、解释或 ```markdown 包裹。直接从 YAML 头部（即第一行 '---'）开始输出。
"""
        try:
            start_time = time.time()
            merged_content = self._call_api(prompt, system_prompt)
            
            # 清理可能的 markdown 代码块标记
            merged_content = merged_content.strip()
            if merged_content.startswith("```"):
                lines = merged_content.split("\n")
                if lines[0].startswith("```markdown") or lines[0].startswith("```"):
                    lines = lines[1:-1]
                merged_content = "\n".join(lines).strip()

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
                
        except Exception as e:
            logger.error(f"合并笔记失败: {concept_name}, {e}")
            db_manager.add_log("ERROR", "LLM", "Wiki_Weave_Failure", f"合并失败: {concept_name}, {e}")
            raise e

# 实例化单例
llm_core = LLMCore()
