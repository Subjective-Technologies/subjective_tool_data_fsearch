#!/usr/bin/env python3

import sys
import sqlite3
import time  # For measuring execution time
import json  # For parsing global.config
import subprocess  # For running external commands
import shutil
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout,
    QHBoxLayout, QTableWidget, QTableWidgetItem, QComboBox, QDateEdit, QMessageBox,
    QCheckBox, QSizePolicy, QFileDialog, QAction, QMenu, QTextEdit, QProgressBar,
    QGroupBox, QGridLayout
)
from PyQt5.QtCore import Qt, QDate, QSize, QPoint, QUrl, QMimeData, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QFont, QTextOption, QCursor
from PyQt5.QtSvg import QSvgRenderer
import os  # For path operations
import configparser  # For parsing rclone.config

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from com_subjective_tools.window_chrome import get_subjective_tool_icon, install_subjective_window_chrome

# Embedded SVG Icon (Neon Yellow and Pink File Search Icon)
SVG_ICON = """
<svg width="256" height="256" viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg">
  <!-- Background Circle -->
  <circle cx="128" cy="128" r="120" fill="#1a1a1a" stroke="#ff69b4" stroke-width="8"/>
  
  <!-- File Icon -->
  <rect x="76" y="80" width="80" height="100" fill="#ffffff" rx="8" ry="8" stroke="#ffff00" stroke-width="4"/>
  <polyline points="76,80 156,80 156,160" fill="none" stroke="#ffff00" stroke-width="4"/>
  
  <!-- Magnifying Glass -->
  <circle cx="176" cy="176" r="32" fill="none" stroke="#ffff00" stroke-width="8"/>
  <line x1="200" y1="200" x2="240" y2="240" stroke="#ff69b4" stroke-width="8" stroke-linecap="round"/>
  
  <!-- Glow Effects -->
  <circle cx="176" cy="176" r="40" fill="none" stroke="rgba(255, 105, 180, 0.3)" stroke-width="16" filter="url(#glow)"/>
  
  <!-- Filters for Glow -->
  <defs>
    <filter id="glow">
      <feGaussianBlur stdDeviation="10" result="coloredBlur"/>
      <feMerge>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="coloredBlur"/>
        <feMergeNode in="coloredBlur"/>
      </feMerge>
    </filter>
  </defs>
</svg>
"""

# Embedded SVG Icon for Rclone Config Manager
SVG_RCLONE_TOOL_ICON = """
<svg width="128" height="128" viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
  <rect x="8" y="12" width="112" height="84" rx="10" fill="#1B1B1B" stroke="#3B82F6" stroke-width="4"/>
  <rect x="20" y="28" width="88" height="14" rx="6" fill="#2A2A2A"/>
  <rect x="20" y="50" width="88" height="14" rx="6" fill="#2A2A2A"/>
  <rect x="20" y="72" width="60" height="12" rx="6" fill="#2A2A2A"/>
  <circle cx="96" cy="78" r="16" fill="#3B82F6"/>
  <path d="M90 78h12" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round"/>
  <path d="M96 72v12" stroke="#FFFFFF" stroke-width="4" stroke-linecap="round"/>
  <rect x="22" y="102" width="84" height="12" rx="6" fill="#3A3A3A"/>
</svg>
"""

def _first_existing_path(candidates, fallback):
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return fallback


def resolve_default_paths():
    if os.name == "nt":
        root_candidates = [
            r"C:\brainboost",
            os.path.join(os.path.expanduser("~"), "brainboost"),
        ]
    else:
        root_candidates = [
            "/brainboost",
            os.path.expanduser("~/brainboost"),
        ]

    root_fallback = root_candidates[0]
    root_dir = _first_existing_path(root_candidates, root_fallback)

    data_candidates = [
        os.path.join(root_dir, "brainboost_data"),
        r"C:\brainboost\brainboost_data" if os.name == "nt" else None,
    ]
    data_fallback = data_candidates[0]
    data_dir = _first_existing_path(data_candidates, data_fallback)

    return {
        "rclone_config_path": os.path.join(root_dir, "brainboost_server", "server_rclone.conf"),
        "search_index_script_path": os.path.join(
            data_dir, "data_source", "brainboost_data_source_rclone", "rclone_list_files.py"
        ),
        "db_path": os.path.join(
            data_dir, "data_source", "brainboost_data_source_rclone", "search_rclone_index_db.sqlite"
        ),
        "drives_dir": os.path.join(data_dir, "data_storage", "storage_clouds"),
    }


def resolve_rclone_executable(config_value=None):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidates = []
    env_path = os.environ.get("RCLONE_PATH") or os.environ.get("RCLONE_EXE")
    if env_path:
        candidates.append(env_path)
    if config_value:
        candidates.append(str(config_value))

    for candidate in candidates:
        expanded = os.path.expandvars(os.path.expanduser(candidate))
        if not os.path.isabs(expanded):
            expanded = os.path.abspath(os.path.join(project_root, expanded))
        if os.path.isfile(expanded):
            return expanded

    which_path = shutil.which("rclone")
    if which_path:
        return which_path

    return None


def read_subjective_conf_value(key: str):
    env_value = os.environ.get(key)
    if env_value is not None and str(env_value).strip():
        return str(env_value).strip()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    conf_path = os.path.join(project_root, "subjective.conf")
    if not os.path.isfile(conf_path):
        return None
    try:
        with open(conf_path, "r", encoding="utf-8") as conf_file:
            for line in conf_file:
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                k, v = stripped.split("=", 1)
                if k.strip() == key:
                    return v.strip()
    except Exception:
        return None
    return None


def read_last_passed_remotes():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    userdata_path = read_subjective_conf_value("USERDATA_PATH") or "com_subjective_userdata"
    userdata_path = os.path.expandvars(os.path.expanduser(str(userdata_path)))
    if not os.path.isabs(userdata_path):
        userdata_path = os.path.abspath(os.path.join(project_root, userdata_path))
    userdata_path = os.path.normpath(userdata_path)
    results_path = os.path.join(userdata_path, "com_subjective_rclone", "last_passed_remotes.json")
    if not os.path.isfile(results_path):
        return None
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        remotes = payload.get("passed")
        config_path = payload.get("config_path")
        if isinstance(remotes, list):
            return remotes, config_path
    except Exception:
        return None
    return None


def passed_remotes_file_path():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    userdata_path = read_subjective_conf_value("USERDATA_PATH") or "com_subjective_userdata"
    userdata_path = os.path.expandvars(os.path.expanduser(str(userdata_path)))
    if not os.path.isabs(userdata_path):
        userdata_path = os.path.abspath(os.path.join(project_root, userdata_path))
    userdata_path = os.path.normpath(userdata_path)
    return os.path.join(userdata_path, "com_subjective_rclone", "last_passed_remotes.json")


DEFAULT_PATHS = resolve_default_paths()
PREFERRED_RCLONE_CONFIG_PATH = r"C:\brainboost\brainboost_computer\brainboost_server\server_rclone.conf"

# Path to global.config
GLOBAL_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "global.config")


class ScriptRunner(QThread):
    """
    Worker thread to execute external scripts asynchronously.
    Emits signals to update the UI in real-time.
    """
    output_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)  # Emit return code

    def __init__(self, script_path, python_exe, args=None, env=None):
        super().__init__()
        self.script_path = script_path
        self.python_exe = python_exe
        self.args = args or []
        self.env = env

    def run(self):
        try:
            process = subprocess.Popen(
                [self.python_exe, self.script_path, *self.args],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self.env,
            )

            # Read stdout
            for line in iter(process.stdout.readline, ''):
                if line:
                    self.output_signal.emit(line.strip())
            process.stdout.close()

            # Read stderr
            stderr = process.stderr.read()
            if stderr:
                self.error_signal.emit(stderr.strip())
            process.stderr.close()

            return_code = process.wait()
            self.finished_signal.emit(return_code)
        except Exception as e:
            self.error_signal.emit(str(e))
            self.finished_signal.emit(-1)


class FilterLoader(QThread):
    """
    Worker thread to load filter values from the database without blocking the UI.
    """
    loaded_signal = pyqtSignal(list, list)
    error_signal = pyqtSignal(str)

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path

    def run(self):
        if not self.db_path or not os.path.exists(self.db_path):
            self.error_signal.emit(f"Database not found at: {self.db_path}")
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Ensure indexes exist to speed up DISTINCT queries.
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_drive ON files(drive)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_file_type ON files(file_type)")
            conn.commit()

            cursor.execute(
                "SELECT DISTINCT drive FROM files "
                "WHERE drive IS NOT NULL AND drive <> '' "
                "ORDER BY drive"
            )
            drives = [row[0] for row in cursor.fetchall()]

            cursor.execute(
                "SELECT DISTINCT file_type FROM files "
                "WHERE file_type IS NOT NULL AND file_type <> '' "
                "ORDER BY file_type LIMIT 1000"
            )
            file_types = [row[0] for row in cursor.fetchall()]

            conn.close()
            self.loaded_signal.emit(drives, file_types)
        except Exception as e:
            self.error_signal.emit(str(e))


class FileSearchApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BrainBoost File Search")
        self.resize(1200, 800)  # Increased size for better layout

        # Load config overrides (if any)
        config = self.load_global_config()

        # Initialize paths with OS-aware defaults
        preferred_path = PREFERRED_RCLONE_CONFIG_PATH if os.path.exists(PREFERRED_RCLONE_CONFIG_PATH) else None
        self.rclone_config_path = config.get(
            "rclone_config_path",
            preferred_path or DEFAULT_PATHS["rclone_config_path"],
        )
        self.search_index_script_path = config.get(
            "search_index_script_path", DEFAULT_PATHS["search_index_script_path"]
        )
        self.db_path = config.get("db_path", DEFAULT_PATHS["db_path"])
        self.drives_dir = config.get("drives_dir", DEFAULT_PATHS["drives_dir"])
        self.rclone_path = resolve_rclone_executable(config.get("rclone_path"))
        if not self.rclone_path:
            conf_rclone_path = read_subjective_conf_value("RCLONE_PATH")
            self.rclone_path = resolve_rclone_executable(conf_rclone_path)
        self.rclone_tool_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "subjective_tool_rclone_config_manager",
                "subjective_tool_rclone_config_manager.py",
            )
        )

        # Filter loading state
        self.filter_loader = None
        self._filter_loading = False
        self._filters_loaded = False

        print("Initializing UI...")
        self.initUI()
        self.center_window()
        print("UI initialized successfully.")

        # **Set Focus on the Name Text Field After UI Initialization Using QTimer**
        QTimer.singleShot(0, self.name_input.setFocus)

    def load_global_config(self):
        """Read global.config file to get configuration settings (if present)."""
        print("Reading global.config...")
        if not os.path.exists(GLOBAL_CONFIG_PATH):
            print(f"global.config not found at {GLOBAL_CONFIG_PATH}. Using defaults.")
            return {}

        try:
            with open(GLOBAL_CONFIG_PATH, 'r') as config_file:
                config_data = json.load(config_file)
                if not isinstance(config_data, dict):
                    print("global.config contents are not a JSON object. Using defaults.")
                    return {}
                return config_data
        except json.JSONDecodeError as e:
            print(f"Error parsing global.config: {e}. Using defaults.")
            return {}
        except Exception as e:
            print(f"Unexpected error reading global.config: {e}. Using defaults.")
            return {}

    def initUI(self):
        # Set the window icon from the embedded SVG
        self.set_window_icon()

        # Apply dark theme styling consistent with other QT UIs
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #121212;
                color: #EAEAEA;
            }
            QLabel {
                color: #EAEAEA;
            }
            QGroupBox {
                background-color: #1E1E1E;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
                margin-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                font-weight: bold;
            }
            QLineEdit, QComboBox, QDateEdit, QTextEdit {
                background-color: #1E1E1E;
                color: #EAEAEA;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                padding: 6px;
            }
            QLineEdit::placeholder {
                color: #9A9A9A;
            }
            QComboBox::drop-down {
                border-left: 1px solid #3A3A3A;
            }
            QComboBox QAbstractItemView {
                background-color: #1E1E1E;
                color: #EAEAEA;
                selection-background-color: #2A5EA6;
            }
            QPushButton {
                background-color: #242424;
                color: #EAEAEA;
                border: 1px solid #3A3A3A;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2E2E2E;
            }
            QPushButton:pressed {
                background-color: #1F1F1F;
            }
            QTableWidget {
                background-color: #141414;
                gridline-color: #2A2A2A;
                border: 1px solid #2A2A2A;
            }
            QHeaderView::section {
                background-color: #1C1C1C;
                color: #EAEAEA;
                padding: 6px;
                border: 1px solid #2A2A2A;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #2A5EA6;
                color: #FFFFFF;
            }
            QMenuBar, QMenu {
                background-color: #1A1A1A;
                color: #EAEAEA;
            }
            QMenu::item:selected {
                background-color: #2A5EA6;
            }
            QProgressBar {
                background-color: #1E1E1E;
                border: 1px solid #3A3A3A;
                color: #EAEAEA;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2A5EA6;
            }
            QStatusBar {
                background-color: #1A1A1A;
                color: #CFCFCF;
            }
            QScrollBar:vertical {
                background: #1A1A1A;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #3A3A3A;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        # Create central widget and main layout
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        self.setFont(QFont("Segoe UI", 10))

        # Header row with title and icon
        header_layout = QHBoxLayout()
        title_label = QLabel("File Search")
        title_label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        icon_label = QLabel()
        icon_pixmap = self.render_svg_icon()
        icon_label.setPixmap(icon_pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setFixedSize(36, 36)
        header_layout.addWidget(icon_label)
        main_layout.addLayout(header_layout)

        # Search row
        search_layout = QHBoxLayout()
        name_label = QLabel("Name")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter part or full file name")
        self.name_input.setMinimumHeight(32)
        self.name_input.returnPressed.connect(self.perform_search)
        self.search_button = QPushButton("Search")
        self.search_button.setMinimumWidth(120)
        self.search_button.clicked.connect(self.perform_search)
        search_layout.addWidget(name_label)
        search_layout.addWidget(self.name_input, 1)
        search_layout.addWidget(self.search_button)
        main_layout.addLayout(search_layout)

        # Filters group
        filters_group = QGroupBox("Filters")
        filters_layout = QGridLayout()
        filters_layout.setHorizontalSpacing(12)
        filters_layout.setVerticalSpacing(8)
        filters_layout.setColumnStretch(1, 1)
        filters_layout.setColumnStretch(3, 1)

        size_label = QLabel("Size > (bytes)")
        self.size_input = QLineEdit()
        self.size_input.setPlaceholderText("Enter minimum size")
        self.size_input.setMinimumHeight(28)

        drive_label = QLabel("Drive")
        self.drive_combo = QComboBox()
        self.drive_combo.addItem("Loading...")
        self.drive_combo.setEnabled(False)

        self.date_checkbox = QCheckBox("Modified after")
        self.date_checkbox.setChecked(False)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setEnabled(False)
        self.date_checkbox.stateChanged.connect(self.toggle_date_filter)

        file_type_label = QLabel("File Type")
        self.file_type_combo = QComboBox()
        self.file_type_combo.addItem("Loading...")
        self.file_type_combo.setEnabled(False)

        filters_layout.addWidget(size_label, 0, 0)
        filters_layout.addWidget(self.size_input, 0, 1)
        filters_layout.addWidget(drive_label, 0, 2)
        filters_layout.addWidget(self.drive_combo, 0, 3)
        filters_layout.addWidget(self.date_checkbox, 1, 0)
        filters_layout.addWidget(self.date_edit, 1, 1)
        filters_layout.addWidget(file_type_label, 1, 2)
        filters_layout.addWidget(self.file_type_combo, 1, 3)

        filters_group.setLayout(filters_layout)
        main_layout.addWidget(filters_group)

        # Action buttons row
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.clear_button = QPushButton("Clear Filters")
        self.clear_button.setMinimumWidth(140)
        self.clear_button.clicked.connect(self.clear_filters)
        self.update_index_button = QPushButton("Update Index")
        self.update_index_button.setMinimumWidth(140)
        self.update_index_button.clicked.connect(self.update_index)
        self.rclone_tool_button = QPushButton("Rclone Manager")
        self.rclone_tool_button.setMinimumWidth(160)
        self.rclone_tool_button.setIcon(self._svg_to_icon(SVG_RCLONE_TOOL_ICON, QSize(18, 18)))
        self.rclone_tool_button.clicked.connect(self.launch_rclone_manager)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.update_index_button)
        button_layout.addWidget(self.rclone_tool_button)
        main_layout.addLayout(button_layout)

        # Results Table
        self.results_table = QTableWidget()
        # Update column count and headers by replacing 'Full Path' with 'File Name'
        self.results_table.setColumnCount(5)  # Reduced by hiding 'ID'
        # New order: ["File Name", "Drive", "Size (bytes)", "File Type", "Modified Date"]
        self.results_table.setHorizontalHeaderLabels(["File Name", "Drive", "Size (bytes)", "File Type", "Modified Date"])
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setAlternatingRowColors(True)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setSortingEnabled(True)  # Enable sorting
        self.results_table.setWordWrap(True)  # Enable word wrap

        # Set a fixed row height to accommodate two lines of text
        font_metrics = self.results_table.fontMetrics()
        line_height = font_metrics.lineSpacing()
        max_height = line_height * 2 + 10  # Two lines plus padding
        self.results_table.verticalHeader().setDefaultSectionSize(max_height)

        # Disable automatic resizing based on contents
        # self.results_table.resizeColumnsToContents()  # Removed to prevent changing column widths on data load

        # Enable custom context menu
        self.results_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results_table.customContextMenuRequested.connect(self.open_context_menu)

        # Connect double-click to show folder
        self.results_table.cellDoubleClicked.connect(self.show_folder)

        main_layout.addWidget(self.results_table)

        # **New: Text Area for Update Index Output**
        self.update_output_text = QTextEdit()
        self.update_output_text.setReadOnly(True)
        self.update_output_text.setStyleSheet(
            "background-color: #0B0B0B; color: #9FE870; border: 1px solid #2A2A2A;"
        )
        self.update_output_text.setFont(QFont("Consolas", 9))  # Monospaced font for better readability
        self.update_output_text.hide()  # Initially hidden
        main_layout.addWidget(self.update_output_text)
        # **End of New Section**

        # **New: Progress Bar for Database Queries**
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)  # Indeterminate
        self.progress_bar.setVisible(False)  # Initially hidden
        main_layout.addWidget(self.progress_bar)
        # **End of New Section**

        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # Initialize status bar
        self.init_status_bar()

        # Initialize menu
        self.init_menu()

        # Adjust column widths initially
        self.adjust_column_widths()

    def center_window(self):
        """Center the window on the screen."""
        frame_gm = self.frameGeometry()
        screen = QApplication.desktop().screenNumber(QApplication.desktop().cursor().pos())
        center_point = QApplication.desktop().screenGeometry(screen).center()
        frame_gm.moveCenter(center_point)
        self.move(frame_gm.topLeft())
        print("Window centered on the screen.")

    def init_status_bar(self):
        """Initialize the status bar to display the rclone config path and drives_dir."""
        self.update_status_bar()
        print(
            f"Status bar initialized with rclone.config path: {self.rclone_config_path}, "
            f"Mount Root: {self.drives_dir}, DB: {self.db_path}"
        )

    def update_status_bar(self):
        self.statusBar().showMessage(
            f"rclone.config path: {self.rclone_config_path} | Mount Root: {self.drives_dir} | DB: {self.db_path}"
        )

    def init_menu(self):
        """Initialize the menu bar with options to change the rclone config path and mount root."""
        menubar = self.menuBar()
        settings_menu = menubar.addMenu("Settings")

        # Action to change rclone config path
        change_config_action = QAction("Change rclone.config Path", self)
        change_config_action.setShortcut("Ctrl+O")
        change_config_action.setStatusTip("Change the path to the rclone.config file")
        change_config_action.triggered.connect(self.change_rclone_config_path)
        settings_menu.addAction(change_config_action)

        # Action to change mount root directory
        change_mount_root_action = QAction("Change Mount Root Directory", self)
        change_mount_root_action.setShortcut("Ctrl+M")
        change_mount_root_action.setStatusTip("Change the root directory for mounting drives")
        change_mount_root_action.triggered.connect(self.change_mount_root_directory)
        settings_menu.addAction(change_mount_root_action)

    def launch_rclone_manager(self):
        """Launch the standalone Rclone Config Manager tool."""
        if not os.path.exists(self.rclone_tool_path):
            self.show_error(f"Rclone Manager not found: {self.rclone_tool_path}")
            return
        try:
            subprocess.Popen([sys.executable, self.rclone_tool_path])
        except Exception as exc:
            self.show_error(f"Failed to launch Rclone Manager: {exc}")

    def change_rclone_config_path(self):
        """Open a file dialog to allow the user to select a new rclone config file path."""
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select rclone.config File",
            "",
            "Configuration Files (*.conf);;All Files (*)",
            options=options
        )
        if file_path:
            # Update the config path
            self.rclone_config_path = file_path
            # Update the status bar
            self.update_status_bar()
            print(f"rclone.config path changed to: {self.rclone_config_path}")
            self.update_global_config({"rclone_config_path": self.rclone_config_path})
            # Optionally, you can add logic here to reload or apply the new config

    def change_mount_root_directory(self):
        """Open a directory dialog to allow the user to select a new mount root directory."""
        options = QFileDialog.Options()
        options |= QFileDialog.ShowDirsOnly
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select New Mount Root Directory",
            self.drives_dir,
            options=options
        )
        if directory:
            # Update the drives_dir
            self.drives_dir = directory
            # Update the status bar
            self.update_status_bar()
            print(f"Mount Root Directory changed to: {self.drives_dir}")

            # Update global.config
            self.update_global_config({"drives_dir": self.drives_dir})

    def update_global_config(self, updates):
        """Update the global.config file with new key/value pairs."""
        try:
            config_data = self.load_global_config()
            config_data.update(updates)
            with open(GLOBAL_CONFIG_PATH, 'w') as config_file:
                json.dump(config_data, config_file, indent=4)
            print(f"global.config updated with: {updates}")
        except Exception as e:
            self.show_error(f"Failed to update global.config: {e}")

    def set_window_icon(self):
        """Set the window icon from the embedded SVG data."""
        try:
            subject_icon = get_subjective_tool_icon()
            if not subject_icon.isNull():
                self.setWindowIcon(subject_icon)
                print("Window icon set successfully.")
                return

            # Initialize QSvgRenderer with the SVG data
            renderer = QSvgRenderer(SVG_ICON.encode('utf-8'))
            pixmap = QPixmap(256, 256)
            pixmap.fill(Qt.transparent)

            # Render the SVG onto the pixmap
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()

            # Set the window icon
            self.setWindowIcon(QIcon(pixmap))
            print("Window icon set successfully.")
        except Exception as e:
            print(f"Error setting window icon: {e}")

    def _svg_to_icon(self, svg_text, size):
        """Render an SVG string to a QIcon."""
        renderer = QSvgRenderer(svg_text.encode("utf-8"))
        pixmap = QPixmap(size.width(), size.height())
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def render_svg_icon(self):
        """Render the embedded SVG icon and return a QPixmap."""
        try:
            renderer = QSvgRenderer(SVG_ICON.encode('utf-8'))
            pixmap = QPixmap(64, 64)  # Adjusted size to 64x64 (50% smaller)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            print("SVG icon rendered successfully.")
            return pixmap
        except Exception as e:
            print(f"Error rendering SVG icon: {e}")
            return QPixmap()

    def toggle_date_filter(self, state):
        """Enable or disable the modified date filter based on the checkbox."""
        if state == Qt.Checked:
            self.date_edit.setEnabled(True)
            print("Modified Date filter enabled.")
        else:
            self.date_edit.setEnabled(False)
            print("Modified Date filter disabled.")

    def start_filter_loading(self):
        """Load filter values in a background thread to keep UI responsive."""
        if self._filter_loading:
            return
        self._filter_loading = True

        self.drive_combo.clear()
        self.drive_combo.addItem("Loading...")
        self.drive_combo.setEnabled(False)
        self.file_type_combo.clear()
        self.file_type_combo.addItem("Loading...")
        self.file_type_combo.setEnabled(False)

        self.statusBar().showMessage("Loading filters...")

        self.filter_loader = FilterLoader(self.db_path)
        self.filter_loader.loaded_signal.connect(self.apply_filter_data)
        self.filter_loader.error_signal.connect(self.handle_filter_error)
        self.filter_loader.finished.connect(self.handle_filter_finished)
        self.filter_loader.start()

    def handle_filter_finished(self):
        self._filter_loading = False

    def apply_filter_data(self, drives, file_types):
        self.drive_combo.clear()
        self.drive_combo.addItem("Any")
        for drive in drives:
            self.drive_combo.addItem(drive)
        self.drive_combo.setEnabled(True)

        self.file_type_combo.clear()
        self.file_type_combo.addItem("Any")
        for file_type in file_types:
            self.file_type_combo.addItem(file_type)
        self.file_type_combo.setEnabled(True)

        self._filters_loaded = True
        self.statusBar().showMessage(
            f"Filters loaded | DB: {self.db_path} | Mount Root: {self.drives_dir}"
        )
        print("Filters loaded successfully.")

    def handle_filter_error(self, message):
        print(f"Filter load error: {message}")
        self.drive_combo.clear()
        self.drive_combo.addItem("Any")
        self.drive_combo.setEnabled(False)
        self.file_type_combo.clear()
        self.file_type_combo.addItem("Any")
        self.file_type_combo.setEnabled(False)
        self.statusBar().showMessage(f"Filter load failed: {message}")

    def populate_drive_combo(self):
        """Populate the drive combo box (async)."""
        self.start_filter_loading()

    def populate_file_type_combo(self):
        """Populate the file type combo box (async)."""
        self.start_filter_loading()

    def perform_search(self):
        """Generate and execute the SQL query based on the filters, then display the results."""
        print("\nPerforming search with the following criteria:")
        if not self.db_path or not os.path.exists(self.db_path):
            self.show_error(f"Database not found at: {self.db_path}")
            return

        name = self.name_input.text().strip()
        size = self.size_input.text().strip()
        drive = self.drive_combo.currentText()
        file_type = self.file_type_combo.currentText()
        if drive == "Loading...":
            drive = "Any"
        if file_type == "Loading...":
            file_type = "Any"

        # Handle Modified Date based on the checkbox
        if self.date_checkbox.isChecked():
            modified_date = self.date_edit.date().toString("yyyy-MM-dd")
            print(f"Modified After: '{modified_date}'")
        else:
            modified_date = None
            print("Modified After: Not applied")

        print(f"Name: '{name}'")
        print(f"Size > (bytes): '{size}'")
        print(f"Drive: '{drive}'")
        print(f"File Type: '{file_type}'")

        # Modify the query to search within 'full_path' instead of 'file_name'
        query = "SELECT full_path, drive, size, file_type, modified_date FROM files"
        conditions = []
        params = []

        if name:
            conditions.append("full_path LIKE ?")
            params.append(f"%{name}%")
            print(f"Added condition: full_path LIKE '%{name}%'")
        if size:
            try:
                size_int = int(size)
                conditions.append("size > ?")
                params.append(size_int)
                print(f"Added condition: size > {size_int}")
            except ValueError:
                print("Error: Size must be a number representing bytes.")
                self.show_error("Size must be a number representing bytes.")
                return
        if drive != "Any":
            conditions.append("drive = ?")
            params.append(drive)
            print(f"Added condition: drive = '{drive}'")
        if modified_date:
            conditions.append("DATE(modified_date) > DATE(?)")
            params.append(modified_date)
            print(f"Added condition: DATE(modified_date) > DATE('{modified_date}')")
        if file_type != "Any":
            conditions.append("file_type = ?")
            params.append(file_type)
            print(f"Added condition: file_type = '{file_type}'")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
            print(f"Final Query with WHERE clause: {query}")
        else:
            print("Final Query without WHERE clause.")

        query += " ORDER BY modified_date DESC"
        print(f"Final Query after ORDER BY: {query}")
        print(f"Parameters: {params}")

        # **Show Progress Bar**
        self.progress_bar.setVisible(True)

        start_time = time.time()
        try:
            conn = sqlite3.connect(self.db_path, timeout=3)
            cursor = conn.cursor()
            print("Executing query...")
            cursor.execute(query, params)
            results = cursor.fetchall()
            conn.close()
            end_time = time.time()
            elapsed_time = end_time - start_time
            print(f"Query executed successfully in {elapsed_time:.4f} seconds.")
            print(f"Number of results fetched: {len(results)}")
            self.display_results(results)
        except Exception as e:
            print(f"Error executing query: {e}")
            self.show_error(f"Error executing query: {e}")
        finally:
            # **Hide Progress Bar**
            self.progress_bar.setVisible(False)

    def display_results(self, results):
        """Display the query results in the table widget."""
        print("Displaying results in the table...")
        self.results_table.setRowCount(0)  # Clear existing results

        for row_data in results:
            full_path = row_data[0]
            drive = row_data[1]
            size = row_data[2]
            file_type = row_data[3]
            modified_date = row_data[4]

            # Determine if the item is a folder based on 'file_type'
            is_folder = file_type.lower() == 'folder'

            # Extract the relative path after the colon
            if ':' in full_path:
                _, _, relative_path = full_path.partition(':')
            else:
                relative_path = full_path  # Fallback if ':' not present

            relative_path = relative_path.lstrip('/\\')

            if is_folder:
                display_name = os.path.join(drive, relative_path)
            else:
                display_name = os.path.basename(full_path)

            row_number = self.results_table.rowCount()
            self.results_table.insertRow(row_number)

            # File Name or Folder Path
            file_name_item = QTableWidgetItem(display_name)
            file_name_item.setToolTip(full_path)  # Set tooltip with full path
            file_name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Align left
            file_name_item.setFlags(file_name_item.flags() | Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.results_table.setItem(row_number, 0, file_name_item)

            # Drive
            drive_item = QTableWidgetItem(drive)
            drive_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.results_table.setItem(row_number, 1, drive_item)

            # Size (bytes)
            size_item = QTableWidgetItem(str(size))
            size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.results_table.setItem(row_number, 2, size_item)

            # File Type
            file_type_item = QTableWidgetItem(file_type)
            file_type_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.results_table.setItem(row_number, 3, file_type_item)

            # Modified Date
            modified_date_item = QTableWidgetItem(modified_date)
            modified_date_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.results_table.setItem(row_number, 4, modified_date_item)

            # Set tooltip for the entire row
            for column in range(self.results_table.columnCount()):
                self.results_table.item(row_number, column).setToolTip(full_path)

        # Prevent the "File Name" column from resizing when data loads
        # Ensure that column widths remain as set in adjust_column_widths

        # Remove resizeColumnsToContents to prevent dynamic resizing
        # self.results_table.resizeColumnsToContents()  # Already removed

        print("Results displayed successfully.")

        if not results:
            print("No results found.")
            QMessageBox.information(self, "No Results", "No files found matching the search criteria.")

        # **Ensure that the text area is hidden when displaying search results**
        self.update_output_text.hide()
        self.results_table.show()

    def clear_filters(self):
        """Clear all search filters."""
        print("Clearing all filters...")
        self.name_input.clear()
        self.size_input.clear()
        self.drive_combo.setCurrentIndex(0)
        self.file_type_combo.setCurrentIndex(0)
        self.date_checkbox.setChecked(False)
        self.date_edit.setDate(QDate.currentDate())
        print("All filters cleared.")

    def show_error(self, message):
        """Display an error message to the user."""
        print(f"Displaying error message: {message}")
        QMessageBox.critical(self, "Error", message)

    def resizeEvent(self, event):
        """Handle window resize events to adjust column widths."""
        super().resizeEvent(event)
        self.adjust_column_widths()

    def adjust_column_widths(self):
        """Adjust the column widths based on the current window width."""
        total_width = self.results_table.viewport().width()
        full_name_width = int(total_width * 0.6)
        remaining_width = total_width - full_name_width

        # Assuming 4 remaining columns: Drive, Size (bytes), File Type, Modified Date
        # Distribute remaining width equally
        other_columns = ["Drive", "Size (bytes)", "File Type", "Modified Date"]
        num_other_columns = len(other_columns)
        if num_other_columns == 0:
            return
        each_other_width = int(remaining_width / num_other_columns)

        # Set the width for each column
        self.results_table.setColumnWidth(0, full_name_width)  # File Name or Folder Path

        for i in range(1, self.results_table.columnCount()):
            self.results_table.setColumnWidth(i, each_other_width)

    def showEvent(self, event):
        """Handle the show event to adjust column widths initially."""
        super().showEvent(event)
        self.adjust_column_widths()
        if not self._filters_loaded:
            QTimer.singleShot(0, self.start_filter_loading)

    def open_context_menu(self, position: QPoint):
        """Open a contextual menu on right-click with options to copy paths and show folder."""
        # Get the index of the item that was clicked
        index = self.results_table.indexAt(position)
        if not index.isValid():
            return

        row = index.row()

        # Retrieve data from the selected row
        file_name_item = self.results_table.item(row, 0)
        drive_item = self.results_table.item(row, 1)
        size_item = self.results_table.item(row, 2)
        file_type_item = self.results_table.item(row, 3)
        modified_date_item = self.results_table.item(row, 4)

        if not file_name_item:
            return

        # Assuming that if display_name is full_path (for folders), extract accordingly
        display_name = file_name_item.text()
        full_path = file_name_item.toolTip()

        # Extract file name
        if ':' in full_path:
            _, _, relative_path = full_path.partition(':')
            relative_path = relative_path.lstrip('/\\')
        else:
            relative_path = full_path  # Fallback if ':' not present

        is_folder = file_type_item.text().lower() == 'folder'

        if is_folder:
            nautilus_path = os.path.join(self.drives_dir, drive_item.text(), relative_path)
        else:
            nautilus_path = os.path.dirname(os.path.join(self.drives_dir, drive_item.text(), relative_path))

        # Create the context menu
        context_menu = QMenu(self)

        copy_fullpath_action = context_menu.addAction("Copy FullPath")
        copy_filename_action = context_menu.addAction("Copy FileName")
        copy_file_action = context_menu.addAction("Copy File")
        show_folder_action = context_menu.addAction("Show Folder")  # New action

        # Execute the context menu and get the selected action
        selected_action = context_menu.exec_(self.results_table.viewport().mapToGlobal(position))

        if selected_action == copy_fullpath_action:
            self.copy_fullpath(full_path)
        elif selected_action == copy_filename_action:
            file_name = os.path.basename(full_path.split(':', 1)[-1]) if ':' in full_path else full_path
            self.copy_filename(file_name)
        elif selected_action == copy_file_action:
            self.copy_file(full_path)
        elif selected_action == show_folder_action:
            self.show_folder(row)

    def copy_fullpath(self, full_path: str):
        """Copy the full path to the clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(full_path)
        print(f"Copied FullPath to clipboard: {full_path}")

    def copy_filename(self, file_name: str):
        """Copy the file name to the clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(file_name)
        print(f"Copied FileName to clipboard: {file_name}")

    def copy_file(self, full_path: str):
        """Copy the file or folder as a file reference to the clipboard."""
        mime_data = QMimeData()
        # Convert the path to a QUrl
        file_url = QUrl.fromLocalFile(full_path)
        mime_data.setUrls([file_url])
        clipboard = QApplication.clipboard()
        clipboard.setMimeData(mime_data)
        print(f"Copied File to clipboard: {full_path}")

    def open_in_file_manager(self, path):
        """Open a path in the OS file manager."""
        try:
            if os.name == "nt":
                subprocess.Popen(["explorer", path])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["nemo", path])
            print(f"Opened file manager at: {path}")
        except Exception as e:
            self.show_error(f"Failed to open file manager: {e}")

    def show_folder(self, row=None):
        """
        Show the selected folder in the system file manager.
        If the drive is 'localdrive', open directly without mounting.
        Otherwise, perform mounting as needed and then open.
        """
        print("Attempting to show folder in file manager...")

        if row is None:
            # If row is not provided, get the currently selected row
            selected_items = self.results_table.selectedItems()
            if not selected_items:
                self.show_error("No row selected.")
                return
            row = selected_items[0].row()

        # Retrieve data from the selected row
        file_name_item = self.results_table.item(row, 0)
        drive_item = self.results_table.item(row, 1)
        file_type_item = self.results_table.item(row, 3)

        if not file_name_item or not drive_item or not file_type_item:
            self.show_error("Invalid row data.")
            return

        full_path = file_name_item.toolTip()
        drive_name = drive_item.text()
        is_folder = file_type_item.text().lower() == 'folder'

        print(f"Selected Drive: {drive_name}")
        print(f"Full Path: {full_path}")

        # Extract the relative path after the colon
        if ':' in full_path:
            _, _, relative_path = full_path.partition(':')
        else:
            relative_path = full_path  # Fallback if ':' not present

        relative_path = relative_path.lstrip('/\\')

        # Determine if the drive is 'localdrive'
        if drive_name.lower() == "localdrive":
            # Construct the local path
            if is_folder:
                local_path = os.path.join(self.drives_dir, relative_path)
            else:
                local_path = os.path.dirname(os.path.join(self.drives_dir, relative_path))
            
            print(f"Local path to open: {local_path}")

            # Verify that the path exists
            if not os.path.exists(local_path):
                self.show_error(f"The path '{local_path}' does not exist.")
                return

            self.open_in_file_manager(local_path)
        else:
            # Handle non-local drives (remote drives)
            # Create subdirectory for the drive if it doesn't exist
            drive_mount_path = os.path.join(self.drives_dir, drive_name)
            if not os.path.exists(drive_mount_path):
                try:
                    os.makedirs(drive_mount_path, exist_ok=True)
                    print(f"Created directory for drive '{drive_name}' at: {drive_mount_path}")
                except Exception as e:
                    self.show_error(f"Failed to create drive directory: {e}")
                    return

            # Check if the drive is already mounted by checking if the directory is empty
            # If empty, mount the drive
            if not os.listdir(drive_mount_path):
                print(f"Directory '{drive_mount_path}' is empty. Attempting to mount the drive.")
                if not self.rclone_path:
                    self.show_error(
                        "rclone not found. Set RCLONE_PATH in the environment or add "
                        "\"rclone_path\" to global.config."
                    )
                    return
                # Parse rclone.config to find the remote matching the drive_name
                config = configparser.ConfigParser()
                if not os.path.exists(self.rclone_config_path):
                    self.show_error(f"rclone.config not found at {self.rclone_config_path}.")
                    return

                try:
                    config.read(self.rclone_config_path)
                    if drive_name not in config.sections():
                        self.show_error(f"Drive '{drive_name}' not found in rclone.config.")
                        return
                    remote = drive_name  # Assuming the section name matches the remote name
                    print(f"Found remote '{remote}' in rclone.config.")
                except Exception as e:
                    self.show_error(f"Error parsing rclone.config: {e}")
                    return

                # Mount the drive using rclone
                mount_command = [
                    self.rclone_path,
                    "mount",
                    remote,
                    drive_mount_path,
                    "--daemon"  # Run in the background
                ]

                try:
                    print(f"Mounting drive with command: {' '.join(mount_command)}")
                    subprocess.Popen(mount_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print(f"Drive '{remote}' mounted at '{drive_mount_path}'.")
                    # Wait briefly to ensure the mount has time to establish
                    time.sleep(5)
                except Exception as e:
                    self.show_error(f"Failed to mount drive '{remote}': {e}")
                    return

            # Construct the path to open in the file manager
            if is_folder:
                nemo_path = os.path.join(self.drives_dir, drive_name, relative_path)
            else:
                nemo_path = os.path.dirname(os.path.join(self.drives_dir, drive_name, relative_path))

            print(f"Constructed file manager path: {nemo_path}")

            # Verify that the path exists
            if not os.path.exists(nemo_path):
                self.show_error(f"The path '{nemo_path}' does not exist.")
                return

            self.open_in_file_manager(nemo_path)

    def update_index(self):
        """Handle the Update Index button click to execute rclone_list_files.py and display output."""
        print("\nUpdate Index button clicked.")

        script_path = self.search_index_script_path

        if not os.path.isfile(script_path):
            print(f"Script not found at {script_path}. Prompting user to locate the script.")
            QMessageBox.warning(
                self, 
                "Script Not Found",
                f"Update script not found at {script_path}.\nPlease locate the 'rclone_list_files.py' script."
            )
            options = QFileDialog.Options()
            options |= QFileDialog.ReadOnly
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Locate rclone_list_files.py",
                "",
                "Python Files (*.py);;All Files (*)",
                options=options
            )
            if file_path:
                script_path = file_path
                self.search_index_script_path = script_path  # Update the path
                print(f"User selected script at {script_path}.")
                self.update_global_config({"search_index_script_path": self.search_index_script_path})
            else:
                print("User did not select a script. Aborting Update Index.")
                QMessageBox.information(
                    self, 
                    "Update Index", 
                    "No script selected. Update Index aborted."
                )
                return

        # Check if the script is executable or can be run with python3
        if not os.access(script_path, os.X_OK):
            print(f"Script at {script_path} is not executable. Attempting to run with python3.")

        # **Replace the table with the text area**
        self.results_table.hide()
        self.update_output_text.show()
        self.update_output_text.clear()
        args = []
        effective_config_path = self.rclone_config_path
        passed_data = read_last_passed_remotes()
        if passed_data is not None:
            passed_remotes, passed_config = passed_data
            if not passed_remotes:
                QMessageBox.warning(
                    self,
                    "Update Index",
                    "No passed remotes found from the last test. Run tests in the Rclone Manager first.",
                )
                return
            if passed_config:
                effective_config_path = passed_config
            args.extend(["--drives", *passed_remotes])
        if effective_config_path:
            args.extend(["--config", effective_config_path])
        self.update_output_text.append(
            f"Executing: {' '.join([sys.executable, script_path] + args)}\n\n"
        )

        # Initialize and start the worker thread
        env = os.environ.copy()
        if self.rclone_path:
            env["RCLONE_PATH"] = self.rclone_path
        env["PASSED_REMOTES_FILE"] = passed_remotes_file_path()
        self.thread = ScriptRunner(script_path, sys.executable, args=args, env=env)
        self.thread.output_signal.connect(self.append_output)
        self.thread.error_signal.connect(self.append_error)
        self.thread.finished_signal.connect(self.handle_script_finished)
        self.thread.start()

    def append_output(self, text):
        """Append standard output to the text area."""
        self.update_output_text.append(text)

    def append_error(self, text):
        """Append error output to the text area."""
        # Display errors in red
        self.update_output_text.append(f"<span style='color:red;'>{text}</span>")

    def handle_script_finished(self, return_code):
        """Handle the completion of the script execution."""
        if return_code == 0:
            print("Script executed successfully.")
            QMessageBox.information(self, "Update Index", "Index updated successfully.")
        else:
            print(f"Script executed with errors. Return code: {return_code}")
            QMessageBox.critical(
                self, 
                "Update Index Failed",
                f"An error occurred while updating the index.\nReturn Code: {return_code}"
            )
        self.refresh_filters()

    # **Optional Method: Refresh Filters After Update**
    def refresh_filters(self):
        """Refresh the drive and file type combo boxes after updating the index."""
        print("Refreshing Drive and File Type filters after index update.")
        self._filters_loaded = False
        self.start_filter_loading()
    # **End of Optional Method**

def main():
    app = QApplication(sys.argv)
    install_subjective_window_chrome(app)
    window = FileSearchApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
