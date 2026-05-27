# Crucible 桌面客户端打包指南

本项目基于 **PyQt6** 开发，可以通过 **PyInstaller** 方便地打包为 Windows 或 macOS 独立的可执行文件（无 Python 环境亦可直接运行）。

---

## 1. 安装 PyInstaller

在您的 Python 虚拟环境中，运行以下命令安装打包工具：

```bash
pip install pyinstaller
```

---

## 2. 打包步骤 (Windows)

在项目根目录下，执行以下打包命令：

```bash
pyinstaller --noconsole --name="Crucible" --add-data="Crucible/config.py;." --add-data="Crucible/utils;utils" --add-data="Crucible/models;models" Crucible/gui.py
```

### 参数说明：
* `--noconsole` / `-w`：关闭命令行黑窗口，启动时只显示 PyQt6 的 GUI 窗口。
* `--name="Crucible"`：生成的可执行文件名称。
* `--add-data`：打包时包含的依赖文件（Windows 下使用 `;` 分割，macOS/Linux 下使用 `:` 分割）。
* `Crucible/gui.py`：主程序入口点。

---

## 3. 生成输出

执行完打包命令后，会在项目根目录生成以下目录：
1. **`build/`**：打包过程中的临时缓存文件。
2. **`dist/`**：打包后的产物。您可在 `dist/Crucible/` 目录下找到 **`Crucible.exe`**。双击即可直接运行启动。

---

## 4. 离线运行排坑提示

由于本项目集成了 Whisper、Qwen-VL 等深度学习模型：
1. **模型文件过大**：本客户端定位为**轻量级工作台**。在商业/期末部署中，如果客户端独立运行，建议使用 `.env` 配置文件中的 `LLM_API_KEY` 和 `LLM_API_BASE` 配置远端 API。
2. **FFmpeg 环境变量**：在无 Python 环境运行 `Crucible.exe` 前，需确保目标机器上已安装 **FFmpeg** 并将其加入了系统环境变量，否则音视频处理提取阶段将不可用。admiadaa
