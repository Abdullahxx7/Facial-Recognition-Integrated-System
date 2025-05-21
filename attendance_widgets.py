from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QFormLayout, QLineEdit, QGroupBox,
    QListWidget, QListWidgetItem, QButtonGroup, QRadioButton, QGridLayout,
    QFileDialog, QSizePolicy, QFrame, QProgressBar
)
from PyQt5.QtCore import Qt, QDate, QTimer, QSize
from PyQt5.QtGui import QFont, QBrush, QColor

class AttendanceStatsWidget(QWidget):
    """Reusable widget to display attendance statistics with enhanced warnings"""
    
    def __init__(self, parent=None, compact=False):
        super().__init__(parent)
        self.compact = compact  # Compact mode for teacher/admin views
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Stats grid layout
        stats_layout = QGridLayout()
        stats_layout.setColumnStretch(1, 1)
        
        # Attendance percentage
        self.percentage_label = QLabel("Attendance: 0%")
        self.percentage_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        stats_layout.addWidget(self.percentage_label, 0, 0)
        
        # Absence count
        self.absence_count_label = QLabel("Total Absences: 0")
        stats_layout.addWidget(self.absence_count_label, 1, 0)
        
        # Remaining lectures before denial
        self.remaining_label = QLabel("Remaining before denial: 0")
        stats_layout.addWidget(self.remaining_label, 2, 0)
        
        # Status indicator
        self.status_frame = QFrame()
        self.status_frame.setFrameShape(QFrame.StyledPanel)
        self.status_frame.setMinimumWidth(100)
        self.status_frame.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        
        status_layout = QVBoxLayout(self.status_frame)
        status_layout.setContentsMargins(5, 5, 5, 5)
        self.status_label = QLabel("GOOD")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; color: white;")
        status_layout.addWidget(self.status_label)
        
        stats_layout.addWidget(self.status_frame, 0, 1, 3, 1)
        
        main_layout.addLayout(stats_layout)
        
        # Progress bar for visual indicator
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        main_layout.addWidget(self.progress_bar)
        
        # Warning message
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red; font-weight: bold;")
        self.warning_label.setAlignment(Qt.AlignCenter)
        self.warning_label.setWordWrap(True)
        main_layout.addWidget(self.warning_label)
        
        # Absence list (only in full mode)
        if not self.compact:
            absence_container = QGroupBox("Absence Dates")
            absence_layout = QVBoxLayout(absence_container)
            
            self.absence_list = QListWidget()
            self.absence_list.setMaximumHeight(150)
            absence_layout.addWidget(self.absence_list)
            
            main_layout.addWidget(absence_container)
        
        # Set initial state
        self.update_status(100)
    
    def update_data(self, attendance_data):
        """Update widget with attendance data
        
        attendance_data should be a dict with:
        - percentage: float (0-100)
        - absence_count: int
        - total_lectures: int
        - absence_dates: list of date strings
        - max_absence_percentage: float (default 20.0)
        """
        percentage = attendance_data.get('percentage', 100.0)
        absence_count = attendance_data.get('absence_count', 0)
        total_lectures = attendance_data.get('total_lectures', 0)
        absence_dates = attendance_data.get('absence_dates', [])
        max_absence_percentage = attendance_data.get('max_absence_percentage', 20.0)
        
        # Calculate remaining lectures before denial
        absence_percentage = 100.0 - percentage
        max_absences = total_lectures * (max_absence_percentage / 100.0)
        remaining = int(max_absences - absence_count)
        
        # Update labels
        self.percentage_label.setText(f"Attendance: {percentage:.1f}%")
        self.absence_count_label.setText(f"Total Absences: {absence_count}")
        
        if remaining > 0:
            self.remaining_label.setText(f"Remaining before denial: {remaining}")
        else:
            self.remaining_label.setText("Denied: Exceeded absence limit")
            self.remaining_label.setStyleSheet("color: red; font-weight: bold;")
        
        # Update progress bar
        self.progress_bar.setValue(int(percentage))
        
        # Update status indicator
        self.update_status(percentage)
        
        # Update absence list if not in compact mode
        if not self.compact and hasattr(self, 'absence_list'):
            self.absence_list.clear()
            for date_str in absence_dates:
                item = QListWidgetItem(date_str)
                self.absence_list.addItem(item)
                
                # Color-code recent absences in red
                if len(absence_dates) > 0 and date_str == absence_dates[0]:
                    item.setForeground(QBrush(QColor(255, 0, 0)))
    
    def update_status(self, percentage):
        """Update the status indicator based on attendance percentage"""
        if percentage >= 90:
            # Good status (green)
            self.status_frame.setStyleSheet("background-color: #4CAF50; border-radius: 5px;")
            self.status_label.setText("GOOD")
            self.warning_label.setText("")
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
        elif percentage >= 85:
            # First warning (yellow)
            self.status_frame.setStyleSheet("background-color: #FFC107; border-radius: 5px;")
            self.status_label.setText("WARNING")
            self.warning_label.setText("⚠️ FIRST WARNING: Your attendance is dropping below acceptable levels.")
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #FFC107; }")
        elif percentage >= 80:
            # Second warning (orange)
            self.status_frame.setStyleSheet("background-color: #FF9800; border-radius: 5px;")
            self.status_label.setText("AT RISK")
            self.warning_label.setText("⚠️⚠️ SECOND WARNING: You are at risk of being denied from this course.")
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #FF9800; }")
        else:
            # Denied (red)
            self.status_frame.setStyleSheet("background-color: #F44336; border-radius: 5px;")
            self.status_label.setText("DENIED")
            self.warning_label.setText("❌ FINAL WARNING: You have exceeded the absence threshold and are denied from this course.")
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #F44336; }")



class StudentAttendanceWidget(AttendanceStatsWidget):
    """Attendance widget specifically for student dashboard"""

    def __init__(self, parent=None):
        super().__init__(parent, compact=False)
        # Add student-specific UI elements if needed


class TeacherAttendanceWidget(QWidget):
    """Fixed attendance widget for teacher's student list view that displays properly in tables"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        # Use horizontal layout for better fit in table cells
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(5)
        
        # Create fixed-width percentage bar
        self.percentage_bar = QFrame()
        self.percentage_bar.setFixedWidth(100)
        self.percentage_bar.setMinimumHeight(20)
        self.percentage_bar.setMaximumHeight(20)
        self.percentage_bar.setFrameShape(QFrame.StyledPanel)
        
        # Add percentage label that overlays the bar
        self.percentage_label = QLabel("100%")
        self.percentage_label.setAlignment(Qt.AlignCenter)
        self.percentage_label.setStyleSheet("font-weight: bold; color: white;")
        
        # Create a layout for the percentage bar that allows the label to overlay it
        bar_layout = QHBoxLayout(self.percentage_bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.addWidget(self.percentage_label)
        
        # Add the percentage bar to the main layout
        layout.addWidget(self.percentage_bar)
        
        # Add absence info
        absence_info = QLabel("0/0 classes")
        absence_info.setStyleSheet("margin-left: 5px;")
        self.absence_info = absence_info
        layout.addWidget(absence_info, 1)  # Give it stretch priority
        
        # Set initial state
        self.update_status(100)
    
    def update_data(self, attendance_data):
        """Update widget with attendance data"""
        percentage = attendance_data.get('percentage', 100.0)
        absence_count = attendance_data.get('absence_count', 0)
        total_lectures = attendance_data.get('total_lectures', 0)
        
        # Update percentage display
        self.percentage_label.setText(f"{percentage:.1f}%")
        
        # Update absence information
        self.absence_info.setText(f"{absence_count}/{total_lectures} classes missed")
        
        # Apply color based on status
        self.update_status(percentage)
    
    def update_status(self, percentage):
        """Update the status indicator based on attendance percentage"""
        if percentage >= 90:
            # Good status (green)
            self.percentage_bar.setStyleSheet("background-color: #4CAF50; border-radius: 3px;")
        elif percentage >= 85:
            # First warning (yellow)
            self.percentage_bar.setStyleSheet("background-color: #FFC107; border-radius: 3px;")
        elif percentage >= 80:
            # Second warning (orange)
            self.percentage_bar.setStyleSheet("background-color: #FF9800; border-radius: 3px;")
        else:
            # Denied (red)
            self.percentage_bar.setStyleSheet("background-color: #F44336; border-radius: 3px;")

class AdminAttendanceOverviewWidget(QWidget):
    """Widget for admin to see attendance overview of all students"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # Title with tooltip explanation
        title = QLabel("Course Attendance Overview")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        title.setToolTip("Shows the number of students in each attendance category")
        layout.addWidget(title)
        
        # Summary statistics with enhanced visualization
        summary_layout = QHBoxLayout()
        
        # Good standing students (>=90%)
        self.good_frame = self.create_summary_frame("Good Standing\n≥ 90%", "#4CAF50")
        summary_layout.addWidget(self.good_frame)
        
        # Warning level students (85-90%)
        self.warning_frame = self.create_summary_frame("Warning\n85-90%", "#FFC107")
        summary_layout.addWidget(self.warning_frame)
        
        # At risk students (80-85%)
        self.risk_frame = self.create_summary_frame("At Risk\n80-85%", "#FF9800")
        summary_layout.addWidget(self.risk_frame)
        
        # Denied students (<80%)
        self.denied_frame = self.create_summary_frame("Denied\n< 80%", "#F44336")
        summary_layout.addWidget(self.denied_frame)
        
        layout.addLayout(summary_layout)
        
        # Add threshold explanation
        threshold_info = QLabel("Students are denied from courses when absences exceed 20% of total classes")
        threshold_info.setAlignment(Qt.AlignCenter)
        threshold_info.setStyleSheet("color: #555; font-style: italic; margin-top: 10px;")
        layout.addWidget(threshold_info)
    
    def create_summary_frame(self, title, color):
        """Create a summary frame with count of students in each category"""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet(f"background-color: {color}; border-radius: 5px;")
        frame.setMinimumWidth(120)
        frame.setMinimumHeight(90)  # Increased height
        
        layout = QVBoxLayout(frame)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: white; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setWordWrap(True)
        
        count_label = QLabel("0")
        count_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        count_label.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(title_label)
        layout.addWidget(count_label)
        
        # Store the count label for later updates
        frame.count_label = count_label
        
        return frame
    
    def update_data(self, attendance_summary):
        """Update the summary frames with counts
        
        attendance_summary should be a dict with:
        - good_count: int
        - warning_count: int
        - risk_count: int
        - denied_count: int
        """
        # Animate the count changes for a more engaging UI
        good_count = attendance_summary.get('good_count', 0)
        warning_count = attendance_summary.get('warning_count', 0)
        risk_count = attendance_summary.get('risk_count', 0)
        denied_count = attendance_summary.get('denied_count', 0)
        
        # Update with bold highlighting for non-zero counts
        if good_count > 0:
            self.good_frame.count_label.setText(f"<b>{good_count}</b>")
        else:
            self.good_frame.count_label.setText("0")
            
        if warning_count > 0:
            self.warning_frame.count_label.setText(f"<b>{warning_count}</b>")
        else:
            self.warning_frame.count_label.setText("0")
            
        if risk_count > 0:
            self.risk_frame.count_label.setText(f"<b>{risk_count}</b>")
        else:
            self.risk_frame.count_label.setText("0")
            
        if denied_count > 0:
            self.denied_frame.count_label.setText(f"<b>{denied_count}</b>")
            # Make denied count more noticeable if there are denied students
            self.denied_frame.setStyleSheet("background-color: #F44336; border-radius: 5px; border: 2px solid yellow;")
        else:
            self.denied_frame.count_label.setText("0")
            self.denied_frame.setStyleSheet("background-color: #F44336; border-radius: 5px;")
