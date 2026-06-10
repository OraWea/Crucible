# Repository Guidelines

## 项目定位
Crucible 是一个“视频优先”的 AI 知识库，目标类似 Obsidian，但重点支持视频、音频、文档的自动解析、转写、分段、摘要、概念抽取、事实核查、双链 Markdown 笔记和本地知识库沉淀。所有功能设计必须围绕“用户能把视频变成可检索、可追溯、可编辑的知识资产”展开。

## 技术栈原则
- 尽量全栈使用 Python。GUI 优先沿用 `PyQt6`，后端逻辑、任务编排、模型调用、索引、数据库和文件处理均优先用 Python 实现。
- 不要轻易引入 Node、Electron、Go、Rust 等额外运行时；除非有明确收益，并先说明替代方案。
- 优先使用成熟 Python 库：`openai-whisper`、`transformers`、`torch`、`opencv-python`、`pydub`、`pypdf`、`yt-dlp`、`sqlite3` 等。

## 项目结构
- `gui.py`：当前桌面 GUI 入口。新增 UI 行为应保持界面响应性，耗时任务必须异步或放入工作线程。
- `config.py`：集中管理路径、模型、API、设备和安全配置。禁止把密钥、模型参数散落到业务代码中。
- `models/`：LLM、VLM、Whisper、事实核查等模型能力封装。
- `utils/`：音视频处理、文档解析、数据库、文件路由、Markdown 写入等基础能力。
- `data/`：本地 vault、数据库、备份等运行数据。不要提交用户数据。
- `temp/`：临时文件目录。任务结束后应尽量清理可恢复的中间文件。

## AI 与模型策略
- 用户必须能自由选择模型 Provider、模型名、API Base 和 API Key。设计配置时兼容 OpenAI-compatible API、DashScope、Ollama、LM Studio 等。
- API Key 只能来自 `.env`、本地配置文件或用户界面输入，禁止硬编码真实密钥。
- 必须提供本地模型兜底路径：ASR 可用 Whisper，本地 LLM/VLM 可通过 Ollama、LM Studio 或 `transformers` 加载。云端不可用时，应降级为本地摘要、转写或离线索引能力，而不是直接崩溃。
- 模型调用层要隔离 Provider 差异，对上暴露稳定接口，例如 `extract_concepts()`、`summarize_segment()`、`check_consistency()`。

## 视频知识库核心规则
- 视频导入后应保留来源、文件 hash、时长、分辨率、音轨、字幕、关键帧、转写文本和时间戳。
- 所有 AI 生成内容必须尽量可追溯到原始片段时间戳，例如 `[[source.mp4#00:12:33]]` 或等价 Markdown 链接。
- 笔记输出优先 Markdown，兼容 Obsidian 双链、标签、frontmatter 和附件引用。
- 不要只做“摘要工具”。功能应服务于长期知识管理：概念页、主题页、来源页、片段页、反向链接、事实核查记录都要能逐步演进。

## 编码规范
- Python 使用 4 空格缩进，函数和变量用 `snake_case`，类名用 `PascalCase`，常量用 `UPPER_SNAKE_CASE`。
- 保持模块职责单一：GUI 不直接写复杂模型逻辑，模型层不直接操作 UI。
- 对外部文件、视频、模型响应和网络结果做显式异常处理，并写入日志。
- 新功能优先编辑现有模块；只有职责明确时才新增文件。

## 测试与验证
- 当前可用测试入口是 `python test_crucible_local.py`。新增核心能力时，应补充可离线运行的最小测试。
- 测试不要依赖真实 API Key。需要模型响应时，优先使用 mock、fixture 或本地小样本。
- 音视频处理、Markdown 写入、路径路由、数据库写入和模型 Provider 适配是高风险区域，修改后必须验证。

## 安全与隐私
- 默认本地优先。用户视频、转写文本、笔记和 API Key 均视为敏感数据。
- 不得自动上传用户素材到云端模型；调用云端前必须由配置或 UI 明确选择。
- 覆写笔记前遵守 `Config.ENABLE_BACKUP`，保留可恢复备份。
- 日志不得记录完整 API Key，不得无节制记录大段用户原文。

## 提交与协作
- Git 提交沿用简洁 Conventional Commits 风格，例如 `feat: add provider settings`、`fix: handle empty transcript`。

- PR 或变更说明应包含：改动目的、影响模块、验证命令、是否涉及模型/API/用户数据。

- 不要提交 `data/`、`temp/`、`app.log`、模型权重、用户 vault 或真实配置文件。

- ```
  - 细粒度半成品不要单独 commit：单个 AB / 单个常量 / 单个 layout 这种零碎改动不单独成 commit
  - 代码可 auto commit：实现类代码可以自动提交
  - Spec / plan 文档不入库：brainstorming / writing-plans 产出的 .md 文件不要 commit
  ```

  通用规范：

  ```
  - 不更新 git config
  - 不擅自做破坏性操作（push --force、reset --hard、checkout . 等）
  - 不跳过 hooks（不用 --no-verify / --no-gpg-sign）
  - 优先 add 具体文件而不是 git add -A / git add .，避免误带 .env 等敏感文件
  ```
