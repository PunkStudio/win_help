import os
import sys
import json
import subprocess
import requests
import shutil
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                             QScrollArea, QMessageBox, QDialog, QLineEdit, 
                             QFormLayout, QComboBox)
from PySide6.QtCore import Qt, QThread, Signal

VERSION = "1.0.0"
# Замените на ваши реальные ссылки на GitHub
UPDATE_URL = "https://github.com/PunkStudio/main/version.json"
EXE_URL = "https://github.com/PunkStudio/main/releases/latest/download/SysAdminHelper.exe"

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
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            for line in process.stdout:
                self.output_signal.emit(line)
            
            process.wait()
            self.finished_signal.emit(process.returncode)
        except Exception as e:
            self.output_signal.emit(f"Error: {str(e)}")
            self.finished_signal.emit(1)

class ScriptEditorDialog(QDialog):
    def __init__(self, parent=None, script_data=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Script")
        self.layout = QFormLayout(self)
        
        self.name_edit = QLineEdit(script_data.get("name", "") if script_data else "")
        self.desc_edit = QLineEdit(script_data.get("description", "") if script_data else "")
        self.url_edit = QLineEdit(script_data.get("url", "") if script_data else "")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["powershell", "cmd", "python"])
        if script_data:
            index = self.type_combo.findText(script_data.get("type", "powershell"))
            self.type_combo.setCurrentIndex(index)
        
        self.command_edit = QLineEdit(script_data.get("command", "") if script_data else "")

        self.layout.addRow("Name:", self.name_edit)
        self.layout.addRow("Description:", self.desc_edit)
        self.layout.addRow("GitHub URL:", self.url_edit)
        self.layout.addRow("Type:", self.type_combo)
        self.layout.addRow("Command (Optional):", self.command_edit)

        self.buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.buttons.addWidget(self.save_btn)
        self.buttons.addWidget(self.cancel_btn)
        self.layout.addRow(self.buttons)

    def get_data(self):
        return {
            "name": self.name_edit.text(),
            "description": self.desc_edit.text(),
            "url": self.url_edit.text(),
            "type": self.type_combo.currentText(),
            "command": self.command_edit.text()
        }

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

        # Left side: Script list
        left_widget = QWidget()
        self.left_layout = QVBoxLayout(left_widget)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.script_list_widget = QWidget()
        self.script_list_layout = QVBoxLayout(self.script_list_widget)
        self.scroll_area.setWidget(self.script_list_widget)
        
        self.add_script_btn = QPushButton("Add New Script")
        self.add_script_btn.clicked.connect(self.add_script)
        
        self.left_layout.addWidget(QLabel("Available Scripts:"))
        self.left_layout.addWidget(self.scroll_area)
        self.left_layout.addWidget(self.add_script_btn)

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

        self.refresh_script_list()

    def refresh_script_list(self):
        # Clear existing buttons
        while self.script_list_layout.count():
            item = self.script_list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i, script in enumerate(self.config["scripts"]):
            script_container = QWidget()
            script_layout = QHBoxLayout(script_container)
            
            run_btn = QPushButton(script["name"])
            run_btn.setToolTip(script["description"])
            run_btn.clicked.connect(lambda checked=False, s=script: self.run_script(s))
            
            edit_btn = QPushButton("Edit")
            edit_btn.setFixedWidth(50)
            edit_btn.clicked.connect(lambda checked=False, idx=i: self.edit_script(idx))
            
            del_btn = QPushButton("X")
            del_btn.setFixedWidth(30)
            del_btn.setStyleSheet("background-color: #d9534f; color: white;")
            del_btn.clicked.connect(lambda checked=False, idx=i: self.delete_script(idx))

            script_layout.addWidget(run_btn)
            script_layout.addWidget(edit_btn)
            script_layout.addWidget(del_btn)
            self.script_list_layout.addWidget(script_container)
        
        self.script_list_layout.addStretch()

    def log(self, text):
        self.log_view.append(text)

    def run_script(self, script_data):
        self.log(f"--- Starting: {script_data['name']} ---")
        
        script_path = os.path.join(SCRIPTS_DIR, f"{script_data.get('id', 'temp')}_{os.path.basename(script_data['url'])}")
        
        # Download if needed
        if script_data["url"]:
            try:
                self.log(f"Downloading from {script_data['url']}...")
                response = requests.get(script_data["url"])
                response.raise_for_status()
                with open(script_path, "wb") as f:
                    f.write(response.content)
                self.log("Download complete.")
            except Exception as e:
                self.log(f"Download failed: {str(e)}")
                if not os.path.exists(script_path) and not script_data.get("command"):
                    return

        self.executor = ScriptExecutor(script_path, script_data["type"], script_data.get("command"))
        self.executor.output_signal.connect(self.log)
        self.executor.finished_signal.connect(lambda code: self.log(f"--- Finished with exit code: {code} ---\n"))
        self.executor.start()

    def add_script(self):
        dialog = ScriptEditorDialog(self, {})
        if dialog.exec():
            new_script = dialog.get_data()
            new_script["id"] = str(hash(new_script["name"]))
            self.config["scripts"].append(new_script)
            self.save_config()
            self.refresh_script_list()

    def edit_script(self, index):
        dialog = ScriptEditorDialog(self, self.config["scripts"][index])
        if dialog.exec():
            self.config["scripts"][index] = dialog.get_data()
            self.save_config()
            self.refresh_script_list()

    def delete_script(self, index):
        if QMessageBox.question(self, "Delete", "Are you sure?") == QMessageBox.StandardButton.Yes:
            self.config["scripts"].pop(index)
            self.save_config()
            self.refresh_script_list()

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
