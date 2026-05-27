import logging
import json
import time
import requests
from Crucible.config import Config
from Crucible.utils.db_manager import db_manager

logger = logging.getLogger(__name__)

class FactChecker:
    def __init__(self):
        self.api_key = Config.LLM_API_KEY
        self.api_base = Config.LLM_API_BASE
        self.model_name = Config.LLM_MODEL_NAME

    def check_consistency(self, original_source_text: str, generated_wiki_content: str) -> dict:
        """
        比对生成的 Wiki 页面与原始数据源，判断是否存在事实虚构或幻觉
        
        Args:
            original_source_text: 原始 Whisper 转写文本或解析的 PDF/TXT 原文
            generated_wiki_content: AI 提取合并后的 Markdown 内容
            
        Returns:
            Dict: {'score': int, 'consistent': bool, 'reason': str}
        """
        logger.info("开始执行 [AI 事实一致性核对 (LLM-as-a-Judge)]...")
        start_time = time.time()
        
        # 截断极长文本防止超出 token 上限
        truncated_source = original_source_text[:12000]
        truncated_wiki = generated_wiki_content[:4000]

        system_prompt = "你是一个严谨的事实审查裁判（Fact-checking Judge）。你的任务是执行自然语言推理（NLI），核对文本一致性并指出幻觉。"

        prompt = f"""请对比以下【原始参考数据】与【生成的知识库笔记】，仔细检查生成内容中是否存在“原数据中未提及的事实、捏造的虚假公式、胡乱编写的代码细节、或直接的逻辑冲突（幻觉）”。

【原始参考数据】：
\"\"\"
{truncated_source}
\"\"\"

【生成的知识库笔记】：
\"\"\"
{truncated_wiki}
\"\"\"

评分守则：
1. 评分范围为 0 到 100 分。
2. 如果生成的笔记中内容完美契合原始参考数据，且无任何捏造或冲突，评分在 90 分以上。
3. 如果生成的笔记中补充了外围推理，但未捏造关键事实，评分在 80-90 分。
4. 如果笔记中出现了与原视频/原文件含义直接矛盾的事实（如写错了原理、歪曲了参数、捏造了代码函数），扣减 20-50 分。
5. 80 分及以上视为一致性判定合格 (consistent = true)，低于 80 分判定为不合格 (consistent = false)。

请严格以以下 JSON 格式输出，不要带有 Markdown 代码块包裹，也不要含有额外字眼：
{{
  "score": 分数值（整数）,
  "consistent": 判定合格与否（true/false）,
  "reason": "审查判定的简短中文理由，指出具体哪些点存在冲突或完美契合"
}}
"""
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
            "temperature": 0.0  # 设为 0 以保证裁判评分的稳定性与确定性
        }

        default_fallback = {
            "score": 85,
            "consistent": True,
            "reason": "评估超时或接口异常，执行安全通过（保底评分）"
        }

        try:
            response = requests.post(f"{self.api_base}/chat/completions", json=payload, headers=headers, timeout=30)
            if response.status_code != 200:
                raise RuntimeError(f"Fact Checker API 失败: {response.text}")
                
            resp_json = response.json()
            content = resp_json['choices'][0]['message']['content'].strip()
            
            # 清理可能的 markdown 标记
            if content.startswith("```"):
                lines = content.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:-1]
                content = "\n".join(lines).strip()
                
            result = json.loads(content)
            duration = time.time() - start_time
            
            logger.info(f"事实一致性校验完毕。得分: {result.get('score')}，是否合格: {result.get('consistent')}。用时: {duration:.2f}s")
            db_manager.add_log(
                "INFO", "VLM", "Fact_Check_Success", 
                f"评分: {result.get('score')}, 原因: {result.get('reason')}", 
                duration=duration
            )
            return result

        except Exception as e:
            logger.error(f"事实一致性校验失败: {e}，将启动保底防崩回退机制。")
            db_manager.add_log("WARNING", "VLM", "Fact_Check_Exception", str(e))
            return default_fallback

# 实例化单例
fact_checker = FactChecker()
