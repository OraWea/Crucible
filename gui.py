import os
import sys

# 将项目父目录添加至 Python 路径，以支持以 Crucible.xxx 的包形式导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import logging
import datetime
from typing import List, Dict
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox, QTextEdit,
    QProgressBar, QTreeView, QTabWidget, QDialog, QFormLayout, QMessageBox,
    QFileDialog, QHeaderView, QTableWidget, QTableWidgetItem, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDir
from PyQt6.QtGui import QFont, QFileSystemModel, QIcon, QTextCursor

# 载入配置及工具类
from Crucible.config import Config
from Crucible.utils.db_manager import db_manager
from Crucible.utils.audio_processor import audio_processor
from Crucible.utils.doc_parser import doc_parser
from Crucible.utils.fs_router import fs_router
from Crucible.utils.wiki_editor import wiki_editor

# 载入 AI 核心模块
from Crucible.models.whisper_model import WhisperTranscriber
from Crucible.models.vlm_analyzer import vlm_analyzer
from Crucible.models.llm_core import llm_core
from Crucible.models.fact_checker import fact_checker

# 初始化各路径
Config.init_paths()

# 设置 Python 日志到本地文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Crucible_GUI")


# =====================================================================
# 1. 登录与注册 Dialog 窗体
# =====================================================================
class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crucible | 智能知识库登录")
        self.setFixedSize(380, 240)
        self.user_role = None
        self.username = None
        
        # 预置默认账户以便演示与评分
        self._init_default_users()
        self._setup_ui()
        self._apply_style()

    def _init_default_users(self):
        """如果用户表为空，则注入默认演示账户"""
        try:
            import hashlib
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                # 检查是否存在 users 表，不存在则直接建表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL
                    )
                """)
                cursor.execute("SELECT COUNT(*) as cnt FROM users")
                if cursor.fetchone()["cnt"] == 0:
                    # 默认管理员: admin / admin123
                    h_admin = hashlib.sha256("admin123".encode()).hexdigest()
                    cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                                   ("admin", h_admin, "admin"))
                    
                    # 默认普通用户: user / user123
                    h_user = hashlib.sha256("user123".encode()).hexdigest()
                    cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                                   ("user", h_user, "user"))
                    conn.commit()
                    logger.info("系统检测到空库，已自动注入默认账户 admin(管理员) 与 user(普通用户)。")
        except Exception as e:
            logger.error(f"预置账户初始化失败: {e}")

    def _setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        title = QLabel("Crucible Second Brain")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #7f6df2; margin-bottom: 10px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("请输入用户名")
        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pass.setPlaceholderText("请输入密码")
        
        form.addRow("用户名:", self.txt_user)
        form.addRow("密  码:", self.txt_pass)
        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        self.btn_login = QPushButton("登录")
        self.btn_register = QPushButton("注册新账户")
        btn_layout.addWidget(self.btn_login)
        btn_layout.addWidget(self.btn_register)
        layout.addLayout(btn_layout)

        # 信号绑定
        self.btn_login.clicked.connect(self.handle_login)
        self.btn_register.clicked.connect(self.handle_register)

    def _apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e3e3e3;
            }
            QLabel {
                color: #a3a3a3;
                font-size: 13px;
                font-weight: bold;
            }
            QLineEdit {
                background-color: #262626;
                border: 1px solid #363636;
                border-radius: 5px;
                padding: 6px;
                color: #e3e3e3;
            }
            QLineEdit:focus {
                border: 1px solid #7f6df2;
            }
            QPushButton {
                background-color: #7f6df2;
                color: #ffffff;
                font-weight: bold;
                border: none;
                border-radius: 5px;
                padding: 8px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #6b58e7;
            }
            QPushButton#btn_register {
                background-color: #2e2e2e;
                color: #e3e3e3;
                border: 1px solid #363636;
            }
            QPushButton#btn_register:hover {
                background-color: #363636;
            }
            
            /* QMessageBox styling */
            QMessageBox {
                background-color: #f0f0f0;
            }
            QMessageBox QLabel {
                color: #000000;
                font-size: 13px;
                font-weight: normal;
            }
            QMessageBox QPushButton {
                background-color: #e1e1e1;
                color: #000000;
                border: 1px solid #acacac;
                border-radius: 4px;
                padding: 5px 15px;
                min-width: 70px;
                font-weight: normal;
            }
            QMessageBox QPushButton:hover {
                background-color: #e5f1fb;
                border-color: #0078d7;
            }
            QMessageBox QPushButton:pressed {
                background-color: #cce4f7;
                border-color: #005499;
            }
        """)
        self.btn_register.setObjectName("btn_register")

    def handle_login(self):
        username = self.txt_user.text().strip()
        password = self.txt_pass.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "错误提示", "用户名或密码不能为空！")
            return

        import hashlib
        h_pass = hashlib.sha256(password.encode()).hexdigest()

        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT role FROM users WHERE username = ? AND password_hash = ?", 
                               (username, h_pass))
                row = cursor.fetchone()
                if row:
                    self.username = username
                    self.user_role = row["role"]
                    db_manager.add_log("INFO", "GUI", "User_Login", f"用户 {username} 成功登录系统")
                    self.accept()
                else:
                    QMessageBox.warning(self, "认证失败", "用户名或密码错误，请重试！")
        except Exception as e:
            QMessageBox.critical(self, "系统错误", f"数据库查询失败: {e}")

    def handle_register(self):
        username = self.txt_user.text().strip()
        password = self.txt_pass.text().strip()

        if len(username) < 3 or len(password) < 6:
            QMessageBox.warning(self, "注册失败", "用户名至少3位，密码至少6位！")
            return

        import hashlib
        h_pass = hashlib.sha256(password.encode()).hexdigest()

        try:
            with db_manager.get_connection() as conn:
                cursor = conn.cursor()
                # 检查用户名是否重复
                cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                if cursor.fetchone():
                    QMessageBox.warning(self, "注册失败", "该用户名已被注册，请换一个！")
                    return
                
                # 新注册账号一律默认为普通 user 权限
                cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                               (username, h_pass, "user"))
                conn.commit()
                QMessageBox.information(self, "注册成功", "账户注册成功，您现在可以登录了！")
                db_manager.add_log("INFO", "GUI", "User_Register", f"新用户 {username} 注册成功")
        except Exception as e:
            QMessageBox.critical(self, "系统错误", f"数据库写入失败: {e}")


# =====================================================================
# 2. QThread 后台 AI 异步工作线程
# =====================================================================
class AIWorker(QThread):
    progress_signal = pyqtSignal(str, int) # 发送日志与当前进度百分比
    finished_signal = pyqtSignal(bool, str) # 发送处理成功与否及最终提示信息

    def __init__(self, file_paths: List[str], whisper_lang: str = 'auto', 
                 use_reflection: bool = True, custom_api_key: str = None):
        super().__init__()
        self.file_paths = file_paths
        self.whisper_lang = whisper_lang
        self.use_reflection = use_reflection
        self.custom_api_key = custom_api_key

    def run(self):
        temp_dir = Config.TEMP_DIR
        try:
            # 如果用户在界面临时修改了 API KEY，动态同步至全局配置
            if self.custom_api_key:
                Config.LLM_API_KEY = self.custom_api_key
                llm_core.api_key = self.custom_api_key
                vlm_analyzer.api_key = self.custom_api_key
                fact_checker.api_key = self.custom_api_key

            self.progress_signal.emit(">>> Crucible AI 工作流启动 ...", 5)
            
            for file_path in self.file_paths:
                if not os.path.exists(file_path):
                    continue
                
                filename = os.path.basename(file_path)
                ext = os.path.splitext(filename)[1].lower()
                
                self.progress_signal.emit(f"开始处理源文件: {filename}", 10)
                
                # 分流处理：音视频 VS 纯文档
                if ext in Config.SUPPORTED_VIDEO_FORMATS or ext in Config.SUPPORTED_AUDIO_FORMATS:
                    # 1. 媒体抽取与重采样
                    self.progress_signal.emit("第一步: 音频分离与重采样中...", 20)
                    wav_path = audio_processor.process_media(file_path, temp_dir)
                    
                    # 2. ASR 语音转录
                    self.progress_signal.emit("第二步: Whisper 转写语音文本中...", 40)
                    # 动态实例化本地转录器，用完即毁释放内存
                    transcriber = WhisperTranscriber()
                    segments = transcriber.transcribe(wav_path, language=self.whisper_lang)
                    
                    # 拼接 ASR 文本作为输入源
                    full_source_text = "\n".join([f"[{seg['start']}-{seg['end']}s]: {seg['text']}" for seg in segments])
                    
                    # 3. 如果是视频文件，调用 VLM 场景感知
                    vlm_contexts = {}
                    if ext in Config.SUPPORTED_VIDEO_FORMATS:
                        self.progress_signal.emit("第三步: 抽取视频关键帧并执行 VLM 分析 (OCR + 描述)...", 60)
                        # 动态根据时长抽 3 个时间点的帧进行多模态分析
                        duration = audio_processor.get_audio_duration(wav_path)
                        ts_list = [round(duration * 0.1, 2), round(duration * 0.5, 2), round(duration * 0.9, 2)]
                        vlm_contexts = vlm_analyzer.analyze_video(file_path, ts_list)
                        
                    # 整合 ASR 文本与 VLM 视觉感知
                    structured_source = "【视频声音转写内容】:\n" + full_source_text + "\n\n"
                    if vlm_contexts:
                        structured_source += "【视频画面抽帧分析】:\n"
                        for ts, ctx in vlm_contexts.items():
                            structured_source += f"- 在 {ts}s 画面:\n  OCR 文字: {ctx['ocr']}\n  画面描述: {ctx['description']}\n"
                    
                elif ext in Config.SUPPORTED_DOC_FORMATS:
                    # 1. 文档解析
                    self.progress_signal.emit("第一步: 解析并读取文档文本...", 30)
                    structured_source = doc_parser.parse_file(file_path)
                    
                else:
                    self.progress_signal.emit(f"不支持的文件格式: {filename}", 0)
                    continue

                # 4. LLM 知识抽取与合并 (Qwen)
                self.progress_signal.emit("第四步: Qwen LLM 智能提炼核心概念...", 75)
                extracted_concepts = llm_core.extract_concepts(structured_source)
                
                self.progress_signal.emit(f"成功提取 {len(extracted_concepts)} 个概念，开始合并织网...", 85)
                
                # 遍历写入或更新 Obsidian 本地文件
                for idx, concept_item in enumerate(extracted_concepts):
                    concept_name = concept_item["concept"]
                    self.progress_signal.emit(f"合并 Wiki 页面: {concept_name}...", 85 + int((idx/len(extracted_concepts))*10))
                    
                    # 调用大脑生成或合并旧文件
                    merged_md = llm_core.merge_and_write_wiki(concept_item, filename)
                    
                    # 5. NLI 事实一致性核对 (LLM-as-a-Judge)
                    self.progress_signal.emit(f"执行事实一致性核对 -> {concept_name} ...", 95)
                    check_result = fact_checker.check_consistency(structured_source, merged_md)
                    
                    # 将核对的评分更新入 markdown 头部 frontmatter 中
                    file_path = fs_router.locate_concept_file(concept_name)
                    if file_path and os.path.exists(file_path):
                        content = wiki_editor.read_wiki(file_path)
                        # 将评分追加到 metadata 区域
                        if 'qe_score:' not in content:
                            updated_content = content.replace("---", f"qe_score: {check_result['score']}\n---", 1)
                            wiki_editor.write_wiki_atomic(file_path, updated_content)

            self.progress_signal.emit(">>> Crucible AI 工作流成功执行完毕！", 100)
            self.finished_signal.emit(True, f"成功处理完成，已生成并更新所有关联笔记。")
        except Exception as e:
            logger.error(f"后台 AIWorker 执行中断: {e}", exc_info=True)
            self.progress_signal.emit(f"❌ 运行发生错误: {e}", 0)
            self.finished_signal.emit(False, str(e))


# =====================================================================
# 3. 主界面 Window 窗体
# =====================================================================
class MainWindow(QMainWindow):
    def __init__(self, username: str, role: str):
        super().__init__()
        self.username = username
        self.user_role = role
        self.selected_files = []
        self.active_worker = None

        self.setWindowTitle("Crucible | 智能自更新知识库工作台 (Phase 1: Local MVP)")
        self.resize(1280, 800)
        
        self._setup_ui()
        self._apply_theme()
        self.refresh_vault_tree()

    def _setup_ui(self):
        # 核心中央小部件
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(15, 12, 15, 15)
        main_layout.setSpacing(10)

        # -------------------------------------------------------------
        # 头部 Top Bar (标题、登录信息)
        # -------------------------------------------------------------
        top_bar = QHBoxLayout()
        logo_label = QLabel("CRUCIBLE")
        logo_label.setStyleSheet("font-size: 20px; font-weight: 800; color: #7f6df2; font-family: 'Segoe UI', 'Microsoft YaHei'; letter-spacing: 1.5px;")
        user_info = QLabel(f"当前用户: {self.username} ({'管理员' if self.user_role == 'admin' else '普通用户'})")
        user_info.setStyleSheet("color: #a3a3a3; font-size: 12px; font-weight: 500;")
        
        top_bar.addWidget(logo_label)
        top_bar.addStretch()
        top_bar.addWidget(user_info)
        main_layout.addLayout(top_bar)

        # -------------------------------------------------------------
        # 三栏布局 Splitter (左侧目录树、中间控制区、右侧编辑器)
        # -------------------------------------------------------------
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # 3.1 左栏: Obsidian 目录导航
        left_widget = QWidget()
        left_widget.setObjectName("LeftSidebar")
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        title_left = QLabel("Obsidian 知识库目录")
        title_left.setStyleSheet("font-size: 11px; font-weight: 600; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;")
        left_layout.addWidget(title_left)

        self.dir_model = QFileSystemModel()
        self.dir_model.setReadOnly(True)
        self.dir_model.setRootPath(Config.OBSIDIAN_VAULT_PATH)
        
        self.tree_view = QTreeView()
        self.tree_view.setModel(self.dir_model)
        self.tree_view.setRootIndex(self.dir_model.index(Config.OBSIDIAN_VAULT_PATH))
        self.tree_view.setHeaderHidden(True)
        # 隐藏大小、类型、修改时间等列，仅保留名称
        for i in range(1, 4):
            self.tree_view.hideColumn(i)
        
        left_layout.addWidget(self.tree_view)
        splitter.addWidget(left_widget)

        # 3.2 中栏: AI 任务控制中心
        center_tab = QTabWidget()
        
        # Tab 1: AI 工作台
        workbench_widget = QWidget()
        workbench_widget.setObjectName("WorkbenchTab")
        workbench_layout = QVBoxLayout(workbench_widget)
        workbench_layout.setContentsMargins(8, 8, 8, 8)
        workbench_layout.setSpacing(10)
        
        # 拖拽/浏览上传区
        self.upload_frame = QFrame()
        self.upload_frame.setObjectName("UploadFrame")
        self.upload_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.upload_frame.setAcceptDrops(True)
        
        upload_vbox = QVBoxLayout(self.upload_frame)
        upload_icon = QLabel("📥")
        upload_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        upload_icon.setStyleSheet("font-size: 28px;")
        self.upload_text = QLabel("拖拽音视频/文档文件至此，或点击上传")
        self.upload_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.upload_text.setStyleSheet("color: #a3a3a3; font-size: 13px;")
        self.btn_select_file = QPushButton("选择本地文件")
        self.btn_select_file.setFixedWidth(120)
        
        upload_vbox.addWidget(upload_icon)
        upload_vbox.addWidget(self.upload_text)
        upload_vbox.addWidget(self.btn_select_file, alignment=Qt.AlignmentFlag.AlignCenter)
        workbench_layout.addWidget(self.upload_frame)

        # 文件列表展示
        self.lbl_selected = QLabel("未选择任何文件")
        self.lbl_selected.setStyleSheet("color: #a3a3a3; font-size: 12px; margin-top: 5px;")
        workbench_layout.addWidget(self.lbl_selected)

        # 配置参数区
        config_box = QFormLayout()
        config_box.setVerticalSpacing(8)
        config_box.setHorizontalSpacing(10)
        
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Auto (自动检测)", "zh (中文)", "en (英文)", "ja (日语)"])
        config_box.addRow("ASR 语音语言:", self.combo_lang)

        self.txt_api_key = QLineEdit()
        self.txt_api_key.setPlaceholderText("可在此覆盖 .env 中的 LLM API KEY")
        if Config.LLM_API_KEY != 'your-api-key':
            self.txt_api_key.setText(Config.LLM_API_KEY)
        config_box.addRow("LLM API KEY:", self.txt_api_key)
        
        workbench_layout.addLayout(config_box)

        # 开始编织按钮
        self.btn_weave = QPushButton("开始 AI 提取与知识织网")
        self.btn_weave.setObjectName("PrimaryButton")
        workbench_layout.addWidget(self.btn_weave)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        workbench_layout.addWidget(self.progress_bar)

        # 实时日志控制台
        self.console_log = QTextEdit()
        self.console_log.setObjectName("ConsoleLog")
        self.console_log.setReadOnly(True)
        self.console_log.append(">> Crucible console initialized. Ready for operations.")
        workbench_layout.addWidget(self.console_log)
        
        center_tab.addTab(workbench_widget, "AI 知识提炼")

        # Tab 2: 系统审计日志 (仅 Admin 可见)
        if self.user_role == 'admin':
            self.admin_widget = QWidget()
            self.admin_widget.setObjectName("AdminTab")
            admin_layout = QVBoxLayout(self.admin_widget)
            admin_layout.setContentsMargins(8, 8, 8, 8)
            
            title_log = QLabel("系统运行日志 (SQLite)")
            title_log.setStyleSheet("font-size: 11px; font-weight: 600; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;")
            admin_layout.addWidget(title_log)

            self.log_table = QTableWidget()
            self.log_table.setColumnCount(5)
            self.log_table.setHorizontalHeaderLabels(["时间", "模块", "操作", "详情", "耗时(s)"])
            self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            admin_layout.addWidget(self.log_table)

            ctrl_row = QHBoxLayout()
            self.btn_refresh_logs = QPushButton("刷新日志")
            self.btn_export_logs = QPushButton("导出为TXT")
            ctrl_row.addWidget(self.btn_refresh_logs)
            ctrl_row.addWidget(self.btn_export_logs)
            admin_layout.addLayout(ctrl_row)
            
            center_tab.addTab(self.admin_widget, "系统日志审计")
            
            # 日志信号连接
            self.btn_refresh_logs.clicked.connect(self.refresh_admin_logs)
            self.btn_export_logs.clicked.connect(self.export_admin_logs)
            
        splitter.addWidget(center_tab)

        # 3.3 右栏: 预览与 Markdown 编辑区
        right_widget = QWidget()
        right_widget.setObjectName("RightPanel")
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)

        title_right = QLabel("Wiki 知识编辑器")
        title_right.setStyleSheet("font-size: 11px; font-weight: 600; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;")
        right_layout.addWidget(title_right)

        self.txt_editor = QTextEdit()
        self.txt_editor.setObjectName("MarkdownEditor")
        self.txt_editor.setPlaceholderText("双击左侧目录树中的 Markdown 笔记文件在此处进行预览与二次编辑。")
        right_layout.addWidget(self.txt_editor)

        self.btn_save_note = QPushButton("保存本地笔记修改")
        self.btn_save_note.setObjectName("PrimaryButton")
        self.btn_save_note.setEnabled(False)
        right_layout.addWidget(self.btn_save_note)
        splitter.addWidget(right_widget)

        # 调整三栏比例宽度 (左: 25%, 中: 40%, 右: 35%)
        splitter.setSizes([280, 520, 480])

        # -------------------------------------------------------------
        # 全局信号绑定
        # -------------------------------------------------------------
        self.btn_select_file.clicked.connect(self.select_files_manually)
        self.btn_weave.clicked.connect(self.start_ai_flow)
        self.tree_view.doubleClicked.connect(self.load_selected_note)
        self.btn_save_note.clicked.connect(self.save_note_modifications)

        # 覆写窗口拖拽拖放事件
        self.upload_frame.dragEnterEvent = self.dragEnterEvent
        self.upload_frame.dropEvent = self.dropEvent

        self.current_editing_path = None

    # -------------------------------------------------------------
    # 4. 主控核心交互逻辑
    # -------------------------------------------------------------
    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
            QWidget {
                color: #e3e3e3;
                font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
                font-size: 13px;
            }
            QWidget#CentralWidget, QWidget#RightPanel, QWidget#WorkbenchTab, QWidget#AdminTab {
                background-color: #1e1e1e;
            }
            QSplitter::handle {
                background-color: #2e2e2e;
            }
            QSplitter::handle:horizontal {
                width: 1px;
            }
            QMenu {
                background-color: #262626;
                color: #e3e3e3;
                border: 1px solid #363636;
            }
            QMenu::item:selected {
                background-color: #7f6df2;
                color: #ffffff;
            }
            QComboBox QAbstractItemView {
                background-color: #262626;
                color: #e3e3e3;
                border: 1px solid #363636;
                selection-background-color: #7f6df2;
                selection-color: #ffffff;
            }
            
            /* Sidebar styling */
            QWidget#LeftSidebar {
                background-color: #181818;
                border-right: 1px solid #2e2e2e;
            }
            
            QTreeView {
                background-color: #181818;
                color: #b3b3b3;
                border: none;
                font-size: 13px;
                padding: 5px;
            }
            QTreeView::item {
                height: 28px;
                border-radius: 4px;
                padding-left: 5px;
            }
            QTreeView::item:hover {
                background-color: #242424;
                color: #ffffff;
            }
            QTreeView::item:selected {
                background-color: #262626;
                color: #7f6df2;
                font-weight: bold;
            }
            
            /* TabWidget styling */
            QTabWidget::panel {
                border: 1px solid #2e2e2e;
                background-color: #1e1e1e;
                border-radius: 0px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab {
                background: #181818;
                color: #a3a3a3;
                padding: 10px 18px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border: 1px solid #2e2e2e;
                border-bottom: none;
                margin-right: 4px;
                font-weight: 500;
            }
            QTabBar::tab:hover {
                background: #202020;
                color: #e3e3e3;
            }
            QTabBar::tab:selected {
                background: #1e1e1e;
                color: #ffffff;
                border-top: 2px solid #7f6df2;
                font-weight: bold;
            }
            
            /* Forms, inputs and text fields */
            QLineEdit, QComboBox, QTextEdit, QTableWidget {
                background-color: #262626;
                border: 1px solid #363636;
                border-radius: 5px;
                padding: 6px;
                color: #e3e3e3;
                selection-background-color: #3b2c9e;
                selection-color: #ffffff;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QTableWidget:focus {
                border: 1px solid #7f6df2;
            }
            
            /* Specific text fields */
            QTextEdit#ConsoleLog {
                background-color: #111111;
                color: #a78bfa;
                font-family: 'Consolas', 'Fira Code', monospace;
                font-size: 12px;
                border: 1px solid #2e2e2e;
            }
            
            QTextEdit#MarkdownEditor {
                background-color: #1e1e1e;
                color: #e3e3e3;
                line-height: 1.6;
                font-family: 'Consolas', 'Segoe UI Semibold', monospace;
                font-size: 14px;
                border: 1px solid #2e2e2e;
                padding: 15px;
            }

            /* Buttons styling */
            QPushButton {
                background-color: #2e2e2e;
                color: #e3e3e3;
                border: 1px solid #363636;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #363636;
                border-color: #444444;
            }
            QPushButton:pressed {
                background-color: #202020;
            }
            QPushButton:disabled {
                background-color: #1c1c1c;
                color: #666666;
                border-color: #262626;
            }
            
            /* Accent / Primary buttons */
            QPushButton#PrimaryButton {
                background-color: #7f6df2;
                color: #ffffff;
                border: none;
            }
            QPushButton#PrimaryButton:hover {
                background-color: #6b58e7;
            }
            QPushButton#PrimaryButton:pressed {
                background-color: #5a45db;
            }
            
            /* Drag and drop upload frame */
            QFrame#UploadFrame {
                border: 2px dashed #444444;
                border-radius: 8px;
                background-color: #181818;
                min-height: 120px;
            }
            QFrame#UploadFrame:hover {
                border-color: #7f6df2;
                background-color: #1e1e1e;
            }
            
            /* Table widgets */
            QTableWidget {
                gridline-color: #2e2e2e;
                border: 1px solid #2e2e2e;
            }
            QHeaderView::section {
                background-color: #181818;
                color: #a3a3a3;
                padding: 6px;
                border: 1px solid #2e2e2e;
                font-weight: bold;
            }
            
            /* Scrollbars styling */
            QScrollBar:vertical {
                border: none;
                background: #181818;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #363636;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #444444;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                border: none;
                background: #181818;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #363636;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #444444;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
            
            /* ProgressBar */
            QProgressBar {
                background-color: #181818;
                border: 1px solid #2e2e2e;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #7f6df2;
                border-radius: 3px;
            }
            
            /* QMessageBox styling */
            QMessageBox {
                background-color: #f0f0f0;
            }
            QMessageBox QLabel {
                color: #000000;
                font-size: 13px;
                font-weight: normal;
            }
            QMessageBox QPushButton {
                background-color: #e1e1e1;
                color: #000000;
                border: 1px solid #acacac;
                border-radius: 4px;
                padding: 5px 15px;
                min-width: 70px;
                font-weight: normal;
            }
            QMessageBox QPushButton:hover {
                background-color: #e5f1fb;
                border-color: #0078d7;
            }
            QMessageBox QPushButton:pressed {
                background-color: #cce4f7;
                border-color: #005499;
            }
        """)

    def refresh_vault_tree(self):
        """刷新左侧知识库目录树缓存"""
        fs_router.scan_vault()
        self.dir_model.setRootPath(Config.OBSIDIAN_VAULT_PATH)
        self.tree_view.setRootIndex(self.dir_model.index(Config.OBSIDIAN_VAULT_PATH))

    def select_files_manually(self):
        """弹出文件选择对话框"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择输入多媒体/文档数据", "", 
            "Supported Files (*.mp4 *.mkv *.mp3 *.wav *.pdf *.txt *.md);;All Files (*)"
        )
        if files:
            self.selected_files = files
            self.lbl_selected.setText(f"已选择 {len(files)} 个文件:\n" + "\n".join([os.path.basename(f) for f in files]))
            self.console_log.append(f">> Selected files: {files}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        files = []
        for url in event.mimeData().urls():
            local_path = url.toLocalFile()
            if os.path.exists(local_path):
                files.append(local_path)
        if files:
            self.selected_files = files
            self.lbl_selected.setText(f"已拖入 {len(files)} 个文件:\n" + "\n".join([os.path.basename(f) for f in files]))
            self.console_log.append(f">> Dropped files: {files}")

    def start_ai_flow(self):
        """启动后台 ASR + VLM + LLM 推理异步子线程"""
        if not self.selected_files:
            QMessageBox.warning(self, "操作提示", "请先拖入或选择需要提炼的源视频或文档文件！")
            return

        self.btn_weave.setEnabled(False)
        self.progress_bar.setValue(0)
        
        # 提取参数
        whisper_lang = self.combo_lang.currentText().split(" ")[0].strip()
        custom_key = self.txt_api_key.text().strip()
        
        # 实例化后台线程，开始异步执行
        self.active_worker = AIWorker(
            file_paths=self.selected_files,
            whisper_lang=whisper_lang,
            custom_api_key=custom_key if custom_key else None
        )
        
        # 信号绑定
        self.active_worker.progress_signal.connect(self.update_log_console)
        self.active_worker.finished_signal.connect(self.on_worker_finished)
        
        self.active_worker.start()

    def update_log_console(self, log_msg: str, progress_val: int):
        """实时输出日志到控制台"""
        self.console_log.append(log_msg)
        self.progress_bar.setValue(progress_val)
        # 自动滚动探底
        self.console_log.moveCursor(QTextCursor.MoveOperation.End)

    def on_worker_finished(self, success: bool, msg: str):
        """线程完毕回调"""
        self.btn_weave.setEnabled(True)
        self.selected_files.clear()
        self.lbl_selected.setText("未选择任何文件")
        
        if success:
            QMessageBox.information(self, "织网成功", msg)
            self.refresh_vault_tree()
            if self.user_role == 'admin':
                self.refresh_admin_logs()
        else:
            QMessageBox.critical(self, "运行出错", f"AI 工作流异常中断: {msg}")

    def load_selected_note(self, index):
        """双击左侧目录树中的 markdown 载入编辑器"""
        file_path = self.dir_model.filePath(index)
        if not file_path.endswith('.md'):
            return
        
        self.current_editing_path = file_path
        content = wiki_editor.read_wiki(file_path)
        self.txt_editor.setText(content)
        self.btn_save_note.setEnabled(True)
        self.console_log.append(f">> Loaded note: {os.path.basename(file_path)}")

    def save_note_modifications(self):
        """将编辑器的改动保存入本地文件"""
        if not self.current_editing_path:
            return
        
        content = self.txt_editor.toPlainText()
        success = wiki_editor.write_wiki_atomic(self.current_editing_path, content)
        if success:
            QMessageBox.information(self, "保存成功", f"笔记已成功原子覆写至磁盘！")
            db_manager.add_log("INFO", "GUI", "Manual_Save", f"手动修改并覆写笔记: {os.path.basename(self.current_editing_path)}")
            self.console_log.append(f">> Manual saved note: {os.path.basename(self.current_editing_path)}")
        else:
            QMessageBox.critical(self, "保存失败", "无法原子写入文件，请检查写入权限或文件占用。")

    # -------------------------------------------------------------
    # 5. 管理员专属审计功能
    # -------------------------------------------------------------
    def refresh_admin_logs(self):
        """拉取 SQLite 最新的操作审计日志"""
        if self.user_role != 'admin':
            return
            
        logs = db_manager.get_logs(limit=200)
        self.log_table.setRowCount(len(logs))
        
        for row_idx, log_row in enumerate(logs):
            self.log_table.setItem(row_idx, 0, QTableWidgetItem(str(log_row["timestamp"])))
            self.log_table.setItem(row_idx, 1, QTableWidgetItem(str(log_row["module"])))
            self.log_table.setItem(row_idx, 2, QTableWidgetItem(str(log_row["action"])))
            self.log_table.setItem(row_idx, 3, QTableWidgetItem(str(log_row["detail"])))
            self.log_table.setItem(row_idx, 4, QTableWidgetItem(str(log_row["duration"] or "")))
            
        self.console_log.append(">> Admin logs tables refreshed successfully.")

    def export_admin_logs(self):
        """导出操作审计日志到 TXT 文件"""
        if self.user_role != 'admin':
            return
            
        save_path, _ = QFileDialog.getSaveFileName(self, "保存审计日志", "crucible_audit_logs.txt", "Text Files (*.txt)")
        if not save_path:
            return
            
        try:
            logs = db_manager.get_logs(limit=1000)
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(f"Crucible System Audit Logs - Exported at {datetime.datetime.now()}\n")
                f.write("=" * 80 + "\n\n")
                for log_row in logs:
                    f.write(f"[{log_row['timestamp']}] [{log_row['level']}] [{log_row['module']}] "
                            f"{log_row['action']} - {log_row['detail']} (Duration: {log_row['duration']}s)\n")
            QMessageBox.information(self, "导出成功", f"日志成功导出至:\n{save_path}")
            db_manager.add_log("INFO", "GUI", "Export_Logs", f"管理员导出日志到: {save_path}")
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"无法写入日志文件: {e}")


# =====================================================================
# 4. 应用程序入口
# =====================================================================
def main():
    app = QApplication(sys.argv)
    
    # 1. 弹出登录框
    login = LoginDialog()
    if login.exec() == QDialog.DialogCode.Accepted:
        # 2. 登录通过，启动主窗口
        main_win = MainWindow(username=login.username, role=login.user_role)
        main_win.show()
        sys.exit(app.exec())
    else:
        # 取消登录，直接退出
        sys.exit(0)

if __name__ == '__main__':
    main()
