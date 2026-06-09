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
    QFileDialog, QHeaderView, QTableWidget, QTableWidgetItem, QFrame,
    QInputDialog, QTextBrowser
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDir, QUrl, QTimer
from PyQt6.QtGui import QFont, QFileSystemModel, QIcon, QTextCursor

# 载入配置及工具类
from Crucible.config import Config
from Crucible.utils.db_manager import db_manager
from Crucible.utils.fs_router import fs_router
from Crucible.utils.wiki_editor import wiki_editor
from Crucible.utils.graph_builder import knowledge_graph_builder
from Crucible.utils.note_analyzer import note_analyzer
from Crucible.utils.processing_workflow import ProcessingOptions, ProcessingWorkflow
from Crucible.utils.source_index import source_index
from Crucible.utils.templates import template_manager

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
                 use_reflection: bool = True, custom_api_key: str = None,
                 asr_engine: str = 'dashscope', provider: str = None,
                 api_base: str = None, llm_model: str = None,
                 vlm_model: str = None, fact_model: str = None):
        super().__init__()
        self.file_paths = file_paths
        self.whisper_lang = whisper_lang
        self.use_reflection = use_reflection
        self.custom_api_key = custom_api_key
        self.asr_engine = asr_engine
        self.provider = provider or Config.LLM_PROVIDER
        self.api_base = api_base
        self.llm_model = llm_model
        self.vlm_model = vlm_model
        self.fact_model = fact_model

    def run(self):
        try:
            options = ProcessingOptions(
                file_paths=self.file_paths,
                whisper_lang=self.whisper_lang,
                asr_engine=self.asr_engine,
                provider=self.provider,
                api_key=self.custom_api_key,
                api_base=self.api_base,
                llm_model=self.llm_model,
                vlm_model=self.vlm_model,
                fact_model=self.fact_model,
            )
            result = ProcessingWorkflow(options, self.progress_signal.emit).run()
            self.finished_signal.emit(
                True,
                f"成功处理 {result.processed_sources} 个源，生成或更新 {result.written_notes} 条笔记。",
            )
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

        tree_actions = QHBoxLayout()
        self.btn_new_folder = QPushButton("新建文件夹")
        self.btn_new_note = QPushButton("新建笔记")
        self.btn_rename_node = QPushButton("重命名")
        tree_actions.addWidget(self.btn_new_folder)
        tree_actions.addWidget(self.btn_new_note)
        tree_actions.addWidget(self.btn_rename_node)
        left_layout.addLayout(tree_actions)

        tree_actions_2 = QHBoxLayout()
        self.btn_open_rules = QPushButton("整理规则")
        self.btn_command_palette = QPushButton("命令")
        self.btn_refresh_tree = QPushButton("刷新")
        tree_actions_2.addWidget(self.btn_open_rules)
        tree_actions_2.addWidget(self.btn_command_palette)
        tree_actions_2.addWidget(self.btn_refresh_tree)
        left_layout.addLayout(tree_actions_2)
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

        # 新增 URL 输入行
        url_layout = QHBoxLayout()
        self.txt_url_input = QLineEdit()
        self.txt_url_input.setPlaceholderText("在此输入或粘贴视频 URL 链接 (如 Bilibili、YouTube)...")
        self.btn_add_url = QPushButton("添加链接")
        self.btn_add_url.setFixedWidth(80)
        url_layout.addWidget(self.txt_url_input)
        url_layout.addWidget(self.btn_add_url)
        workbench_layout.addLayout(url_layout)

        # 文件列表展示
        self.lbl_selected = QLabel("未选择任何文件")
        self.lbl_selected.setStyleSheet("color: #a3a3a3; font-size: 12px; margin-top: 5px;")
        workbench_layout.addWidget(self.lbl_selected)

        # 配置参数区
        config_box = QFormLayout()
        config_box.setVerticalSpacing(8)
        config_box.setHorizontalSpacing(10)

        self.combo_provider = QComboBox()
        self.provider_keys = []
        for provider_key, label in Config.get_provider_options():
            self.provider_keys.append(provider_key)
            self.combo_provider.addItem(label)
        if Config.LLM_PROVIDER in self.provider_keys:
            self.combo_provider.setCurrentIndex(self.provider_keys.index(Config.LLM_PROVIDER))
        config_box.addRow("模型 Provider:", self.combo_provider)

        self.txt_api_base = QLineEdit(Config.LLM_API_BASE)
        self.txt_api_base.setPlaceholderText("OpenAI-compatible API Base")
        config_box.addRow("API Base:", self.txt_api_base)

        self.txt_llm_model = QLineEdit(Config.LLM_MODEL_NAME)
        self.txt_llm_model.setPlaceholderText("知识抽取/笔记合并模型")
        config_box.addRow("LLM 模型:", self.txt_llm_model)

        self.txt_vlm_model = QLineEdit(Config.VLM_MODEL_NAME)
        self.txt_vlm_model.setPlaceholderText("视觉理解模型")
        config_box.addRow("VLM 模型:", self.txt_vlm_model)

        self.txt_fact_model = QLineEdit(Config.FACT_CHECKER_MODEL_NAME)
        self.txt_fact_model.setPlaceholderText("事实核查模型")
        config_box.addRow("核查模型:", self.txt_fact_model)
        
        self.combo_lang = QComboBox()
        self.combo_lang.addItems(["Auto (自动检测)", "zh (中文)", "en (英文)", "ja (日语)"])
        config_box.addRow("ASR 语音语言:", self.combo_lang)

        self.combo_asr_engine = QComboBox()
        self.combo_asr_engine.addItems(["DashScope (百炼实时流式)", "Local Whisper (本地模型)"])
        if not Config.has_valid_api_key():
            self.combo_asr_engine.setCurrentIndex(1)
        config_box.addRow("ASR 识别引擎:", self.combo_asr_engine)

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

        graph_widget = QWidget()
        graph_widget.setObjectName("GraphTab")
        graph_layout = QVBoxLayout(graph_widget)
        graph_layout.setContentsMargins(8, 8, 8, 8)

        graph_title = QLabel("关系图谱")
        graph_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;")
        graph_layout.addWidget(graph_title)

        self.graph_summary = QTextEdit()
        self.graph_summary.setReadOnly(True)
        self.graph_summary.setObjectName("ConsoleLog")
        graph_layout.addWidget(self.graph_summary)

        self.graph_table = QTableWidget()
        self.graph_table.setColumnCount(5)
        self.graph_table.setHorizontalHeaderLabels(["来源", "指向", "关系", "时间戳", "来源路径"])
        self.graph_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        graph_layout.addWidget(self.graph_table)

        self.btn_refresh_graph = QPushButton("刷新关系图谱")
        graph_layout.addWidget(self.btn_refresh_graph)
        center_tab.addTab(graph_widget, "关系图谱")

        search_widget = QWidget()
        search_widget.setObjectName("SearchTab")
        search_layout = QVBoxLayout(search_widget)
        search_layout.setContentsMargins(8, 8, 8, 8)

        search_title = QLabel("本地检索")
        search_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #a3a3a3; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 5px;")
        search_layout.addWidget(search_title)

        search_row = QHBoxLayout()
        self.txt_search_keyword = QLineEdit()
        self.txt_search_keyword.setPlaceholderText("搜索视频片段、来源标题或概念...")
        self.btn_search_index = QPushButton("搜索")
        search_row.addWidget(self.txt_search_keyword)
        search_row.addWidget(self.btn_search_index)
        search_layout.addLayout(search_row)

        self.search_table = QTableWidget()
        self.search_table.setColumnCount(6)
        self.search_table.setHorizontalHeaderLabels(["来源", "时间戳", "片段", "概念", "开始", "来源路径"])
        self.search_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        search_layout.addWidget(self.search_table)
        center_tab.addTab(search_widget, "本地检索")

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

        editor_toolbar = QHBoxLayout()
        self.lbl_save_status = QLabel("未打开笔记")
        self.lbl_save_status.setStyleSheet("color: #a3a3a3; font-size: 12px;")
        self.btn_refresh_preview = QPushButton("刷新预览")
        editor_toolbar.addWidget(self.lbl_save_status)
        editor_toolbar.addStretch()
        editor_toolbar.addWidget(self.btn_refresh_preview)
        right_layout.addLayout(editor_toolbar)

        self.note_tabs = QTabWidget()

        self.txt_editor = QTextEdit()
        self.txt_editor.setObjectName("MarkdownEditor")
        self.txt_editor.setPlaceholderText("双击左侧目录树中的 Markdown 笔记文件在此处进行预览与二次编辑。")
        self.note_tabs.addTab(self.txt_editor, "编辑")

        self.preview_browser = QTextBrowser()
        self.preview_browser.setOpenExternalLinks(False)
        self.preview_browser.setOpenLinks(False)
        self.preview_browser.setObjectName("MarkdownEditor")
        self.note_tabs.addTab(self.preview_browser, "预览")

        self.properties_table = QTableWidget()
        self.properties_table.setColumnCount(2)
        self.properties_table.setHorizontalHeaderLabels(["属性", "值"])
        self.properties_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.note_tabs.addTab(self.properties_table, "属性")

        self.links_table = QTableWidget()
        self.links_table.setColumnCount(3)
        self.links_table.setHorizontalHeaderLabels(["类型", "目标", "路径/时间戳"])
        self.links_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.note_tabs.addTab(self.links_table, "链接")

        right_layout.addWidget(self.note_tabs)

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
        self.preview_refresh_timer = QTimer(self)
        self.preview_refresh_timer.setSingleShot(True)
        self.preview_refresh_timer.setInterval(300)
        self.preview_refresh_timer.timeout.connect(self.refresh_live_note_preview)

        self.btn_select_file.clicked.connect(self.select_files_manually)
        self.btn_weave.clicked.connect(self.start_ai_flow)
        self.tree_view.doubleClicked.connect(self.load_selected_note)
        self.btn_save_note.clicked.connect(self.save_note_modifications)
        self.btn_add_url.clicked.connect(self.add_url_manually)
        self.txt_url_input.returnPressed.connect(self.add_url_manually)
        self.combo_provider.currentIndexChanged.connect(self.on_provider_changed)
        self.btn_new_folder.clicked.connect(self.create_folder_from_tree)
        self.btn_new_note.clicked.connect(self.create_note_from_tree)
        self.btn_rename_node.clicked.connect(self.rename_selected_tree_item)
        self.btn_open_rules.clicked.connect(self.open_organization_rules)
        self.btn_command_palette.clicked.connect(self.open_command_palette)
        self.btn_refresh_tree.clicked.connect(self.refresh_vault_tree)
        self.btn_refresh_graph.clicked.connect(self.refresh_relation_graph)
        self.graph_table.cellDoubleClicked.connect(self.open_graph_edge_source)
        self.btn_search_index.clicked.connect(self.search_knowledge_index)
        self.txt_search_keyword.returnPressed.connect(self.search_knowledge_index)
        self.search_table.cellDoubleClicked.connect(self.open_search_result)
        self.btn_refresh_preview.clicked.connect(self.refresh_note_context)
        self.preview_browser.anchorClicked.connect(self.open_preview_link)
        self.links_table.cellDoubleClicked.connect(self.open_link_table_item)
        self.txt_editor.textChanged.connect(self.on_editor_text_changed)

        # 覆写窗口拖拽拖放事件
        self.upload_frame.dragEnterEvent = self.dragEnterEvent
        self.upload_frame.dropEvent = self.dropEvent

        self.current_editing_path = None
        self.note_dirty = False
        self.update_provider_hint()
        self.refresh_relation_graph()

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
            QWidget#CentralWidget, QWidget#RightPanel, QWidget#WorkbenchTab, QWidget#AdminTab, QWidget#GraphTab, QWidget#SearchTab {
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

    def get_selected_tree_path(self) -> str:
        index = self.tree_view.currentIndex()
        if index.isValid():
            return self.dir_model.filePath(index)
        return Config.OBSIDIAN_VAULT_PATH

    def get_selected_tree_dir(self) -> str:
        selected_path = self.get_selected_tree_path()
        if os.path.isdir(selected_path):
            return selected_path
        return os.path.dirname(selected_path) if selected_path else Config.OBSIDIAN_VAULT_PATH

    def create_folder_from_tree(self):
        """在当前目录下创建文件夹"""
        folder_name, ok = QInputDialog.getText(self, "新建文件夹", "文件夹名称:")
        if not ok or not folder_name.strip():
            return
        try:
            created_path = fs_router.create_folder(self.get_selected_tree_dir(), folder_name)
            self.refresh_vault_tree()
            self.console_log.append(f">> Created folder: {fs_router.get_relative_path(created_path)}")
        except Exception as e:
            QMessageBox.critical(self, "创建失败", str(e))

    def create_note_from_tree(self):
        """在当前目录下创建 Markdown 笔记"""
        note_name, ok = QInputDialog.getText(self, "新建笔记", "笔记名称:")
        if not ok or not note_name.strip():
            return
        try:
            templates = template_manager.list_templates()
            template_name, selected = QInputDialog.getItem(
                self,
                "选择模板",
                "模板:",
                ["空白"] + templates,
                0,
                False,
            )
            if not selected:
                return
            title = os.path.splitext(note_name.strip())[0]
            content = (
                f"---\ntags: [manual-note]\n---\n\n# {title}\n"
                if template_name == "空白"
                else template_manager.render_template(template_name, title)
            )
            created_path = fs_router.create_note(
                self.get_selected_tree_dir(),
                note_name,
                content,
            )
            self.refresh_vault_tree()
            self.open_note_path(created_path)
            self.console_log.append(f">> Created note: {fs_router.get_relative_path(created_path)}")
        except Exception as e:
            QMessageBox.critical(self, "创建失败", str(e))

    def rename_selected_tree_item(self):
        """重命名当前选择的目录或 Markdown 文件"""
        selected_path = self.get_selected_tree_path()
        if not selected_path or os.path.abspath(selected_path) == os.path.abspath(Config.OBSIDIAN_VAULT_PATH):
            QMessageBox.warning(self, "操作提示", "请选择需要重命名的文件或文件夹。")
            return

        confirm = QMessageBox.question(
            self,
            "确认重命名",
            f"重命名会改变 Obsidian 链接引用的目标路径。\n\n确定要重命名 {os.path.basename(selected_path)} 吗？",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        new_name, ok = QInputDialog.getText(self, "重命名", "新名称:", text=os.path.basename(selected_path))
        if not ok or not new_name.strip():
            return
        try:
            new_path = fs_router.rename_path(selected_path, new_name)
            if self.current_editing_path == selected_path:
                self.current_editing_path = new_path
            self.refresh_vault_tree()
            self.console_log.append(f">> Renamed to: {fs_router.get_relative_path(new_path)}")
        except Exception as e:
            QMessageBox.critical(self, "重命名失败", str(e))

    def open_organization_rules(self):
        """打开给 LLM 使用的知识库整理规则文件"""
        rules_path = fs_router.ensure_organization_rules()
        self.open_note_path(rules_path)
        self.refresh_vault_tree()
        self.console_log.append(f">> Loaded organization rules: {os.path.basename(rules_path)}")

    def open_note_path(self, file_path: str, anchor: str = ""):
        """打开 Markdown 文件并刷新预览、属性和链接上下文。"""
        if not file_path or not os.path.exists(file_path):
            return
        self.current_editing_path = file_path
        self.txt_editor.blockSignals(True)
        self.txt_editor.setText(wiki_editor.read_wiki(file_path))
        self.txt_editor.blockSignals(False)
        self.btn_save_note.setEnabled(True)
        self.note_dirty = False
        self.lbl_save_status.setText(f"已打开: {fs_router.get_relative_path(file_path)}")
        self.refresh_note_context()
        if anchor:
            self._focus_text(anchor)

    def refresh_note_context(self):
        """刷新当前笔记的预览、属性、出链、反链和来源时间戳。"""
        content = self.txt_editor.toPlainText()
        self.preview_browser.setHtml(wiki_editor.render_markdown_preview(content))
        self.refresh_properties_table(content)
        self.refresh_links_table()

    def refresh_live_note_preview(self):
        """编辑时轻量刷新预览和 frontmatter，不触发反链/索引扫描。"""
        content = self.txt_editor.toPlainText()
        self.preview_browser.setHtml(wiki_editor.render_markdown_preview(content))
        self.refresh_properties_table(content)

    def refresh_properties_table(self, content: str):
        frontmatter = wiki_editor.read_frontmatter(content)
        self.properties_table.setRowCount(len(frontmatter))
        for row_idx, (key, value) in enumerate(frontmatter.items()):
            self.properties_table.setItem(row_idx, 0, QTableWidgetItem(str(key)))
            self.properties_table.setItem(row_idx, 1, QTableWidgetItem(", ".join(value) if isinstance(value, list) else str(value)))

    def refresh_links_table(self):
        if not self.current_editing_path:
            self.links_table.setRowCount(0)
            return
        analysis = note_analyzer.analyze(self.current_editing_path)
        rows = []
        for item in analysis["outgoing_links"]:
            rows.append(("出链", item["label"], item["raw"]))
        for item in analysis["backlinks"]:
            rows.append(("反链", item["source"], item["path"]))
        for item in analysis["source_mentions"]:
            rows.append(("来源时间戳", item["concept_name"], f"{item['source_note_path']}#{item['timestamp_label']}"))

        self.links_table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, value in enumerate(row):
                self.links_table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

    def mark_note_dirty(self):
        if self.current_editing_path:
            self.note_dirty = True
            self.lbl_save_status.setText("未保存")

    def on_editor_text_changed(self):
        self.mark_note_dirty()
        if self.current_editing_path:
            self.preview_refresh_timer.start()

    def refresh_relation_graph(self):
        """刷新 Markdown 双链关系图谱"""
        graph = knowledge_graph_builder.build_graph()
        self.graph_summary.setText(knowledge_graph_builder.build_summary())
        self.graph_table.setRowCount(len(graph["edges"]))
        for row_idx, edge in enumerate(graph["edges"]):
            self.graph_table.setItem(row_idx, 0, QTableWidgetItem(edge["source"]))
            self.graph_table.setItem(row_idx, 1, QTableWidgetItem(edge["target"]))
            self.graph_table.setItem(row_idx, 2, QTableWidgetItem(edge.get("type", "wiki_link")))
            self.graph_table.setItem(row_idx, 3, QTableWidgetItem(edge.get("timestamp", "")))
            self.graph_table.setItem(row_idx, 4, QTableWidgetItem(edge["source_path"]))
        self.console_log.append(">> Relation graph refreshed.")

    def open_graph_edge_source(self, row: int, column: int):
        """双击关系边时打开来源 Markdown。"""
        item = self.graph_table.item(row, 4)
        if not item:
            return
        source_path = os.path.join(Config.OBSIDIAN_VAULT_PATH, item.text().replace("/", os.sep))
        if not os.path.exists(source_path):
            QMessageBox.warning(self, "打开失败", "来源笔记不存在或已被移动。")
            return
        timestamp = ""
        timestamp_item = self.graph_table.item(row, 3)
        if timestamp_item:
            timestamp = timestamp_item.text()
        self.open_note_path(source_path, timestamp)
        self.console_log.append(f">> Loaded graph source: {os.path.basename(source_path)}")

    def search_knowledge_index(self):
        """搜索本地来源片段索引。"""
        keyword = self.txt_search_keyword.text().strip()
        results = source_index.search(keyword)
        self.search_table.setRowCount(len(results))
        for row_idx, row in enumerate(results):
            self.search_table.setItem(row_idx, 0, QTableWidgetItem(str(row.get("source_name") or "")))
            self.search_table.setItem(row_idx, 1, QTableWidgetItem(str(row.get("timestamp_label") or "")))
            self.search_table.setItem(row_idx, 2, QTableWidgetItem(str(row.get("text") or "")))
            self.search_table.setItem(row_idx, 3, QTableWidgetItem(str(row.get("concepts") or "")))
            self.search_table.setItem(row_idx, 4, QTableWidgetItem(str(row.get("start_time") or 0)))
            self.search_table.setItem(row_idx, 5, QTableWidgetItem(str(row.get("source_note_path") or "")))
        self.console_log.append(f">> Search completed: {len(results)} results.")

    def open_search_result(self, row: int, column: int):
        """双击搜索结果时打开来源页。"""
        item = self.search_table.item(row, 5)
        if not item:
            return
        source_path = os.path.join(Config.OBSIDIAN_VAULT_PATH, item.text().replace("/", os.sep))
        if not os.path.exists(source_path):
            QMessageBox.warning(self, "打开失败", "来源笔记不存在或已被移动。")
            return
        timestamp_item = self.search_table.item(row, 1)
        self.open_note_path(source_path, timestamp_item.text() if timestamp_item else "")
        self.console_log.append(f">> Loaded search source: {os.path.basename(source_path)}")

    def open_preview_link(self, url: QUrl):
        """点击预览中的 Obsidian 双链。"""
        if url.scheme() != "crucible":
            return
        from urllib.parse import unquote

        raw = unquote(url.path().lstrip("/"))
        self.open_wiki_target(raw)

    def open_link_table_item(self, row: int, column: int):
        """双击链接面板条目。"""
        type_item = self.links_table.item(row, 0)
        target_item = self.links_table.item(row, 2)
        if not type_item or not target_item:
            return
        if type_item.text() == "出链":
            self.open_wiki_target(target_item.text())
        else:
            path, anchor = (target_item.text().split("#", 1) + [""])[:2] if "#" in target_item.text() else (target_item.text(), "")
            file_path = os.path.join(Config.OBSIDIAN_VAULT_PATH, path.replace("/", os.sep))
            self.open_note_path(file_path, anchor)

    def open_wiki_target(self, raw_target: str):
        """打开或创建 Obsidian 双链目标。"""
        item = wiki_editor.extract_wiki_link_items(f"[[{raw_target}]]")[0]
        target = item["target"]
        anchor = item["anchor"]
        file_path = None

        if target.endswith(".md") or "/" in target:
            candidate = os.path.join(Config.OBSIDIAN_VAULT_PATH, target.replace("/", os.sep))
            if not candidate.endswith(".md"):
                candidate += ".md"
            file_path = candidate
        else:
            file_path = fs_router.locate_concept_file(target)

        if not file_path:
            file_path = fs_router.resolve_note_path("", target)
        if not os.path.exists(file_path):
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            title = os.path.splitext(os.path.basename(file_path))[0]
            wiki_editor.write_wiki_atomic(file_path, f"---\ntags: [linked-note]\n---\n\n# {title}\n")

        self.open_note_path(file_path, anchor)

    def _focus_text(self, needle: str):
        if not needle:
            return
        cursor = self.txt_editor.document().find(needle)
        if not cursor.isNull():
            self.txt_editor.setTextCursor(cursor)
            self.note_tabs.setCurrentIndex(0)

    def open_command_palette(self):
        """轻量命令面板。"""
        commands = [
            "新建笔记",
            "打开整理规则",
            "刷新关系图谱",
            "搜索",
            "插入当前时间戳链接",
            "打开来源页",
        ]
        command, ok = QInputDialog.getItem(self, "命令面板", "命令:", commands, 0, False)
        if not ok:
            return
        if command == "新建笔记":
            self.create_note_from_tree()
        elif command == "打开整理规则":
            self.open_organization_rules()
        elif command == "刷新关系图谱":
            self.refresh_relation_graph()
        elif command == "搜索":
            self.txt_search_keyword.setFocus()
        elif command == "插入当前时间戳链接":
            link, accepted = QInputDialog.getText(self, "插入时间戳链接", "链接，例如 [[Sources/Demo#00:00:12|00:00:12]]:")
            if accepted and link.strip():
                self.txt_editor.insertPlainText(link.strip())
        elif command == "打开来源页":
            if not self.current_editing_path:
                return
            frontmatter = wiki_editor.read_frontmatter(self.txt_editor.toPlainText())
            sources = frontmatter.get("sources") or []
            if isinstance(sources, str):
                sources = [sources]
            if not sources:
                QMessageBox.information(self, "无来源", "当前笔记没有 sources 属性。")
                return
            source_path = os.path.join(Config.OBSIDIAN_VAULT_PATH, sources[0].replace("/", os.sep))
            self.open_note_path(source_path)

    def update_provider_hint(self):
        provider = self.provider_keys[self.combo_provider.currentIndex()]
        if provider in ("ollama", "lmstudio"):
            self.txt_api_key.setPlaceholderText("本地 OpenAI-compatible 服务通常可留空")
        else:
            self.txt_api_key.setPlaceholderText("填写该 Provider 的 API KEY")

    def on_provider_changed(self):
        """根据 Provider 预设填充默认 API Base 和模型名，保留用户手动编辑能力。"""
        if not hasattr(self, "provider_keys") or not self.provider_keys:
            return
        provider = self.provider_keys[self.combo_provider.currentIndex()]
        preset = Config.get_provider_preset(provider)
        self.txt_api_base.setText(preset["api_base"])
        self.txt_llm_model.setText(preset["model"])
        self.txt_vlm_model.setText(preset.get("vlm_model") or preset["model"])
        self.txt_fact_model.setText(preset["model"])

        if provider in ("ollama", "lmstudio"):
            self.combo_asr_engine.setCurrentIndex(1)
        self.update_provider_hint()

    def select_files_manually(self):
        """弹出文件选择对话框"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择输入多媒体/文档数据", "", 
            "Supported Files (*.mp4 *.mkv *.mp3 *.wav *.pdf *.txt *.md);;All Files (*)"
        )
        if files:
            for file in files:
                if file not in self.selected_files:
                    self.selected_files.append(file)
            self.update_selected_list_display()
            self.console_log.append(f">> Selected files: {files}")

    def add_url_manually(self) -> bool:
        """手动添加输入的在线 URL"""
        url = self.txt_url_input.text().strip()
        if not url:
            return True
            
        # 自动补全协议头：如果包含 "." 且不含空格，且不以 http:// 或 https:// 开头
        if not url.startswith(('http://', 'https://')):
            if (' ' not in url and '.' in url) or url.startswith('www.'):
                url = 'https://' + url
            
        import re
        url_pattern = re.compile(r'^https?://\S+$', re.IGNORECASE)
        if not url_pattern.match(url):
            QMessageBox.warning(self, "输入错误", "输入的不是合法的 HTTP/HTTPS 链接！")
            return False
            
        if url in self.selected_files:
            QMessageBox.information(self, "操作提示", "该链接已经存在于待处理列表中。")
            return True
            
        self.selected_files.append(url)
        self.update_selected_list_display()
        self.txt_url_input.clear()
        self.console_log.append(f">> 已添加在线视频 URL 至待处理列表: {url}")
        return True

    def update_selected_list_display(self):
        """漂亮地更新已选择/解析的文件与链接列表展示"""
        if not self.selected_files:
            self.lbl_selected.setText("未选择任何文件或链接")
            return
            
        display_texts = []
        for item in self.selected_files:
            if item.startswith(('http://', 'https://')):
                display_texts.append(f"🔗 链接: {item}")
            else:
                display_texts.append(f"📄 文件: {os.path.basename(item)}")
                
        self.lbl_selected.setText(f"已选择 {len(self.selected_files)} 个源:\n" + "\n".join(display_texts))

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
            for file in files:
                if file not in self.selected_files:
                    self.selected_files.append(file)
            self.update_selected_list_display()
            self.console_log.append(f">> Dropped files: {files}")

    def start_ai_flow(self):
        """启动后台 ASR + VLM + LLM 推理异步子线程"""
        if self.active_worker and self.active_worker.isRunning():
            QMessageBox.information(self, "任务进行中", "当前 AI 处理任务尚未完成，请等待结束后再启动新任务。")
            return

        # 如果 URL 输入框中存有内容，自动触发添加动作
        if self.txt_url_input.text().strip():
            if not self.add_url_manually():
                return  # 校验失败，直接返回以避免弹出“请拖入文件”的二次提示

        if not self.selected_files:
            QMessageBox.warning(self, "操作提示", "请先拖入或选择需要提炼的源视频或文档文件！")
            return

        self.btn_weave.setEnabled(False)
        self.progress_bar.setValue(0)
        
        # 提取参数
        whisper_lang = self.combo_lang.currentText().split(" ")[0].strip()
        custom_key = self.txt_api_key.text().strip()
        asr_engine = "dashscope" if "DashScope" in self.combo_asr_engine.currentText() else "local"
        provider = self.provider_keys[self.combo_provider.currentIndex()]
        api_base = self.txt_api_base.text().strip()
        llm_model = self.txt_llm_model.text().strip()
        vlm_model = self.txt_vlm_model.text().strip()
        fact_model = self.txt_fact_model.text().strip()
        Config.save_local_settings(
            provider=provider,
            api_base=api_base,
            llm_model=llm_model,
            vlm_model=vlm_model,
            fact_model=fact_model,
            api_key=custom_key or None,
        )
        
        # 实例化后台线程，开始异步执行
        self.active_worker = AIWorker(
            file_paths=list(self.selected_files),
            whisper_lang=whisper_lang,
            custom_api_key=custom_key if custom_key else None,
            asr_engine=asr_engine,
            provider=provider,
            api_base=api_base,
            llm_model=llm_model,
            vlm_model=vlm_model,
            fact_model=fact_model,
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
        self.active_worker = None
        self.selected_files.clear()
        self.lbl_selected.setText("未选择任何文件")
        
        if success:
            QMessageBox.information(self, "织网成功", msg)
            self.refresh_vault_tree()
            self.refresh_relation_graph()
            if self.user_role == 'admin':
                self.refresh_admin_logs()
        else:
            QMessageBox.critical(self, "运行出错", f"AI 工作流异常中断: {msg}")

    def load_selected_note(self, index):
        """双击左侧目录树中的 markdown 载入编辑器"""
        file_path = self.dir_model.filePath(index)
        if not file_path.endswith('.md'):
            return
        self.open_note_path(file_path)
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
            self.note_dirty = False
            self.lbl_save_status.setText("已保存")
            self.refresh_note_context()
        else:
            self.lbl_save_status.setText("保存失败")
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
