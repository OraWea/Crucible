# Crucible

Crucible 是一个视频优先的 AI 知识库。它的目标不是做一次性的摘要工具，而是把视频、音频、文档和网页来源沉淀为可检索、可追溯、可编辑的本地知识资产。

核心工作流：

- 导入视频、音频、PDF、文本、Markdown 或在线视频 URL。
- 自动提取音频、转写文本、分段并保留时间戳。
- 对视频关键帧执行视觉分析。
- 使用 LLM 抽取概念、生成或合并 Markdown 笔记。
- 将 AI 生成内容绑定到来源页和时间戳。
- 生成 Obsidian 兼容的双链 Markdown、frontmatter、反链和来源索引。
- 支持本地检索、知识图谱、事实一致性核查和审计日志。

## 当前形态

项目目前同时包含三部分：

- `gui.py`：原 PyQt6 桌面端入口，保留原始桌面工作流。
- `backend/`：FastAPI 后端，把 `gui.py` 原来的核心业务能力暴露为 Web API。
- `frontend/`：React + Vite + TypeScript 前端，一个手绘风格的知识库 workspace。

Web 版推荐作为后续主入口；PyQt6 版仍可作为本地桌面版本运行。

## 技术栈

- 后端：Python、FastAPI、SQLite、Whisper、Transformers、DashScope/OpenAI-compatible API。
- 前端：React、TypeScript、Vite、lucide-react。
- 桌面端：PyQt6。
- 知识库格式：Obsidian 兼容 Markdown。
- 数据存储：本地 `data/` 目录和 SQLite。

## 目录结构

```text
Crucible/
  backend/                 FastAPI Web API
  frontend/                React/Vite Web 前端
  models/                  LLM、VLM、Whisper、事实核查封装
  utils/                   音视频处理、数据库、Vault、Markdown、索引、图谱
  data/                    本地运行数据，包含 vault、数据库、备份
  temp/                    临时文件和上传缓存
  gui.py                   PyQt6 桌面端入口
  config.py                路径、模型、Provider、安全配置
  requirements.txt         Python 依赖
  test_core_features.py    离线核心能力测试
```

## 快速启动 Web 版

### 1. 安装 Python 依赖

建议使用虚拟环境。

```bash
pip install -r requirements.txt
```

如果要处理音视频，请确保系统已安装 FFmpeg，并已加入环境变量。

### 2. 安装前端依赖

```bash
cd frontend
npm install
```

### 3. 启动后端

在项目根目录运行：

```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

后端 API 文档：

```text
http://127.0.0.1:8000/docs
```

### 4. 启动前端

另开一个终端：

```bash
cd frontend
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:5173
```

前端开发服务器已配置代理，`/api` 会转发到 `http://127.0.0.1:8000`。

## 默认账号

首次启动后端时，如果用户表为空，会自动创建两个演示账号：

```text
管理员：admin / admin123
普通用户：user / user123
```

生产或正式使用前，请修改默认密码或自行实现更严格的认证策略。

## 运行 PyQt6 桌面版

```bash
python gui.py
```

桌面版保留了原有功能，包括登录、文件选择、AI 提炼、Vault 编辑、检索、图谱和日志审计。

## Web 版功能

当前 Web 版已接入后端 API，支持：

- 登录和登出。
- Vault 树扫描。
- 新建文件夹。
- 新建 Markdown 笔记。
- 打开、编辑、保存笔记。
- 重命名当前笔记。
- 打开整理规则文件。
- 上传文件并启动 AI 处理任务。
- 添加 URL 并启动 AI 处理任务。
- 对当前来源重新提炼。
- 查看来源列表和分段时间戳。
- 本地检索来源片段。
- 查看知识图谱边。
- 保存模型 Provider、API Base、模型名和 API Key。
- 管理员查看和导出审计日志。

浏览器不能像 PyQt 文件选择器那样直接读取任意本机路径，因此 Web 版使用文件上传作为主要导入方式。后端仍支持处理已有本机路径和 URL。

## 模型和 Provider 配置

配置集中在 `config.py`，运行时设置可保存到：

```text
data/local_settings.json
```

支持的 Provider 预设包括：

- OpenAI
- DashScope / Qwen
- DeepSeek
- Moonshot / Kimi
- Zhipu / GLM
- OpenRouter
- Ollama
- LM Studio
- Custom OpenAI-compatible

API Key 不应硬编码在源码中。推荐使用：

- `.env`
- `data/local_settings.json`
- Web/GUI 设置界面输入

## 构建前端

```bash
cd frontend
npm run build
```

构建产物会输出到：

```text
frontend/dist/
```

## 测试

离线核心能力测试：

```bash
python test_core_features.py
```

本地流水线测试入口：

```bash
python test_crucible_local.py
```

注意：`test_crucible_local.py` 可能触发模型调用，运行前请确认本地模型或 API 配置可用。

## 打包建议

### Web 版

推荐先构建前端：

```bash
cd frontend
npm run build
```

然后用后端部署工具运行：

```bash
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

如需完整离线分发，可进一步使用 PyInstaller 打包后端入口，并把 `frontend/dist`、`models/`、`utils/`、`config.py` 等必要文件一起复制到发布目录。

### PyQt6 桌面版

可参考 `package_info.md` 使用 PyInstaller：

```bash
pyinstaller --noconsole --name="Crucible" --add-data="Crucible/config.py;." --add-data="Crucible/utils;utils" --add-data="Crucible/models;models" Crucible/gui.py
```

根据当前实际路径，命令可能需要调整。

## 数据和隐私

Crucible 默认本地优先。以下内容都应视为敏感数据：

- 用户视频和音频。
- 转写文本。
- AI 生成笔记。
- 本地 Vault。
- SQLite 数据库。
- API Key。

不要提交以下内容：

- `data/`
- `temp/`
- `app.log`
- 模型权重
- 真实 `.env`
- `data/local_settings.json`
- 用户 Vault

## 常见问题

### 后端启动后前端请求失败

确认后端运行在：

```text
http://127.0.0.1:8000
```

确认前端开发服务器运行在：

```text
http://127.0.0.1:5173
```

### 音视频处理失败

通常是 FFmpeg 不可用。安装 FFmpeg 后，把 `ffmpeg` 加入系统环境变量。

### 云端模型不可用

检查：

- Provider 是否选对。
- API Base 是否正确。
- API Key 是否有效。
- 模型名是否存在。

也可以切换到 Ollama 或 LM Studio 等本地 OpenAI-compatible 服务。

### VLM 或本地模型加载慢

视觉模型和本地大模型会占用大量显存和内存。开发调试时可以优先使用 API 模式，或只启用 Whisper/文本处理能力。

## 开发原则

- 新功能优先复用 `utils/` 和 `models/` 中已有能力。
- GUI 不应直接写复杂模型逻辑，Web 后端也应复用业务层。
- AI 生成内容必须尽量保留来源时间戳。
- Markdown 输出应兼容 Obsidian 双链、标签和 frontmatter。
- 覆写笔记前遵守 `Config.ENABLE_BACKUP`。

