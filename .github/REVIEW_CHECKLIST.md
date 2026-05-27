## 📝 Summary
- **Core Changes:** (例如: 重构了 `models/llm_core.py` 中的反思 Prompt / 修复了 PyQt6 线程死锁)
- **Code Quality Rating:** 🟢 Approved / 🟡 Changes Requested / 🔴 Rejected

---

## 🎉 Well Done
> [!TIP]
> **本次提交中非常优雅、值得学习的设计亮点：**
> - **亮点 1：** (例如：`utils/wiki_editor.py` 中的文件覆写安全备份机制写得非常严谨，考虑到了大模型幻觉删库的极端情况，给好评！)
> - **亮点 2：** (例如：正确使用了 PyQt6 的信号量机制，线程间的数据流转非常清晰，代码格式极其纯净，非常符合 minimalist 风格。)

---

## 🔍 Core Checklist

### 1. 架构与解耦 (Architecture & Decoupling)
- [ ] **UI 与逻辑完全分离：** 新增的 AI 算法/文件操作逻辑是否 100% 独立于 PyQt6 界面代码？（严禁在 UI 线程写耗时循环）
- [ ] **异步线程安全：** 如果涉及后台长任务，是否正确使用了 `QThread` 和 `pyqtSignal`？有无多线程竞态风险？

### 2. 唯一真实数据源 (Single Source of Truth)
- [ ] **Markdown 纯净度：** 写入/修改 `.md` 文件时，是否破坏了原有的 Markdown AST 结构或 YAML Frontmatter？
- [ ] **I/O 原子性与备份：** 执行文件覆写前，是否调用了快照备份机制？

### 3. AI 模型与异常控制 (AI & Exception Handling)
- [ ] **资源释放：** 本地加载的模型在推理结束后，是否有显存/内存释放逻辑，是否会引发 OOM？
- [ ] **降级预案：** 当本地 GPU 显存不足或 API 超时时，代码是否有 `try-except` 捕获并平滑降级？

---

## 💬 Code Review Comments
> [!NOTE]
> **以下为需要讨论、微调或重构的具体地方：**

- **File:** `utils/fs_router.py` (Line 42)
  - **问题：** 这里直接用了同步的 `os.walk` 遍历整个知识库，如果用户的 Obsidian 库有上万篇笔记，主界面会直接卡死。
  - **建议修改方案：** 建议将此处的检索逻辑改为生成器（Generator）或者扔进 `QThread` 异步执行。

---

## 🚀 Verification & Testing
- [ ] **本地 MVP 运行测试：** 评审人在本地运行 `python gui.py`，测试该变更功能，无卡顿，符合预期。
- [ ] **边缘测试：** 针对极端输入（如拖入损坏的文件），系统能够正常报错拦截，未发生 Crash。

**Approval Sign-off:**
/approve  赞赏作者的优秀设计，建议微调上述具体意见后，直接 Squash and Merge！