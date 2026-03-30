import os
import sys
import json
import subprocess
import requests
import shutil
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                             QScrollArea, QMessageBox, QDialog, QLineEdit, 
                             QFormLayout, QComboBox, QTreeWidget, QTreeWidgetItem)
from PySide6.QtCore import Qt, QThread, Signal

VERSION = "0.0.3"
# Замените на ваши реальные данные GitHub
GITHUB_USER = "PunkStudio"
GITHUB_REPO = "win_help"
SCRIPTS_PATH = "scripts" # Папка в репозитории, где лежат категории со скриптами

UPDATE_URL = f"https://raw.githubusercontent.com/PunkStudio/win_help/main/version.json"
EXE_URL = f"https://github.com/PunkStudio/win_help/releases/latest/download/SysAdminHelper.exe"
API_CONTENTS_URL = f"https://api.github.com/repos/PunkStudio/win_help/contents/"

CONFIG_FILE = "config.json"
SCRIPTS_DIR = "scripts_cache"

class ScriptExecutor(QThread):
    output_signal = Signal(str)
    finished_signal = Signal(int)

    def __init__(self, script_path, script_type, command=None):
        super().__init__()
        self.script_path = script_path
        self.script_type = script_type
        self.command = command

    def run(self):
        try:
            if self.script_type == "powershell":
                if self.command:
                    cmd = ["powershell", "-Command", self.command]
                else:
                    cmd = ["powershell", "-File", self.script_path]
            elif self.script_type == "cmd":
                if self.command:
                    cmd = ["cmd", "/c", self.command]
                else:
                    cmd = ["cmd", "/c", self.script_path]
            elif self.script_type == "python":
                cmd = ["python", self.script_path]
            else:
                self.output_signal.emit(f"Unknown script type: {self.script_type}")
                self.finished_signal.emit(1)
                return

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='cp866',  # Используем кодировку для Windows-консоли
                errors='ignore',   # Игнорируем ошибки декодирования
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            for line in process.stdout:
                self.output_signal.emit(line)
            
            process.wait()
            self.finished_signal.emit(process.returncode)
        except Exception as e:
            self.output_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(1)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SysAdmin Helper v{VERSION}")
        self.resize(800, 600)
        
        if not os.path.exists(SCRIPTS_DIR):
            os.makedirs(SCRIPTS_DIR)
            
        self.load_config()
        self.init_ui()
        self.check_for_updates()

    def check_for_updates(self):
        try:
            response = requests.get(UPDATE_URL, timeout=5)
            if response.status_code == 200:
                remote_config = response.json()
                remote_version = remote_config.get("version", VERSION)
                if remote_version > VERSION:
                    reply = QMessageBox.question(
                        self, 
                        "Update Available", 
                        f"A new version {remote_version} is available. Update now?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    if reply == QMessageBox.StandardButton.Yes:
                        self.download_and_apply_update()
        except Exception as e:
            self.log(f"Update check failed: {str(e)}")

    def download_and_apply_update(self):
        try:
            self.log("Downloading update...")
            response = requests.get(EXE_URL, stream=True)
            response.raise_for_status()
            
            new_exe_path = "SysAdminHelper_new.exe"
            with open(new_exe_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            self.log("Update downloaded. Restarting...")
            self.apply_update_and_restart(new_exe_path)
        except Exception as e:
            QMessageBox.critical(self, "Update Error", f"Failed to download update: {str(e)}")

    def apply_update_and_restart(self, new_exe_path):
        current_exe = sys.executable
        if not getattr(sys, 'frozen', False):
            self.log("Update only works for EXE version.")
            return

        # Create a temporary batch script to swap the files
        batch_script = "updater.bat"
        with open(batch_script, "w") as f:
            f.write(f"""@echo off
timeout /t 2 /nobreak > nul
del "{current_exe}"
move "{new_exe_path}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
""")
        
        subprocess.Popen(["cmd", "/c", batch_script], creationflags=subprocess.CREATE_NO_WINDOW)
        sys.exit(0)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        else:
            self.config = {"scripts": []}

    def save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left side: Dynamic Script tree
        left_widget = QWidget()
        self.left_layout = QVBoxLayout(left_widget)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Scripts Library (GitHub)")
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        self.refresh_btn = QPushButton("Refresh Scripts from GitHub")
        self.refresh_btn.clicked.connect(self.fetch_scripts_from_github)
        
        self.left_layout.addWidget(self.tree)
        self.left_layout.addWidget(self.refresh_btn)

        # Right side: Logs
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: 'Consolas';")
        
        clear_logs_btn = QPushButton("Clear Logs")
        clear_logs_btn.clicked.connect(self.log_view.clear)
        
        right_layout.addWidget(QLabel("Logs:"))
        right_layout.addWidget(self.log_view)
        right_layout.addWidget(clear_logs_btn)

        main_layout.addWidget(left_widget, 1)
        main_layout.addWidget(right_widget, 2)

        self.fetch_scripts_from_github()

    def fetch_scripts_from_github(self):
        self.tree.clear()
        self.log("Fetching script structure from GitHub...")
        
        try:
            # Get the list of categories (folders) in SCRIPTS_PATH
            response = requests.get(API_CONTENTS_URL + SCRIPTS_PATH)
            if response.status_code != 200:
                self.log(f"Error: GitHub API returned {response.status_code}")
                return

            items = response.json()
            for item in items:
                if item["type"] == "dir":
                    category_name = item["name"]
                    category_item = QTreeWidgetItem(self.tree)
                    category_item.setText(0, category_name)
                    category_item.setData(0, Qt.UserRole, "category")
                    
                    # Fetch scripts inside the category
                    self.fetch_category_scripts(item["path"], category_item)
            
            self.tree.expandAll()
            self.log("Script library updated successfully.")
        except Exception as e:
            self.log(f"Error fetching scripts: {str(e)}")

    def fetch_category_scripts(self, path, parent_item):
        try:
            response = requests.get(API_CONTENTS_URL + path)
            if response.status_code != 200:
                return

            items = response.json()
            for item in items:
                if item["type"] == "file":
                    # Only include scripts
                    ext = os.path.splitext(item["name"])[1].lower()
                    if ext in [".ps1", ".bat", ".cmd", ".py"]:
                        script_item = QTreeWidgetItem(parent_item)
                        script_item.setText(0, item["name"])
                        
                        # Store script info in item's UserRole
                        script_type = "powershell" if ext == ".ps1" else "cmd" if ext in [".bat", ".cmd"] else "python"
                        script_data = {
                            "name": item["name"],
                            "url": item["download_url"],
                            "type": script_type,
                            "path": item["path"]
                        }
                        script_item.setData(0, Qt.UserRole, script_data)
        except Exception as e:
            self.log(f"Error fetching scripts for category: {str(e)}")

    def on_item_double_clicked(self, item, column):
        data = item.data(0, Qt.UserRole)
        if isinstance(data, dict):
            self.run_script(data)

    def log(self, text):
        self.log_view.append(text)

    def run_script(self, script_data):
        self.log(f"--- Starting: {script_data['name']} ---")
        
        # Unique name for caching
        safe_path = script_data["path"].replace("/", "_")
        script_path = os.path.join(SCRIPTS_DIR, safe_path)
        
        try:
            self.log(f"Downloading from GitHub: {script_data['path']}...")
            response = requests.get(script_data["url"])
            response.raise_for_status()
            with open(script_path, "wb") as f:
                f.write(response.content)
            self.log("Download complete.")
        except Exception as e:
            self.log(f"Download failed: {str(e)}")
            if not os.path.exists(script_path):
                return

        self.executor = ScriptExecutor(script_path, script_data["type"])
        self.executor.output_signal.connect(self.log)
        self.executor.finished_signal.connect(lambda code: self.log(f"--- Finished with exit code: {code} ---\n"))
        self.executor.start()

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
