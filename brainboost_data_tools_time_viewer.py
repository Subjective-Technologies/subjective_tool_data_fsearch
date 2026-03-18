#!/usr/bin/env python3

import sys
import sqlite3
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLabel, QFrame, QSizePolicy, QProgressBar, QStatusBar, QAction, QMessageBox, QSplitter,
    QGraphicsDropShadowEffect, QPushButton, QCalendarWidget, QTimeEdit, QToolButton
)
from PyQt5.QtCore import Qt, QSize, QTimer, pyqtSignal, QThread, QPropertyAnimation, QRect, QDateTime
from PyQt5.QtGui import QFont, QPainter, QColor, QPen, QIcon, QLinearGradient
import logging
import time
import os
import inspect
from database_client import DatabaseClientSQLite

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from com_subjective_tools.window_chrome import get_subjective_tool_icon, install_subjective_window_chrome

# Global variable to store last log time
_last_log_time = None

def log_with_time(message, level=logging.INFO):
    """Helper function for logging with timestamp and execution time"""
    global _last_log_time
    current_time = time.time()
    
    # Get caller's info
    frame = inspect.currentframe().f_back
    filename = os.path.basename(frame.f_code.co_filename)
    lineno = frame.f_lineno
    
    # Calculate execution time
    if _last_log_time is None:
        exec_time = 0
    else:
        exec_time = int((current_time - _last_log_time) * 1000)  # Convert to milliseconds
    
    _last_log_time = current_time
    
    # Format timestamp
    timestamp = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    
    # Create log message with our custom format
    log_message = f"{timestamp} | {filename}:{lineno} | {message} | {exec_time}ms"
    
    logging.log(level, log_message)

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler('time_viewer_debug.log'),
        logging.StreamHandler()
    ]
)

class DateTimeSelector(QFrame):
    """Custom widget for date and time selection"""
    dateTimeChanged = pyqtSignal(QDateTime)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet("""
            DateTimeSelector {
                background-color: #2b2b2b;
                border-radius: 8px;
                padding: 8px;
                margin: 4px;
            }
            QToolButton {
                background-color: #3d3d3d;
                border: none;
                border-radius: 4px;
                padding: 4px;
                color: white;
            }
            QToolButton:hover {
                background-color: #4d4d4d;
            }
            QTimeEdit {
                background-color: #3d3d3d;
                border: none;
                border-radius: 4px;
                padding: 4px;
                color: white;
            }
            QCalendarWidget {
                background-color: #2b2b2b;
                color: white;
            }
            QCalendarWidget QWidget {
                alternate-background-color: #3d3d3d;
                color: white;
            }
            QCalendarWidget QAbstractItemView:enabled {
                color: white;
                background-color: #2b2b2b;
                selection-background-color: #0d47a1;
                selection-color: white;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #2b2b2b;
            }
            QCalendarWidget QToolButton {
                color: white;
                background-color: #3d3d3d;
                padding: 4px;
            }
        """)
        
        # Initialize widgets first
        self.calendar = QCalendarWidget()
        self.calendar.setWindowFlags(Qt.Popup)
        self.calendar.activated.connect(self.calendar_date_selected)
        
        self.date_button = QToolButton()
        self.date_button.setPopupMode(QToolButton.InstantPopup)
        self.date_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.date_button.setIcon(QIcon.fromTheme("calendar"))
        self.date_button.clicked.connect(self.show_calendar)
        
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.timeChanged.connect(self.time_changed)
        
        self.today_button = QPushButton("Today")
        self.today_button.clicked.connect(self.go_to_today)
        
        # Set up layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        layout.addWidget(self.date_button)
        layout.addWidget(self.time_edit)
        layout.addWidget(self.today_button)
        layout.addStretch()
        
        # Set current date/time
        self.set_current_datetime(QDateTime.currentDateTime())
    
    def set_current_datetime(self, dt):
        """Set the current date and time"""
        self.calendar.setSelectedDate(dt.date())
        self.time_edit.setTime(dt.time())
        self.dateTimeChanged.emit(self.get_selected_datetime())
    
    def show_calendar(self):
        """Show the calendar widget"""
        pos = self.date_button.mapToGlobal(self.date_button.rect().bottomLeft())
        self.calendar.move(pos)
        self.calendar.show()
    
    def calendar_date_selected(self):
        """Handle calendar date selection"""
        self.dateTimeChanged.emit(self.get_selected_datetime())
    
    def time_changed(self):
        """Handle time changes"""
        self.dateTimeChanged.emit(self.get_selected_datetime())
    
    def go_to_today(self):
        """Set the date/time to current"""
        self.set_current_datetime(QDateTime.currentDateTime())
    
    def get_selected_datetime(self):
        """Get the currently selected date and time"""
        return QDateTime(self.calendar.selectedDate(), self.time_edit.time())

class TimelineWidget(QWidget):
    """Widget that displays a horizontal timeline"""
    def __init__(self, start_time, end_time, parent=None):
        super().__init__(parent)
        self.start_time = start_time
        self.end_time = end_time
        self.setMinimumHeight(60)  # Increased for better visibility
        self.setStyleSheet("background: transparent;")
        logging.debug(f"Initializing TimelineWidget from {start_time} to {end_time}")

    def paintEvent(self, event):
        try:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            width = self.width()
            height = self.height()
            
            # Draw background for debugging
            painter.fillRect(self.rect(), QColor(40, 40, 40, 50))
            
            # Calculate timeline metrics
            timeline_height = 8  # Increased thickness
            y = height // 2
            
            logging.debug(f"Drawing timeline at width={width}, height={height}, y={y}")
            
            # Draw time markers (vertical lines)
            time_diff = self.end_time - self.start_time
            total_minutes = time_diff.total_seconds() / 60
            marker_interval = max(5, total_minutes / 10)  # At least 5 minutes between markers
            
            current_time = self.start_time
            while current_time <= self.end_time:
                x_pos = self._get_x_position(current_time)
                
                # Draw vertical marker
                painter.setPen(QPen(QColor("#4f4f4f"), 1))
                painter.drawLine(x_pos, y - 15, x_pos, y + 15)
                
                # Draw time label
                painter.setPen(QColor("#a0a0a0"))
                time_text = current_time.strftime("%H:%M")
                metrics = painter.fontMetrics()
                text_width = metrics.horizontalAdvance(time_text)
                painter.drawText(x_pos - text_width/2, y + 30, time_text)
                
                current_time += timedelta(minutes=marker_interval)
            
            # Draw main timeline
            gradient = QLinearGradient(10, y, width - 10, y)
            gradient.setColorAt(0, QColor("#42a5f5"))
            gradient.setColorAt(1, QColor("#2196f3"))
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(10, y - timeline_height//2, width - 20, timeline_height, 4, 4)
            
            # Draw start and end markers
            marker_radius = 8
            painter.setBrush(QColor("#0d47a1"))
            painter.drawEllipse(8, y - marker_radius, marker_radius * 2, marker_radius * 2)
            painter.drawEllipse(width - marker_radius * 2 - 8, y - marker_radius, marker_radius * 2, marker_radius * 2)
            
            logging.debug("Timeline painting completed successfully")
            
        except Exception as e:
            logging.error(f"Error painting timeline: {str(e)}")
            raise

    def _get_x_position(self, time_point):
        """Calculate x position for a given time point"""
        try:
            total_width = self.width() - 40  # Account for margins
            total_time = (self.end_time - self.start_time).total_seconds()
            if total_time == 0:
                return 20  # Default to left margin
            
            time_diff = (time_point - self.start_time).total_seconds()
            x_pos = 20 + (time_diff / total_time) * total_width
            return x_pos
            
        except Exception as e:
            logging.error(f"Error calculating x position: {str(e)}")
            return 20

class TimeIntervalWidget(QFrame):
    clicked = pyqtSignal(object)  # Signal to emit when interval is clicked
    
    def __init__(self, start_time, end_time, file_count, parent=None):
        super().__init__(parent)
        self.start_time = start_time
        self.end_time = end_time
        self.file_count = file_count
        self.is_selected = False
        
        # Set minimum size and fixed height for consistent layout
        self.setMinimumWidth(200)
        self.setFixedHeight(90)  # Reduced height since we removed timeline
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
        # Set up the widget style
        self.setStyleSheet("""
            TimeIntervalWidget {
                background-color: #2b2b2b;
                border-radius: 8px;
                margin: 6px;
                padding: 12px;
                color: #ffffff;
            }
            TimeIntervalWidget[selected="true"] {
                background-color: #0d47a1;
                border: 2px solid #42a5f5;
            }
            TimeIntervalWidget:hover {
                background-color: #3d3d3d;
                border: 1px solid #42a5f5;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)
        
        # Set up the layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        
        # Create labels with larger font
        time_font = QFont()
        time_font.setPointSize(12)
        time_font.setBold(True)
        
        date_font = QFont()
        date_font.setPointSize(10)
        
        count_font = QFont()
        count_font.setPointSize(9)
        
        # Time range (e.g., "14:30 - 14:35")
        self.time_label = QLabel(f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        self.time_label.setFont(time_font)
        self.time_label.setStyleSheet("color: #ffffff; font-weight: bold;")
        self.time_label.setAlignment(Qt.AlignCenter)
        
        # Date (e.g., "2024-01-15")
        self.date_label = QLabel(start_time.strftime("%Y-%m-%d"))
        self.date_label.setFont(date_font)
        self.date_label.setStyleSheet("color: #e0e0e0;")
        self.date_label.setAlignment(Qt.AlignCenter)
        
        # File count with icon
        self.count_label = QLabel(f"📁 {file_count} files")
        self.count_label.setFont(count_font)
        self.count_label.setStyleSheet("color: #90caf9;")
        self.count_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(self.time_label)
        layout.addWidget(self.date_label)
        layout.addWidget(self.count_label)
        
        # Add glow effect for better visibility
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(20)
        glow.setColor(QColor(66, 165, 245, 50))
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self)

    def setSelected(self, selected):
        if self.is_selected != selected:
            self.is_selected = selected
            self.setProperty("selected", selected)
            self.style().unpolish(self)
            self.style().polish(self)
            
            # Update glow effect
            glow = self.graphicsEffect()
            if selected:
                glow.setColor(QColor(66, 165, 245, 150))  # Brighter glow when selected
            else:
                glow.setColor(QColor(66, 165, 245, 50))  # Normal glow

    def enterEvent(self, event):
        glow = self.graphicsEffect()
        glow.setColor(QColor(66, 165, 245, 100))  # Increase opacity on hover
        super().enterEvent(event)

    def leaveEvent(self, event):
        glow = self.graphicsEffect()
        if self.is_selected:
            glow.setColor(QColor(66, 165, 245, 150))  # Keep bright if selected
        else:
            glow.setColor(QColor(66, 165, 245, 50))  # Reset to normal
        super().leaveEvent(event)

    def show_interval_files(self):
        log_with_time(f"Interval clicked: {self.start_time} - {self.end_time}")
        for i in range(self.timeline_layout.count()):
            widget = self.timeline_layout.itemAt(i).widget()
            if isinstance(widget, TimeIntervalWidget):
                widget.setSelected(widget == self)
        while self.files_layout.count():
            item = self.files_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        files = self.db_client.get_files_in_timerange(self.start_time, self.end_time)
        log_with_time(f"Loaded {len(files)} files for selected interval")
        for file in files:
            file_info = {
                'full_path': file.full_path,
                'size': file.size,
                'modified_date': file.modified_date,
                'drive': file.drive,
                'file_type': file.file_type
            }
            file_widget = FileWidget(file_info)
            self.files_layout.addWidget(file_widget)

class FileWidget(QFrame):
    def __init__(self, file_info, interval_start, interval_end, parent=None):
        super().__init__(parent)
        self.file_info = file_info
        self.interval_start = interval_start
        self.interval_end = interval_end
        
        # Set size policy
        self.setFixedHeight(180)  # Increased height for better spacing
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Set up the widget style
        self.setStyleSheet("""
            QFrame {
                background-color: #2b2b2b;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                margin: 8px;
                padding: 12px;
                color: #ffffff;
            }
            QFrame:hover {
                border: 1px solid #42a5f5;
                background-color: #3d3d3d;
            }
            QLabel {
                background: transparent;
                border: none;
                color: #ffffff;
                padding: 2px;
            }
        """)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)  # Increased spacing
        
        # Add timeline at the top
        self.timeline = TimelineWidget(interval_start, interval_end, self)
        layout.addWidget(self.timeline)
        
        # File information
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)  # Increased spacing
        
        # File name
        name_label = QLabel(os.path.basename(self.file_info['full_path']))
        name_label.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 11pt;")
        name_label.setWordWrap(True)
        name_label.setMinimumHeight(25)  # Ensure enough height for wrapped text
        
        # File details
        details_label = QLabel(f"Size: {self.format_size(self.file_info['size'])}")
        details_label.setStyleSheet("color: #90caf9; font-size: 10pt;")
        
        # Time
        time_label = QLabel(self.file_info['modified_date'].strftime("%Y-%m-%d %H:%M:%S"))
        time_label.setStyleSheet("color: #e0e0e0; font-size: 10pt;")
        
        info_layout.addWidget(name_label)
        info_layout.addWidget(details_label)
        info_layout.addWidget(time_label)
        layout.addLayout(info_layout)
    
    def format_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

class DatabaseLoader(QThread):
    """Thread for loading database data"""
    progress_signal = pyqtSignal(int, int)  # current, total
    finished_signal = pyqtSignal(list, int)  # list of files, skipped count
    error_signal = pyqtSignal(str)  # error message

    def __init__(self, db_path):
        super().__init__()
        self.db_path = db_path

    def run(self):
        try:
            log_with_time(f"Starting database connection to {self.db_path}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Set SQLite optimizations
            log_with_time("Setting SQLite optimizations")
            cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
            cursor.execute("PRAGMA cache_size=-2000000")  # Use 2GB of memory for cache
            cursor.execute("PRAGMA temp_store=MEMORY")  # Store temp tables and indices in memory
            cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes with reasonable safety
            cursor.execute("PRAGMA mmap_size=30000000000")  # Memory-mapped I/O
            conn.commit()
            log_with_time("SQLite optimizations applied")
            
            # Create indexes if they don't exist
            log_with_time("Creating indexes if needed")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_modified_date ON files(modified_date)")
            conn.commit()
            log_with_time("Indexes created")
            
            # First, get total count
            log_with_time("Executing count query")
            cursor.execute("""
                SELECT COUNT(*) FROM files 
                WHERE modified_date IS NOT NULL 
                AND modified_date LIKE '____-__-__ __:__:__'
                AND modified_date >= '1970-01-01 00:00:00'
                AND modified_date <= '2038-01-19 03:14:07'
            """)
            total_files = cursor.fetchone()[0]
            log_with_time(f"Total records in database: {total_files}")
            
            # Increase chunk size since we have indexes now
            chunk_size = 5000
            offset = 0
            files = []
            skipped = 0
            bad_dates = []
            processed = 0
            
            # Use a more efficient query that leverages the index
            query = """
                SELECT id, full_path, drive, size, modified_date, file_type 
                FROM files 
                WHERE modified_date IS NOT NULL 
                AND modified_date LIKE '____-__-__ __:__:__'
                AND modified_date >= '1970-01-01 00:00:00'
                AND modified_date <= '2038-01-19 03:14:07'
                ORDER BY modified_date DESC
                LIMIT ? OFFSET ?
            """
            
            while True:
                log_with_time(f"Processing chunk {offset//chunk_size + 1}, offset: {offset}")
                cursor.execute(query, (chunk_size, offset))
                
                chunk = cursor.fetchall()
                log_with_time(f"Fetched chunk of {len(chunk)} records")
                
                if not chunk:
                    log_with_time("No more records to process")
                    break
                
                chunk_start_time = time.time()
                for row in chunk:
                    id_, full_path, drive, size, modified_date, file_type = row
                    processed += 1
                    try:
                        dt = datetime.strptime(modified_date, "%Y-%m-%d %H:%M:%S")
                        files.append({
                            'full_path': full_path,
                            'size': size,
                            'modified_date': dt,
                            'drive': drive,
                            'file_type': file_type
                        })
                    except Exception as e:
                        skipped += 1
                        if len(bad_dates) < 10:
                            bad_dates.append(modified_date)
                        log_with_time(f"Bad date value: {modified_date} (row id: {id_}, error: {e})", level=logging.WARNING)
                
                chunk_time = time.time() - chunk_start_time
                log_with_time(f"Processed chunk in {chunk_time:.2f}s, {len(chunk)/chunk_time:.1f} records/second")
                
                offset += chunk_size
                self.progress_signal.emit(min(offset, total_files), total_files)
                
                # Small delay to allow UI updates
                self.msleep(10)
            
            conn.close()
            log_with_time(f"Database connection closed. Total processed: {processed}, valid: {len(files)}, skipped: {skipped}")
            
            if bad_dates:
                log_with_time(f"First 10 bad modified_date values: {bad_dates}", level=logging.ERROR)
            
            self.finished_signal.emit(files, skipped)
            
        except Exception as e:
            log_with_time(f"Database loading failed: {str(e)}", level=logging.ERROR)
            self.error_signal.emit(str(e))

class TimeViewerApp(QMainWindow):
    def __init__(self):
        try:
            super().__init__()
            logging.info("Initializing TimeViewerApp")
            
            # Window setup
            self.setWindowTitle("Time-Centric File System Viewer")
            logging.debug("Window title set")
            app_icon = get_subjective_tool_icon()
            if not app_icon.isNull():
                self.setWindowIcon(app_icon)
            
            # Set window size
            screen = QApplication.primaryScreen().geometry()
            self.setGeometry(screen)
            logging.debug(f"Window geometry set to screen size: {screen.width()}x{screen.height()}")
            
            # Initialize UI components
            self._init_ui()
            
            # Initialize data
            self._init_data()
            
            logging.info("TimeViewerApp initialization completed")
            
        except Exception as e:
            logging.error(f"Error during TimeViewerApp initialization: {str(e)}", exc_info=True)
            raise

    def _init_ui(self):
        """Initialize UI components"""
        try:
            logging.debug("Starting UI initialization")
            
            # Create main widget and layout
            main_widget = QWidget()
            self.setCentralWidget(main_widget)
            main_layout = QVBoxLayout(main_widget)
            logging.debug("Main layout created")
            
            # Create splitter
            splitter = QSplitter(Qt.Horizontal)
            main_layout.addWidget(splitter)
            logging.debug("Splitter created")
            
            # Create left pane (Timeline)
            timeline_container = self._create_timeline_pane()
            splitter.addWidget(timeline_container)
            logging.debug("Timeline pane created")
            
            # Create right pane (Files)
            files_container = self._create_files_pane()
            splitter.addWidget(files_container)
            logging.debug("Files pane created")
            
            # Set splitter sizes
            screen_width = QApplication.primaryScreen().geometry().width()
            splitter.setSizes([int(screen_width * 0.3), int(screen_width * 0.7)])
            logging.debug("Splitter sizes set")
            
            # Set dark theme
            self._set_dark_theme()
            logging.debug("Dark theme applied")
            
            logging.info("UI initialization completed")
            
        except Exception as e:
            logging.error(f"Error during UI initialization: {str(e)}", exc_info=True)
            raise

    def _init_data(self):
        """Initialize data and database connection"""
        try:
            logging.debug("Starting data initialization")
            
            # Initialize database connection
            self.db_path = "myself.sqlite"
            self.db_client = DatabaseClientSQLite(self.db_path)
            logging.debug(f"Database connected: {self.db_path}")
            
            # Initialize timeline data
            self._init_timeline_data()
            
            logging.info("Data initialization completed")
            
        except Exception as e:
            logging.error(f"Error during data initialization: {str(e)}", exc_info=True)
            raise

    def _init_timeline_data(self):
        """Initialize timeline data"""
        try:
            logging.debug("Starting timeline data initialization")
            
            # Get time range
            self.first_timestamp, self.last_timestamp = self.db_client.get_first_and_last_timestamp()
            logging.info(f"Time range: {self.first_timestamp} to {self.last_timestamp}")
            
            # Get average gap
            self.avg_gap = self.db_client.get_average_time_gap()
            logging.info(f"Average time gap: {self.avg_gap:.2f} minutes")
            
            # Calculate intervals
            self.current_page = 1
            self.intervals_per_page = 100
            
            min_gap_minutes = max(30, int(self.avg_gap))
            total_minutes = (self.last_timestamp - self.first_timestamp).total_seconds() / 60
            self.total_intervals = int(total_minutes / min_gap_minutes)
            
            logging.info(f"Total intervals: {self.total_intervals} with {min_gap_minutes} minute gaps")
            
            # Generate initial intervals
            self.update_timeline_display()
            
            logging.debug("Timeline data initialization completed")
            
        except Exception as e:
            logging.error(f"Error during timeline data initialization: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to initialize timeline data: {str(e)}")

    def _create_timeline_pane(self):
        """Create the timeline pane"""
        try:
            logging.debug("Creating timeline pane")
            
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(4)
            
            # Add navigation controls
            nav_widget = self._create_navigation_widget()
            layout.addWidget(nav_widget)
            
            # Add timeline scroll area
            self.timeline_scroll = QScrollArea()
            self.timeline_widget = QWidget()
            self.timeline_layout = QVBoxLayout(self.timeline_widget)
            self.timeline_layout.setAlignment(Qt.AlignTop)
            self.timeline_layout.setSpacing(2)
            
            self.timeline_scroll.setWidget(self.timeline_widget)
            self.timeline_scroll.setWidgetResizable(True)
            layout.addWidget(self.timeline_scroll)
            
            logging.debug("Timeline pane created successfully")
            return container
            
        except Exception as e:
            logging.error(f"Error creating timeline pane: {str(e)}", exc_info=True)
            raise

    def _create_files_pane(self):
        """Create the files pane"""
        try:
            logging.debug("Creating files pane")
            
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(4)
            
            self.files_scroll = QScrollArea()
            self.files_widget = QWidget()
            self.files_layout = QVBoxLayout(self.files_widget)
            self.files_layout.setAlignment(Qt.AlignTop)
            self.files_layout.setSpacing(12)
            
            self.files_scroll.setWidget(self.files_widget)
            self.files_scroll.setWidgetResizable(True)
            layout.addWidget(self.files_scroll)
            
            logging.debug("Files pane created successfully")
            return container
            
        except Exception as e:
            logging.error(f"Error creating files pane: {str(e)}", exc_info=True)
            raise

    def _set_dark_theme(self):
        """Apply dark theme to the application"""
        try:
            logging.debug("Applying dark theme")
            
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #1a1a1a;
                    color: #ffffff;
                }
                QPushButton {
                    background-color: #2b2b2b;
                    border: 1px solid #3d3d3d;
                    border-radius: 4px;
                    padding: 6px 12px;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #3d3d3d;
                    border: 1px solid #42a5f5;
                }
                QScrollBar:vertical {
                    background: #2b2b2b;
                    width: 12px;
                    margin: 0px;
                }
                QScrollBar::handle:vertical {
                    background: #3d3d3d;
                    min-height: 20px;
                    border-radius: 6px;
                }
                QScrollBar::handle:vertical:hover {
                    background: #4d4d4d;
                }
            """)
            
            logging.debug("Dark theme applied successfully")
            
        except Exception as e:
            logging.error(f"Error applying dark theme: {str(e)}", exc_info=True)
            raise

    def update_timeline_display(self):
        """Update the timeline display with current data"""
        try:
            logging.info("Updating timeline display")
            
            # Clear existing widgets
            self.clear_layout(self.timeline_layout)
            self.clear_layout(self.files_layout)
            
            if not hasattr(self, 'timeline_intervals'):
                logging.warning("No timeline intervals available")
                return
                
            # Calculate page range
            start_idx = (self.current_page - 1) * self.intervals_per_page
            end_idx = min(start_idx + self.intervals_per_page, len(self.timeline_intervals))
            
            logging.debug(f"Displaying intervals {start_idx} to {end_idx}")
            
            # Create interval widgets
            for interval in self.timeline_intervals[start_idx:end_idx]:
                try:
                    interval_widget = TimeIntervalWidget(
                        interval['start'],
                        interval['end'],
                        interval.get('files', []),
                        self
                    )
                    self.timeline_layout.addWidget(interval_widget)
                    logging.debug(f"Added interval widget for {interval['start']} - {interval['end']}")
                    
                except Exception as e:
                    logging.error(f"Error creating interval widget: {str(e)}", exc_info=True)
            
            # Update navigation
            self._update_navigation()
            
            logging.info("Timeline display update completed")
            
        except Exception as e:
            logging.error(f"Error updating timeline display: {str(e)}", exc_info=True)
            raise

    def sync_scroll_from_timeline(self, value):
        """Synchronize files scroll position when timeline is scrolled"""
        try:
            current_time = time.time()
            if current_time - self._last_sync_time < self._sync_cooldown:
                return
                
            if not self._sync_in_progress:
                self._sync_in_progress = True
                timeline_max = self.timeline_scroll.verticalScrollBar().maximum()
                files_max = self.files_scroll.verticalScrollBar().maximum()
                
                logging.debug(f"Syncing scroll from timeline: value={value}, max={timeline_max}")
                
                if timeline_max > 0:
                    relative_pos = value / timeline_max
                    new_value = int(relative_pos * files_max)
                    self.files_scroll.verticalScrollBar().setValue(new_value)
                    logging.debug(f"Set files scroll to {new_value}")
                
                self._last_sync_time = current_time
                self._sync_in_progress = False
                
        except Exception as e:
            logging.error(f"Error during timeline scroll sync: {str(e)}")
            self._sync_in_progress = False

    def sync_scroll_from_files(self, value):
        """Synchronize timeline scroll position when files are scrolled"""
        try:
            current_time = time.time()
            if current_time - self._last_sync_time < self._sync_cooldown:
                return
                
            if not self._sync_in_progress:
                self._sync_in_progress = True
                timeline_max = self.timeline_scroll.verticalScrollBar().maximum()
                files_max = self.files_scroll.verticalScrollBar().maximum()
                
                logging.debug(f"Syncing scroll from files: value={value}, max={files_max}")
                
                if files_max > 0:
                    relative_pos = value / files_max
                    new_value = int(relative_pos * timeline_max)
                    self.timeline_scroll.verticalScrollBar().setValue(new_value)
                    logging.debug(f"Set timeline scroll to {new_value}")
                
                self._last_sync_time = current_time
                self._sync_in_progress = False
                
        except Exception as e:
            logging.error(f"Error during files scroll sync: {str(e)}")
            self._sync_in_progress = False

    @staticmethod
    def clear_layout(layout):
        """Safely clear all widgets from a layout"""
        try:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            logging.debug("Layout cleared successfully")
        except Exception as e:
            logging.error(f"Error clearing layout: {str(e)}")

    def _create_navigation_widget(self):
        """Create navigation controls widget"""
        try:
            logging.debug("Creating navigation widget")
            
            nav_widget = QWidget()
            nav_layout = QHBoxLayout(nav_widget)
            nav_layout.setContentsMargins(0, 0, 0, 0)
            
            # Create date/time selector
            self.date_time_selector = DateTimeSelector()
            self.date_time_selector.dateTimeChanged.connect(self.date_time_selected)
            nav_layout.addWidget(self.date_time_selector)
            
            # Add spacer
            nav_layout.addSpacing(20)
            
            # Navigation buttons
            self.prev_button = QPushButton("Previous")
            self.next_button = QPushButton("Next")
            self.page_label = QLabel("Page 1")
            
            self.prev_button.clicked.connect(self.prev_page)
            self.next_button.clicked.connect(self.next_page)
            
            nav_layout.addWidget(self.prev_button)
            nav_layout.addWidget(self.page_label)
            nav_layout.addWidget(self.next_button)
            
            # Add stretch to keep buttons centered
            nav_layout.addStretch()
            
            logging.debug("Navigation widget created successfully")
            return nav_widget
            
        except Exception as e:
            logging.error(f"Error creating navigation widget: {str(e)}", exc_info=True)
            raise
            
    def prev_page(self):
        """Handle previous page button click"""
        try:
            if self.current_page > 1:
                self.current_page -= 1
                self.update_timeline_display()
                logging.debug(f"Moved to previous page: {self.current_page}")
        except Exception as e:
            logging.error(f"Error handling previous page: {str(e)}", exc_info=True)
            
    def next_page(self):
        """Handle next page button click"""
        try:
            max_page = (self.total_intervals + self.intervals_per_page - 1) // self.intervals_per_page
            if self.current_page < max_page:
                self.current_page += 1
                self.update_timeline_display()
                logging.debug(f"Moved to next page: {self.current_page}")
        except Exception as e:
            logging.error(f"Error handling next page: {str(e)}", exc_info=True)
            
    def _update_navigation(self):
        """Update navigation button states and page label"""
        try:
            max_page = (self.total_intervals + self.intervals_per_page - 1) // self.intervals_per_page
            
            # Update button states
            self.prev_button.setEnabled(self.current_page > 1)
            self.next_button.setEnabled(self.current_page < max_page)
            
            # Update page label
            self.page_label.setText(f"Page {self.current_page} of {max_page}")
            
            logging.debug(f"Navigation updated: page {self.current_page} of {max_page}")
            
        except Exception as e:
            logging.error(f"Error updating navigation: {str(e)}", exc_info=True)
            
    def date_time_selected(self, selected_datetime):
        """Handle date/time selection"""
        try:
            logging.debug(f"Date/time selected: {selected_datetime}")
            
            # Convert QDateTime to Python datetime
            py_datetime = selected_datetime.toPyDateTime()
            
            # Find the page containing this datetime
            min_gap_minutes = max(30, int(self.avg_gap))
            total_minutes = (py_datetime - self.first_timestamp).total_seconds() / 60
            self.current_page = max(1, int(total_minutes / (min_gap_minutes * self.intervals_per_page)) + 1)
            
            # Update the view
            self.update_timeline_display()
            
            logging.debug(f"Navigated to page {self.current_page} for datetime {py_datetime}")
            
        except Exception as e:
            logging.error(f"Error handling date/time selection: {str(e)}", exc_info=True)

def main():
    try:
        # Configure logging with more detail
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s | %(levelname)s | %(filename)s:%(lineno)d | %(funcName)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        logging.info("="*80)
        logging.info("Starting TimeViewerApp")
        
        app = QApplication(sys.argv)
        install_subjective_window_chrome(app)

        # Get screen info for debugging
        screen = app.primaryScreen()
        screen_geometry = screen.geometry()
        logging.info(f"Screen geometry: {screen_geometry.width()}x{screen_geometry.height()}")
        
        viewer = TimeViewerApp()
        
        # Log window geometry
        window_geometry = viewer.geometry()
        logging.info(f"Initial window geometry: {window_geometry.width()}x{window_geometry.height()}")
        
        viewer.show()
        logging.info("Window shown")
        
        # Log final window state
        final_geometry = viewer.geometry()
        logging.info(f"Final window geometry: {final_geometry.width()}x{final_geometry.height()}")
        logging.info("TimeViewerApp started successfully")
        logging.info("="*80)
        
        sys.exit(app.exec_())
        
    except Exception as e:
        logging.error(f"Fatal error in main: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main() 
