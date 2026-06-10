# Goal 1 Tasks

## TODO

- [x] Task 1: 建立现状基线
  - 范围：读取项目结构、关键模块、测试入口、现有 README/AGENTS 约束；运行可用测试，记录当前失败或风险。
  - 可验证结果：形成模块地图、当前测试结果、关键缺口清单；不修改业务代码。
  - 完成记录：
    - 改动：未修改业务代码；读取了 `README.md`、`AGENTS.md`、`requirements.txt`、`config.py`、`backend/app.py`、`utils/processing_workflow.py`、`utils/video_processor.py`、`utils/wiki_editor.py`、`utils/source_index.py`、`utils/db_manager.py`、`test_core_features.py`、`test_crucible_local.py`、`frontend/package.json`、`frontend/src/main.tsx`、`frontend/src/main.test.ts`，建立当前基线。
    - 模块地图：`config.py` 管理路径、Provider、模型和本地配置；`backend/app.py` 提供 FastAPI Web API、认证、Vault CRUD、上传、异步处理 job、来源/片段/图谱接口；`gui.py` 是 PyQt6 桌面入口；`utils/processing_workflow.py` 串联来源加载、ASR、VLM、LLM 概念抽取、来源索引、来源页和事实核查；`utils/video_processor.py` 负责 ffprobe/OpenCV 视频元数据、抽帧和关键帧保存；`utils/source_index.py` 管理 sources/segments/concept_mentions、来源页、时间戳链接、检索和图谱边；`utils/wiki_editor.py` 负责 Markdown 原子写入、备份、frontmatter、双链解析和同步 HTML 预览；`utils/db_manager.py` 初始化 SQLite 表和索引；`models/` 封装 OpenAI-compatible、LLM、VLM、Whisper、事实核查；`frontend/` 是 React/Vite 工作区，支持 Vault、来源、检索、图谱、设置和 250ms 防抖 Markdown 预览请求。
    - 验证：`python test_core_features.py` 失败，原因是当前环境没有 `python` 命令；`py test_core_features.py` 失败，提示 `No installed Python found!`；`python test_crucible_local.py` 与 `py test_crucible_local.py` 同样因 Python 不可用失败；`npm run test` 和 `npm run build` 在沙箱内失败，原因是 esbuild 读取 `../../..` 和 `frontend/vite.config.ts` 时 `Access is denied`；按权限规则申请沙箱外运行 `npm run test` / `npm run build`，审批服务返回 503，未获得授权，未绕过执行。
    - 当前能力：已有视频来源元数据、SHA256 hash、ffprobe/OpenCV 元数据回退、关键帧保存、来源页、时间轴片段、Obsidian 双链、frontmatter、来源时间戳链接、SQLite 来源索引、Web 后台 job、前端来源/片段/预览视图等雏形。
    - 关键缺口：无法在当前会话验证 Python 测试；`test_crucible_local.py` 会触发真实 LLM/模型调用，不适合作为默认离线基线；Markdown 预览后端为同步全量渲染，前端只有 250ms 防抖，后续仍需缓存/增量/取消策略；视频结构化链路已有元数据但缺少专门离线测试覆盖 hash、时间戳片段和关键帧字段；数据目录已有真实 `data/crucible.db` 和 vault 文件，后续测试必须隔离临时路径；git 状态显示 `AGENTS.md` 已修改且不是本轮改动，不能覆盖；`goal-1/` 是计划文档，不提交。
    - 剩余风险：由于 Python 不可用，未能证明 Python 后端和核心离线测试当前通过；由于沙箱权限和审批 503，未能证明前端测试/构建当前通过；读取 `frontend/src/main.tsx` 时输出过长被截断，但已确认核心状态、预览和来源 UI 逻辑位置。
    - 下一步：Task 2 应聚焦 `utils/processing_workflow.py`、`utils/video_processor.py`、`utils/source_index.py` 和相关测试，补齐视频结构化转译最小元数据缺口；优先设计可离线、临时目录隔离、无需真实模型和大视频文件的测试。

- [x] Task 2: 梳理视频结构化转译链路并补齐最小元数据缺口
  - 范围：检查视频导入、音频提取、转写、分段、元数据保存相关代码，补齐低风险缺口。
  - 可验证结果：新增或更新离线测试覆盖视频来源元数据、hash、时间戳片段输出。
  - 完成记录：
    - 改动：更新 `utils/processing_workflow.py`，让结构化源输入包含 `source_type`、`source_ext`、`source_hash_sha256`、`duration_seconds`、`duration_label`、`is_url`、`file_size`、分辨率、宽高、FPS、音轨数、字幕数等字段；把 ASR 片段从原来的 `[start-end]s` 改为 `HH:MM:SS - HH:MM:SS: text`；新增 `【来源时间戳片段】` 区块，让 LLM 和后续笔记生成有明确、规范的可追溯片段上下文；新增 `_format_segment_line()` 复用格式化逻辑。更新 `test_core_features.py`，新增离线测试覆盖本地文件 SHA256、结构化元数据块、规范化时间戳片段和 URL hash 稳定性。
    - 验证：执行 `git diff --check -- utils/processing_workflow.py test_core_features.py` 通过，仅提示 Windows 换行警告；`Select-String` 确认不存在误引入的 `metadata_value` / `metadata_source_value` 未定义 helper，确认新增 `source_hash_sha256`、`duration_label`、`【来源时间戳片段】` 和两个测试函数。尝试运行 `python test_core_features.py` 失败，原因仍是当前环境没有 `python` 命令；尝试运行 `py test_core_features.py` 失败，提示 `No installed Python found!`。
    - 提交状态：按规则尝试只暂存 `utils/processing_workflow.py` 与 `test_core_features.py`，但 `git add` 因无法创建 `.git/index.lock` 返回 `Permission denied`；申请沙箱外 `git add` 时自动审批服务返回 503，未获授权，因此本轮无法完成 git commit。未绕过权限限制，未暂存 `AGENTS.md` 或 `goal-1/`。
    - 剩余风险：由于当前环境 Python 不可用，新增测试尚未实际执行；代码虽经 diff 和文本检查，但没有解释器级语法验证。结构化源文本新增字段会增加传给 LLM 的上下文长度，但属于与目标一致的可追溯元数据；后续可按性能任务评估裁剪或缓存策略。
    - 下一步：Task 3 应基于新结构化源输入，强化 Markdown 笔记生成的可追溯性，重点检查来源页、概念页 frontmatter 和双链时间戳引用是否完整一致；在可用 Python/Git 权限恢复后优先运行 `test_core_features.py` 并提交本轮代码。

- [x] Task 3: 强化 Markdown 笔记生成的可追溯性
  - 范围：检查 Markdown 写入、frontmatter、双链、来源引用格式，确保 AI 生成内容能定位原始片段。
  - 可验证结果：测试验证生成 Markdown 包含来源、时间戳、frontmatter 和可解析链接。
  - 完成记录：
    - 改动：更新 `utils/source_index.py`，将来源页内容生成拆出 `_build_source_note_content()`，便于离线测试；来源页 frontmatter 新增 `source_timestamps` 与 `concepts` 列表；时间轴每个片段正文新增 `- 时间戳链接: [[Sources/...#HH:MM:SS|HH:MM:SS]]`；元数据区新增时间戳片段数；新增 `_yaml_string_list()` 统一生成简单 YAML 字符串列表。更新 `test_core_features.py`，新增 `test_source_note_contains_traceable_timestamp_links()`，验证来源页 Markdown 包含 frontmatter 来源时间戳、概念列表、正文时间戳双链，并能被 `wiki_editor.extract_wiki_link_items()` 解析出目标与 anchor。
    - 验证：执行 `git diff --check -- utils/source_index.py test_core_features.py` 通过，仅提示 Windows 换行警告；`Select-String` 确认 `_build_source_note_content`、`source_timestamps`、`时间戳链接`、`_yaml_string_list` 与新增测试存在。确认 `ProcessingWorkflow.run()` 仍按顺序调用 `replace_concept_mentions()`、`write_source_note()`、`update_concept_source_frontmatter()`，概念页 frontmatter 的 `sources`、`source_hashes`、`source_timestamps` 追溯更新路径仍保留。尝试运行 `python test_core_features.py` 失败，原因是当前环境没有 `python` 命令；尝试运行 `py test_core_features.py` 失败，提示 `No installed Python found!`。
    - 提交状态：尝试只暂存 `utils/processing_workflow.py`、`utils/source_index.py`、`test_core_features.py`，但 `git add` 因无法创建 `.git/index.lock` 返回 `Permission denied`；申请沙箱外 `git add` 时自动审批服务返回 503，未获授权，因此仍无法完成 git commit。未绕过权限限制，未暂存 `AGENTS.md` 或 `goal-1/`。
    - 剩余风险：Python 不可用，新增测试没有解释器级执行证据；`source_timestamps` frontmatter 使用简单一维列表生成，适合当前 `wiki_editor.read_frontmatter()`，但不是完整 YAML 库解析能力；真实含逗号的路径/概念名后续可能需要更强 frontmatter 序列化。Task 2 的未提交代码仍留在工作区。
    - 下一步：下一轮必须先执行“大型检查-debug循环 1”，全面检查前三个任务是否偏离、是否有 bug、测试/构建受限情况、安全与数据一致性风险，并把检查结果写入本文件；权限恢复后优先运行 `test_core_features.py` 并提交前三个任务的代码改动。

## 大型检查-debug循环 1
- [x] 在 Task 3 完成后执行
  - 检查项：需求偏离、bug、类型检查、构建、测试、UI/UX、安全、数据一致性、回滚方案、文档同步。
  - 记录：
    - 需求偏离：Task 1-3 均围绕视频结构化转译、来源元数据、Markdown 可追溯性推进，没有进入 Markdown 即时渲染或 Provider 配置等后续任务；范围符合当前 goal 拆分。
    - 代码检查：复读 `utils/processing_workflow.py`、`utils/source_index.py`、`test_core_features.py` 与完整 diff；确认 Task 2 的结构化输入包含 hash、duration、媒体元数据和 `【来源时间戳片段】`；确认 Task 3 的来源页 frontmatter 与正文均包含时间戳双链；确认 `ProcessingWorkflow.run()` 仍保留 `replace_concept_mentions()`、`write_source_note()`、`update_concept_source_frontmatter()` 的追溯更新顺序。
    - 修复：检查中发现 `SourceIndex._build_source_note_content()` 对 `source["source_name"]`、`source["source_uri"]`、`source["source_hash"]`、`source["source_note_path"]` 等字段直取，旧记录或部分构造 source dict 可能触发 `KeyError`；已改为 `.get()` 并提供默认值，`source_note_path` 缺失时回退 `_source_note_path(source_name)`。
    - 静态验证：`git diff --check` 通过；`git diff --check -- utils/processing_workflow.py utils/source_index.py test_core_features.py` 通过；`Select-String` 检查未发现 `metadata_value`、`metadata_source_value`、`TODO`、`FIXME`、`eval(`、`exec(`；检查 `utils/source_index.py` 已无 `source['source_...']` / `source["source_..."]` 直取残留。上述命令仅提示 CRLF 换行警告。
    - 测试/构建：`Get-Command` 显示只有 `py.exe` 启动器、`node.exe`、`npm.ps1`，没有 `python`；`python test_core_features.py` 失败，原因 `python` 命令不存在；`py test_core_features.py` 失败，提示 `No installed Python found!`。`npm run test` 与 `npm run build` 在沙箱内失败，原因仍为 esbuild 无法读取 `../../..` 且无法解析 `frontend/vite.config.ts`，属于当前沙箱权限限制；此前申请沙箱外执行多次遇到审批服务 503，未绕过。
    - UI/UX：本轮未修改前端 UI；来源页 Markdown 输出新增时间戳双链，对前端来源片段跳转和 Obsidian 可追溯性是正向增强。未进行浏览器/GUI 运行验证，原因是本轮范围为检查循环且前端构建受限。
    - 安全性：检索 `your-api-key`、`sk-`、`api_key`、`API_KEY`、`password`、`admin123`，未发现真实 API Key；只存在占位 Key、运行时配置字段和 README/后端已有演示账号逻辑。`.gitignore` 已覆盖 `*.db`、`data/crucible.db`、`data/local_settings.json`、`data/backups/`、`data/vault/`、`temp/`、`app.log`；`git ls-files 'data/*' 'temp/*' 'app.log' '*.db'` 为空，未跟踪用户数据。
    - 数据一致性：新增来源页 `source_timestamps` 与正文时间戳链接都由 `source_timestamp_link()` 生成；segments 仍由 `replace_segments()` 写入 SQLite，concept_mentions 仍由 `replace_concept_mentions()` 建立，概念页 frontmatter 仍由 `update_concept_source_frontmatter()` 更新。剩余风险是 frontmatter 列表仍是简单字符串列表序列化，含逗号的值后续需要更完整 YAML 序列化。
    - 回滚方案：本轮只涉及 `utils/processing_workflow.py`、`utils/source_index.py`、`test_core_features.py` 和 goal 文档；若出现回归，可只回滚这三个代码/测试文件对应 diff。未执行破坏性 git 操作。
    - 文档同步：`goal-1/tasks.md` 已记录 Task 1-3 和本检查结果；README 尚未更新，因为产品能力仍处于中间阶段，按计划留到 Task 12。
    - Git 状态：`AGENTS.md` 仍有用户既有改动，不属于本轮；`goal-1/` 是计划目录不提交。尝试 `git add -- utils/processing_workflow.py utils/source_index.py test_core_features.py` 仍因无法创建 `.git/index.lock` 返回 `Permission denied`；未获沙箱外授权，无法 commit。
    - 结论：前三个任务方向正确，检查中发现的 source dict 兼容性问题已修复；当前最大阻塞是 Python/Git/前端构建验证权限环境，不是业务实现本身。下一步进入 Task 4，分析并优化 Markdown 即时渲染路径。

- [x] Task 4: 分析并优化 Markdown 即时渲染路径
  - 范围：定位 GUI 中 Markdown 渲染触发和刷新策略，减少不必要全量刷新或主线程重活。
  - 可验证结果：新增可测的渲染调度/缓存逻辑，或给现有逻辑补充性能保护。
  - 完成记录：
    - 改动：定位到当前 Web Markdown 预览路径为前端 `frontend/src/main.tsx` 编辑器 `useEffect` 250ms 防抖调用后端 `/api/notes/preview`，后端 `backend/app.py` 调用 `wiki_editor.render_markdown_preview()`，最终由 `markdown-it-py` 同步全量渲染。更新 `utils/wiki_editor.py`，为 Markdown 预览增加基于 `len(content)+sha256(content)` 的线程安全 LRU 缓存，默认保留 32 项，避免打开、保存、重复预览同一大文档时反复全量渲染。更新 `frontend/src/main.tsx`，增加前端预览缓存、`AbortController` 中止过时请求、同 key 请求去重、LRU 上限 24 项，并把打开/保存/新建/整理规则/打开 wiki target 时后端已经返回的 `preview_html` 写入前端缓存，避免紧接着二次 POST 预览。更新 `frontend/src/utils.ts`，新增轻量 `previewCacheKey(path, content)`；更新 `frontend/src/main.test.ts` 覆盖 key 稳定性；更新 `test_core_features.py` 覆盖后端预览缓存有界行为。
    - 验证：`git diff --check -- utils/wiki_editor.py frontend/src/main.tsx frontend/src/utils.ts frontend/src/main.test.ts test_core_features.py` 通过，仅提示 CRLF 换行警告；`Select-String` 确认 `previewCacheKey`、`previewAbortRef`、`PREVIEW_CACHE_LIMIT`、`_preview_cache`、`AbortError`、`signal` 等实现点存在；复读 `frontend/src/main.tsx` 预览 effect，确认旧请求 cleanup 会 abort，旧请求 finally 因 `cancelled` 不会错误清除新请求 pending，`openNote` 的 `useCallback` 依赖已补入 `rememberPreview`。
    - 受限验证：`python test_core_features.py` 失败，原因 `python` 命令不存在；`py test_core_features.py` 失败，提示 `No installed Python found!`。`npm run test` 仍在沙箱内失败，原因 esbuild 无法读取 `../../..` 且无法解析 `frontend/vite.config.ts`；申请沙箱外 `npm run test` 和 `npm run build` 时自动审批服务继续返回 503，未获授权，未绕过执行。`git add` 仍因无法创建 `.git/index.lock` 返回 `Permission denied`，无法 commit。
    - 剩余风险：没有 Python/TypeScript 实际执行证据，前端 `AbortController` 和 `DOMException` 类型兼容性未由 `tsc` 证明；后端缓存按内容 hash 缓存 HTML，若未来 Markdown 渲染依赖外部上下文，需要把上下文纳入 cache key；前端 cache key 使用轻量 32-bit hash，理论上有碰撞风险，但 key 同时包含路径和长度，当前作为 UI 预览缓存可接受。
    - 下一步：Task 5 应继续检查耗时视频/模型/索引任务的异步边界，尤其是 GUI/Web 入口是否仍可能在主线程执行重活；权限恢复后优先运行 `test_core_features.py`、`npm run test`、`npm run build` 并提交当前代码改动。

- [x] Task 5: 引入或完善异步任务边界
  - 范围：检查耗时视频/模型/索引任务是否阻塞 GUI，优先复用现有线程或任务机制。
  - 可验证结果：相关任务通过 worker/队列执行，测试或静态检查证明 UI 入口不直接执行重活。
  - 完成记录：
    - 改动：检查 Web 后端 `/api/process` 与 PyQt GUI `start_ai_flow()`。Web 端原先每个处理任务直接 `threading.Thread(target=runner, daemon=True).start()`，虽然不阻塞请求线程，但重复上传/重试可创建无限后台线程；更新 `backend/app.py`，引入模块级 `ThreadPoolExecutor`，通过 `_process_executor.submit(runner)` 统一提交耗时 `ProcessingWorkflow.run()`，默认并发数 2，可用 `CRUCIBLE_PROCESS_WORKERS` 配置，并通过 `_process_worker_count()` 安全解析无效环境变量。GUI 端已使用 `AIWorker(QThread)`，本轮补充 `self.active_worker and self.active_worker.isRunning()` 重入防护，避免重复点击启动并发任务；创建 worker 时使用 `file_paths=list(self.selected_files)`，避免后台线程持有可变列表引用；任务结束时显式 `self.active_worker = None`。
    - 验证：`git diff --check -- backend/app.py gui.py test_core_features.py` 通过，仅提示 CRLF 换行警告；`Select-String` 确认 `ThreadPoolExecutor`、`_process_executor.submit(runner)`、`def _process_worker_count()`、GUI `isRunning()` 防护、`file_paths=list(self.selected_files)` 和新增测试存在。新增 `test_process_entrypoints_keep_heavy_work_async()` 静态测试，断言后端使用 executor、没有直接 `threading.Thread(target=runner`，并断言 GUI 有重复启动防护和列表拷贝。
    - 受限验证：`python test_core_features.py` 失败，原因 `python` 命令不存在；`py test_core_features.py` 失败，提示 `No installed Python found!`。`npm run build` 仍因沙箱 esbuild 无法读取上级目录/解析 `vite.config.ts` 失败。`git add` 仍因无法创建 `.git/index.lock` 返回 `Permission denied`，无法 commit。
    - 剩余风险：无法运行 Python 解释器验证 `backend/app.py` 导入和 executor 行为；`ThreadPoolExecutor` 是进程内队列，服务重启会丢失队列和 `_jobs` 状态，后续 Task 7/10 可考虑持久化 job 状态；GUI 仍不支持取消正在运行的 `AIWorker`，只是防止重复启动；Web 前端仍允许用户排队多个任务，只是后端并发受控。
    - 下一步：Task 6 应检查 `config.py` 与 `models/` Provider 抽象，补齐 API Key 脱敏、Provider 不可用时的错误处理和本地降级行为；权限恢复后优先运行 `test_core_features.py`、前端测试/构建并提交当前所有代码改动。

- [x] Task 6: 强化模型 Provider 配置与安全降级
  - 范围：检查 `config.py` 和 `models/` Provider 抽象，补齐 API Key 脱敏、OpenAI-compatible、本地兜底或错误处理缺口。
  - 可验证结果：离线测试覆盖无真实 Key、Provider 不可用、本地 fallback 的行为。
  - 完成记录：
    - 改动：更新 `config.py`，新增 `LOCAL_PROVIDERS`、`is_local_provider()`、支持传入 provider 的 `has_valid_api_key()`、`mask_secret()` 与 `redact_secrets()`，让本地 OpenAI-compatible Provider 可空 Key，同时为日志/错误消息提供统一脱敏。更新 `models/api_client.py`，新增 `ProviderUnavailableError`，客户端记录当前 provider，调用前阻止占位 Key/空 Key 访问云端 Provider，非 200 响应和异常信息经过脱敏后再抛出。更新 `models/llm_core.py`，在 Provider 不可用时让概念抽取降级为空列表，并为已有概念合并提供 `_build_fallback_concept_note()` 保守 Markdown 模板，避免整个视频导入因云端不可用直接崩溃。更新 `models/vlm_analyzer.py`，本地 VLM 加载失败时仅在存在有效 API Key 时降级到 API，否则跳过视觉分析并记录 warning；分析入口在 VLM Provider 与本地模型均不可用时返回空结果。更新 `test_core_features.py`，新增无效云端 Key 阻止调用、本地 Provider 空 Key 合法、运行期密钥脱敏、LLM/VLM 降级路径存在的离线测试。
    - 验证：`git diff --check -- config.py models/api_client.py models/llm_core.py models/vlm_analyzer.py test_core_features.py` 通过，仅提示 CRLF 换行警告；`Select-String` 确认 `ProviderUnavailableError`、`redact_secrets`、`mask_secret`、`is_local_provider`、`_build_fallback_concept_note`、VLM 双不可用跳过路径和新增测试存在。复读本轮 diff，确认云端调用前会校验 `Config.has_valid_api_key(self.api_key, provider=self.provider)`，API 错误体通过 `Config.redact_secrets(response.text)` 后截断，VLM 本地失败不会在无有效 Key 时强行切到 API。检索 `TODO`、`FIXME`、`eval(`、`exec(` 未发现新增问题；检索 `response.text`、`Authorization`、`api_key` 相关位置，确认仅保留请求头构造和已脱敏错误体。尝试运行 `python test_core_features.py` 失败，原因 `python` 命令不存在；尝试运行 `py test_core_features.py` 失败，提示 `No installed Python found!`。
    - 提交状态：尝试只暂存 `config.py`、`models/api_client.py`、`models/llm_core.py`、`models/vlm_analyzer.py`、`test_core_features.py`，但 `git add` 因无法创建 `.git/index.lock` 返回 `Permission denied`；按规则申请沙箱外 `git add`，自动审批服务返回 503 并拒绝，未获授权，因此本轮仍无法 commit。未绕过权限限制，未暂存 `AGENTS.md`、`goal-1/` 或其他前序任务文件。
    - 剩余风险：当前环境没有 Python，新增测试无法实际执行，不能证明解释器级语法和导入链路完全通过；`extract_concepts()` 在 Provider 不可用时返回空概念会保留来源页和片段索引，但不会生成概念页，属于保守降级，后续 Task 8/10 可补离线 mock 端到端样例；`_build_fallback_concept_note()` 只在已有概念数据进入合并阶段时兜底，不能凭空替代 LLM 抽取；API Base、网络不可达、认证失败等外部错误现在统一为 `ProviderUnavailableError`，上层能降级但错误类型更粗。
    - 下一步：下一轮必须执行“大型检查-debug循环 2”，全面检查 Task 4-6 是否偏离、Markdown 渲染缓存/异步队列/Provider 降级是否存在交叉 bug，继续记录 Python/Git/前端构建受限情况；权限恢复后优先运行 `test_core_features.py`、`npm run test`、`npm run build` 并提交当前代码改动。

## 大型检查-debug循环 2
- [x] 在 Task 6 完成后执行
  - 检查项：需求偏离、bug、类型检查、构建、测试、UI/UX、安全、数据一致性、回滚方案、文档同步。
  - 记录：
    - 需求偏离：Task 4-6 分别围绕 Markdown 即时渲染性能、耗时任务异步边界、Provider 安全降级推进，均服务于“视频结构化转译 + Markdown 即时渲染性能 + 本地/云端安全可用”的目标，没有提前进入 SQLite 数据一致性或知识页扩展等后续任务。
    - 代码检查：复读 `utils/wiki_editor.py`、`frontend/src/main.tsx`、`frontend/src/utils.ts`、`frontend/src/main.test.ts`、`backend/app.py`、`gui.py`、`config.py`、`models/api_client.py`、`models/llm_core.py`、`models/vlm_analyzer.py` 与相关 diff。确认 Markdown 预览后端有线程安全 LRU 缓存，前端有 `AbortController` 取消过时请求、同内容缓存和同 key 去重；确认 Web 处理任务已由 `ThreadPoolExecutor` 控制并发，GUI 有重复启动防护；确认云端 Provider 缺少有效 Key 时调用前拦截，VLM 双不可用时跳过视觉分析，LLM 可保守降级。
    - 修复：检查中发现 `/api/process` 会把完整 `payload` 存入 `_jobs[job_id]["payload"]`，其中可能包含用户传入的 `api_key`，随后 `GET /api/process`、`GET /api/process/{job_id}` 或 retry payload 都可能暴露密钥；已新增 `_job_payload_snapshot()`，任务快照中强制 `api_key = None`，避免展示/持久化密钥。进一步发现失败路径 `_jobs[job_id]["error"] = str(exc)` 和日志 `error={exc}` 可能携带底层异常中的密钥；已改为 `safe_error = Config.redact_secrets(str(exc))`，job 错误与日志都只写脱敏文本。更新 `test_core_features.py` 静态测试，断言 job payload 使用快照、不会直接保存 `payload.model_dump()` / `payload.dict()`，并断言失败错误使用 `safe_error`。
    - 静态验证：`git diff --check -- backend/app.py test_core_features.py config.py models/api_client.py models/llm_core.py models/vlm_analyzer.py utils/wiki_editor.py frontend/src/main.tsx frontend/src/utils.ts frontend/src/main.test.ts gui.py` 通过，仅提示 CRLF 换行警告。`Select-String` 检查 `TODO`、`FIXME`、`eval(`、`exec(`、`_jobs[job_id]["error"] = str`、`error={exc}`、`threading.Thread(target=runner` 未发现残留；检查到 `payload.model_dump()` / `payload.dict()` 只存在于 `_job_payload_snapshot()` 内部并立即清空 `api_key`，不再直接写入 `_jobs`。
    - 测试/构建：`python test_core_features.py` 失败，原因 `python` 命令不存在；`py test_core_features.py` 失败，提示 `No installed Python found!`。`npm run test` 与 `npm run build` 在沙箱内仍失败，原因是 esbuild 无法读取 `../../..` 且无法解析 `frontend/vite.config.ts`，属于当前沙箱权限限制；申请沙箱外 `npm run test` 与 `npm run build` 时自动审批服务继续返回 503，未获授权，未绕过。
    - UI/UX：本轮检查未新增可见 UI；Task 4 的前端缓存和中止请求逻辑理论上减少预览闪烁和过时响应覆盖，但由于 Vite/Vitest 受限，未获得浏览器或构建级证据。GUI 重复启动防护不会改变正常单次处理流程，只在已有任务运行时给出防重入提示。
    - 安全性：已修复 Web process job payload 与失败错误中的潜在 API Key 泄露；`Config.redact_secrets()` 会替换当前运行期真实 Key 和占位 key。仍需后续 Task 11 对 GUI 日志、后端配置测试响应和管理日志做更完整脱敏审查。
    - 数据一致性：Markdown 预览缓存只缓存渲染 HTML，不写 vault；异步 executor 只限制并发，不改变 `ProcessingWorkflow.run()` 的来源索引写入顺序；Provider 降级为空概念时仍可写来源页和片段索引，但不会生成概念页，属于保守数据落盘。进程内 `_jobs` 队列仍非持久化，服务重启会丢 job 状态，留到 Task 7/10 评估。
    - 回滚方案：本检查循环新增修复主要在 `backend/app.py` 与 `test_core_features.py`；若出现 retry 行为回归，可只调整 `_job_payload_snapshot()` 与 retry 密钥策略。不要回滚 `AGENTS.md` 用户改动，不要执行破坏性 git 操作。
    - 文档同步：`goal-1/tasks.md` 已记录本检查结果；README 暂不更新，按计划留到 Task 12 最终文档。
    - Git 状态：`git status --short` 仍显示 `AGENTS.md` 为用户既有改动，`goal-1/` 未跟踪且不提交；前序任务与本轮代码均未暂存。尝试 `git add -- backend/app.py test_core_features.py` 仍因无法创建 `.git/index.lock` 返回 `Permission denied`；未获沙箱外授权，无法 commit。
    - 结论：Task 4-6 方向正确，本轮检查发现并修复了 process job 泄露 API Key 的高风险问题；当前主要未验证项仍是 Python 解释器缺失、前端沙箱构建权限和 git index 写权限。下一轮进入 Task 7，重点强化 SQLite/索引数据一致性。

- [x] Task 7: 强化 SQLite/索引数据一致性
  - 范围：检查数据库 schema、写入事务、重复导入识别、失败状态、搜索索引更新。
  - 可验证结果：测试覆盖重复导入、失败回滚、索引可查询。
  - 完成记录：
    - 改动：更新 `utils/db_manager.py`，让每个 SQLite 连接执行 `PRAGMA foreign_keys = ON`，使 `segments`、`concept_mentions` 上声明的外键与级联规则真实生效；新增 `idx_segments_source_id`、`idx_concept_mentions_source_id`、`idx_concept_mentions_segment_id`，补齐来源详情、级联删除、按 segment/source 查询的热点索引。更新 `utils/source_index.py`，新增 `replace_source_index()`，在单个 SQLite 事务内完成 source upsert、旧 mentions 删除、旧 segments 删除、新 segments 写入、新 concept_mentions 写入；抽出 `_source_note_rel_path()` 和 `_insert_concept_mentions()`，让旧的 `replace_concept_mentions()` 与新事务入口复用一致的 mention 生成逻辑。更新 `utils/processing_workflow.py`，把处理流程从 `upsert_source()` + `replace_segments()` + `replace_concept_mentions()` 三次独立提交，改为一次 `replace_source_index()`，避免处理失败时留下半更新索引。更新 `test_core_features.py`，新增重复导入覆盖、索引查询覆盖、外键开启检查、事务失败回滚检查。
    - 验证：`git diff --check -- utils/db_manager.py utils/source_index.py utils/processing_workflow.py test_core_features.py` 通过，仅提示 CRLF 换行警告；`Select-String` 确认 `PRAGMA foreign_keys`、新增索引、`replace_source_index()`、工作流调用 `source_index.replace_source_index()`、重复导入测试和 rollback 测试存在；复读本轮 diff，确认 `ProcessingWorkflow.run()` 已不再直接调用 `source_index.replace_segments()` / `source_index.replace_concept_mentions()`，核心处理路径只走单事务入口。按用户指示，本轮不再由我执行 Python 测试或 git 提交，需用户本机运行 `python test_core_features.py` 与提交命令并反馈结果。
    - 剩余风险：我无法在当前环境证明新增测试实际通过；`replace_source_index()` 与旧 `upsert_source()` / `replace_segments()` / `replace_concept_mentions()` 并存是为了兼容现有调用，但后续若其他模块继续手动组合旧方法，仍可能产生非原子写入；当前事务覆盖的是 SQLite 索引，不包含随后写来源 Markdown 文件的磁盘写入，数据库与 Markdown 文件之间仍可能在极端崩溃下不一致，后续 Task 8/10 可通过端到端离线样例和恢复策略继续收口。
    - 下一步：Task 8 应完善来源页、片段页、概念页的长期知识库沉淀，重点让片段/概念页面不只是来源索引，而是可被 Obsidian 长期维护和反向链接的知识资产；用户先运行 `python test_core_features.py` 和 git 提交命令，并把结果反馈回来。

- [ ] Task 8: 完善来源页、片段页、概念页的知识库沉淀
  - 范围：让视频转译结果不仅生成摘要，还沉淀为长期可维护的多类型 Markdown 页面。
  - 可验证结果：离线样例能生成来源页、片段页、概念页，并具有反向链接关系。
  - 完成记录：
    - 改动：
    - 验证：
    - 剩余风险：
    - 下一步：

- [ ] Task 9: 性能基线与回归保护
  - 范围：为视频结构化转译关键步骤和 Markdown 渲染调度建立轻量性能基线。
  - 可验证结果：新增可离线运行的性能/计时测试或诊断命令，不依赖大文件和真实模型。
  - 完成记录：
    - 改动：
    - 验证：
    - 剩余风险：
    - 下一步：

## 大型检查-debug循环 3
- [ ] 在 Task 9 完成后执行
  - 检查项：需求偏离、bug、类型检查、构建、测试、UI/UX、安全、数据一致性、回滚方案、文档同步。
  - 记录：

- [ ] Task 10: 整合端到端离线样例
  - 范围：提供无需真实 API Key 的小样例或 mock 流程，从导入素材到生成 Markdown 知识资产。
  - 可验证结果：单条命令可验证核心链路。
  - 完成记录：
    - 改动：
    - 验证：
    - 剩余风险：
    - 下一步：

- [ ] Task 11: GUI 可用性与错误处理收口
  - 范围：检查核心流程按钮、状态提示、异常提示、取消/失败恢复、日志脱敏。
  - 可验证结果：关键 UI 入口有清晰状态和异常处理；测试或静态验证覆盖错误路径。
  - 完成记录：
    - 改动：
    - 验证：
    - 剩余风险：
    - 下一步：

- [ ] Task 12: 文档与最终全面 review
  - 范围：更新 README 或项目文档，执行最终最大的 review，并修缮发现的高风险问题。
  - 可验证结果：最终测试通过，文档说明当前能力、验证命令、限制和回滚方式；goal 可标记完成。
  - 完成记录：
    - 改动：
    - 验证：
    - 剩余风险：
    - 下一步：

## 大型检查-debug循环 4 / Final Review
- [ ] 在 Task 12 完成后执行
  - 检查项：C 端体验、代码、安全性、数据一致性、权限、错误处理、测试、构建、文档、回滚。
  - 记录：
