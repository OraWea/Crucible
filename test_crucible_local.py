import os
import sys
import logging

# 将项目目录添加至 Python 路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Crucible.config import Config
from Crucible.utils.db_manager import db_manager
from Crucible.utils.fs_router import fs_router
from Crucible.utils.wiki_editor import wiki_editor
from Crucible.models.llm_core import llm_core
from Crucible.models.fact_checker import fact_checker

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TestCrucible")

def run_test():
    logger.info("=== Crucible Core Pipeline CLI Test ===")
    
    # 1. 确认路径与初始化
    Config.init_paths()
    logger.info(f"Obsidian Vault 路径: {Config.OBSIDIAN_VAULT_PATH}")
    logger.info(f"SQLite 数据库路径: {Config.DATABASE_PATH}")

    # 2. 测试输入文本 (模拟 ASR 与 VLM 提取的非结构化数据)
    sample_text = """
    在 2017 年，Google 团队发表了著名的论文 Attention Is All You Need，提出了 Transformer 神经网络架构。
    与传统的循环神经网络 (RNN) 相比，Transformer 抛弃了递归结构，完全基于自注意力机制 (Self-Attention) 
    来计算输入与输出的表征。它极大地提升了并行训练速度，并成为如今大语言模型 (LLM) 如 GPT-4、Qwen 等的基石。
    """
    
    logger.info("模拟非结构化输入数据载入完成。")

    # 3. 运行阶段一：概念提取
    logger.info("正在调用 LLM 进行核心概念提炼...")
    try:
        concepts = llm_core.extract_concepts(sample_text)
        logger.info(f"成功提取概念数目: {len(concepts)}")
        for item in concepts:
            logger.info(f" - 提取出的概念: {item['concept']}")
    except Exception as e:
        logger.error(f"提取阶段发生错误: {e}")
        return

    # 4. 运行阶段二：智能合并笔记与双链织网
    logger.info("正在将概念合并写入本地 Obsidian Markdown 笔记...")
    for item in concepts:
        concept_name = item["concept"]
        try:
            # 写入或合并
            merged_md = llm_core.merge_and_write_wiki(item, "test_source.txt")
            
            # 核查路径
            written_path = fs_router.locate_concept_file(concept_name)
            logger.info(f"概念 '{concept_name}' 成功写入路径: {written_path}")
            
            # 5. 事实核对
            logger.info(f"正在启动 LLM-as-a-Judge 校验 '{concept_name}' 事实一致性...")
            judge_res = fact_checker.check_consistency(sample_text, merged_md)
            logger.info(f"一致性检查结果: 分数={judge_res['score']}, 合格={judge_res['consistent']}")
            logger.info(f"判定原因: {judge_res['reason']}")
            
        except Exception as e:
            logger.error(f"概念 '{concept_name}' 合并与核对失败: {e}")

    # 6. 查看操作日志
    logger.info("正在查询 SQLite 中记录的运行日志...")
    logs = db_manager.get_logs(limit=5)
    for log_row in logs:
        logger.info(f"[{log_row['timestamp']}] [{log_row['module']}] {log_row['action']}: {log_row['detail']}")

    logger.info("=== Crucible Core Pipeline 测试顺利结束 ===")

if __name__ == "__main__":
    run_test()
