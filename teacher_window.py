import cv2
import datetime
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QApplication,
    QLabel, QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QDateEdit, QCheckBox, QGroupBox,
    QScrollArea, QFormLayout, QLineEdit, QRadioButton, QButtonGroup,
    QListWidget, QListWidgetItem, QProgressBar, QTimeEdit, QFileDialog
)
from PyQt5.QtCore import Qt, QDate, QTimer, pyqtSlot, QRect, QTime
from PyQt5.QtGui import QFont, QImage, QPixmap, QPainter, QPen, QColor, QBrush, QTextCharFormat
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from attendance_widgets import TeacherAttendanceWidget
from attendance_tracker import AttendanceTracker

from config import (STATUS_PRESENT, STATUS_ABSENT, STATUS_LATE,
                   STATUS_NA, STATUS_UNAUTHORIZED_DEPARTURE, LATE_THRESHOLD)


class AttendanceStatsChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Create a figure and canvas for matplotlib
        self.figure = Figure(figsize=(8, 5), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        layout.addWidget(self.canvas)

    def plot_attendance_pie_chart(self, stats_data):
        """Plot a pie chart of attendance statistics"""
        self.figure.clear()

        # Get the axes and plot the pie chart
        ax = self.figure.add_subplot(111)

        # Extract data for the pie chart
        labels = []
        sizes = []
        colors = []

        status_counts = stats_data.get('status_counts', {})

        if STATUS_PRESENT in status_counts:
            labels.append('Present')
            sizes.append(status_counts[STATUS_PRESENT])
            colors.append('green')

        if STATUS_LATE in status_counts:
            labels.append('Late')
            sizes.append(status_counts[STATUS_LATE])
            colors.append('orange')

        if STATUS_ABSENT in status_counts:
            labels.append('Absent')
            sizes.append(status_counts[STATUS_ABSENT])
            colors.append('red')

        if STATUS_UNAUTHORIZED_DEPARTURE in status_counts:
            labels.append('Unauthorized\nDeparture')
            sizes.append(status_counts[STATUS_UNAUTHORIZED_DEPARTURE])
            colors.append('purple')


        # Only plot if we have data
        if sizes:
            ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
            ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
            ax.set_title('Attendance Distribution')
        else:
            ax.text(0.5, 0.5, 'No attendance data available',
                    horizontalalignment='center', verticalalignment='center',
                    fontsize=12)

        self.canvas.draw()

    def plot_attendance_bar_chart(self, stats_data):
        """Plot a bar chart showing attendance trends"""
        self.figure.clear()

        # Get the axes and plot the bar chart
        ax = self.figure.add_subplot(111)

        # Extract data for the bar chart
        if 'attendance_by_date' in stats_data:
            dates = list(stats_data['attendance_by_date'].keys())
            present_counts = [data.get(STATUS_PRESENT, 0) for data in stats_data['attendance_by_date'].values()]
            late_counts = [data.get(STATUS_LATE, 0) for data in stats_data['attendance_by_date'].values()]

            # Ensure dates are in chronological order
            sorted_items = sorted(zip(dates, present_counts, late_counts), key=lambda x: x[0])
            dates = [item[0] for item in sorted_items]
            present_counts = [item[1] for item in sorted_items]
            late_counts = [item[2] for item in sorted_items]

            # Plot data
            x = range(len(dates))
            width = 0.35

            ax.bar([i - width/2 for i in x], present_counts, width, label='Present', color='green')
            ax.bar([i + width/2 for i in x], late_counts, width, label='Late', color='orange')

            ax.set_xlabel('Date')
            ax.set_ylabel('Number of Students')
            ax.set_title('Attendance Trends')
            ax.set_xticks(x)
            ax.set_xticklabels(dates, rotation=45, ha='right')
            ax.legend()

            self.figure.tight_layout()
        else:
            ax.text(0.5, 0.5, 'No attendance trend data available',
                    horizontalalignment='center', verticalalignment='center',
                    fontsize=12)

        self.canvas.draw()

class CourseDateValidator:
    @staticmethod
    def setup_date_filter(date_edit, course, database):
        """
        Configure a QDateEdit widget to only allow dates that are valid for a course.
        Valid dates match the course days and fall within the course's start and end dates.

        Args:
            date_edit: QDateEdit widget to configure
            course: Course data tuple from database
            database: Database instance for additional queries
        """
        from PyQt5.QtCore import QDate, Qt
        from PyQt5.QtGui import QTextCharFormat, QBrush, QColor

        # Extract course info
        course_id = course[0]
        course_days = course[10]
        start_date_str = course[8] if len(course) > 8 else None
        end_date_str = course[9] if len(course) > 9 else None

        # Convert day abbreviations to numbers (PyQt uses 1=Monday, 7=Sunday)
        day_map = {
            'Mon': 1,   # Monday
            'Tue': 2,   # Tuesday
            'Wed': 3,   # Wednesday
            'Thu': 4,   # Thursday
            'Fri': 5,   # Friday
            'Sat': 6,   # Saturday
            'Sun': 7    # Sunday
        }

        # Parse days string to get allowed days of week
        allowed_days = []
        for day_abbr, day_num in day_map.items():
            if day_abbr in course_days:
                allowed_days.append(day_num)

        # Parse start and end dates
        start_date = QDate.fromString(start_date_str, "yyyy-MM-dd") if start_date_str else QDate.currentDate().addYears(-1)
        end_date = QDate.fromString(end_date_str, "yyyy-MM-dd") if end_date_str else QDate.currentDate().addYears(1)

        def date_filter(date):
            # Check if date is within range
            if date < start_date or date > end_date:
                return False

            # Check if day of week matches course days
            if date.dayOfWeek() not in allowed_days:
                return False

            return True

        # Set the date range
        date_edit.setDateRange(start_date, end_date)

        # Create the special formats
        # Format for INVALID dates - grey them out
        disabled_format = QTextCharFormat()
        disabled_format.setForeground(Qt.lightGray)
        disabled_format.setBackground(QBrush(QColor(200, 200, 200, 100)))

        # Format for VALID dates - highlight them (optional)
        valid_format = QTextCharFormat()
        valid_format.setForeground(Qt.black)
        valid_format.setBackground(QBrush(QColor(230, 240, 250)))

        # Reset any existing formats
        calendar_widget = date_edit.calendarWidget()

        # Get all dates in the range and apply formats
        total_days = start_date.daysTo(end_date) + 1
        for day in range(total_days):
            current_date = start_date.addDays(day)

            # Apply appropriate format based on validity
            if date_filter(current_date):
                # Valid date - use valid format or leave as default
                calendar_widget.setDateTextFormat(current_date, valid_format)
            else:
                # Invalid date - grey it out
                calendar_widget.setDateTextFormat(current_date, disabled_format)

        # Set initial date to current date if valid, otherwise find next valid date
        current_date = QDate.currentDate()
        if date_filter(current_date):
            date_edit.setDate(current_date)
        else:
            # Find the next valid date
            test_date = current_date
            while not date_filter(test_date) and test_date <= end_date:
                test_date = test_date.addDays(1)

            if test_date <= end_date:
                date_edit.setDate(test_date)
            else:
                # If no future valid date, try to find a past valid date
                test_date = current_date
                while not date_filter(test_date) and test_date >= start_date:
                    test_date = test_date.addDays(-1)

                if test_date >= start_date:
                    date_edit.setDate(test_date)
                else:
                    # No valid dates found
                    date_edit.setDate(current_date)

        # Custom date selection handler
        def handle_date_selected(date):
            if not date_filter(date):
                # If invalid date, find the next valid date
                next_date = date
                max_attempts = 100  # Avoid infinite loop
                attempts = 0

                while not date_filter(next_date) and attempts < max_attempts:
                    next_date = next_date.addDays(1)
                    attempts += 1

                if attempts < max_attempts:
                    date_edit.setDate(next_date)
                    return

                # If no future valid date found, try past dates
                prev_date = date
                attempts = 0

                while not date_filter(prev_date) and attempts < max_attempts:
                    prev_date = prev_date.addDays(-1)
                    attempts += 1

                if attempts < max_attempts:
                    date_edit.setDate(prev_date)

        # Connect to the date selection
        date_edit.dateChanged.connect(handle_date_selected)

        # Return the filter function for use in other contexts
        return date_filter

class ChangePasswordDialog(QDialog):
    def __init__(self, parent, database, user_id):
        super().__init__(parent)

        self.database = database
        self.user_id = user_id

        self.setWindowTitle("Change Password")
        self.setMinimumWidth(300)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        form_layout = QFormLayout()

        self.current_password = QLineEdit()
        self.current_password.setEchoMode(QLineEdit.Password)

        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.Password)

        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.Password)

        form_layout.addRow("Current Password:", self.current_password)
        form_layout.addRow("New Password:", self.new_password)
        form_layout.addRow("Confirm Password:", self.confirm_password)

        layout.addLayout(form_layout)

        # Buttons
        buttons_layout = QHBoxLayout()

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_password)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        layout.addLayout(buttons_layout)

    def save_password(self):
        current_password = self.current_password.text()
        new_password = self.new_password.text()
        confirm_password = self.confirm_password.text()

        if not current_password or not new_password or not confirm_password:
            QMessageBox.warning(self, "Input Error", "Please fill in all fields.")
            return

        if new_password != confirm_password:
            QMessageBox.warning(self, "Input Error", "New passwords do not match.")
            return

        # Check current password
        user_info = self.database.authenticate_by_id(self.user_id, current_password)
        if not user_info:
            QMessageBox.warning(self, "Authentication Error", "Current password is incorrect.")
            return

        # Update password
        self.database.update_user(
            self.user_id,
            None,  # No username change
            new_password,
            None,  # No name change
            None,  # No role change
            None   # No face encoding change
        )

        QMessageBox.information(self, "Success", "Password changed successfully.")
        self.accept()

class StudentImageDialog(QDialog):
    def __init__(self, parent, student_id, student_name, face_recognition_system, course_id=None):
        super().__init__(parent)

        self.database = parent.database
        self.face_recognition_system = face_recognition_system
        self.course_id = course_id

        self.setWindowTitle(f"Student Image: {student_name}")
        self.setMinimumSize(400, 600)

        layout = QVBoxLayout(self)

        # Add student name at the top
        name_label = QLabel(student_name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(name_label)

        # Image display
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(320, 320)
        self.image_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        layout.addWidget(self.image_label)

        # Student info
        info_group = QGroupBox("Student Information")
        info_layout = QFormLayout(info_group)

        # Get student info
        student_data = self.database.get_user_by_id(student_id)
        if student_data:
            username_label = QLabel(student_data[1])
            name_label = QLabel(student_data[3])

            # Get attendance statistics for this student
            attendance_stats = self.get_attendance_stats(student_id)

            present_count = attendance_stats.get(STATUS_PRESENT, 0)
            absent_count = attendance_stats.get(STATUS_ABSENT, 0)
            late_count = attendance_stats.get(STATUS_LATE, 0)
            unauthorized_departure = attendance_stats.get(STATUS_UNAUTHORIZED_DEPARTURE, 0)
            total = present_count + absent_count + late_count + unauthorized_departure

            attendance_rate = f"{present_count}/{total}" if total > 0 else "N/A"

            # Add attendance chart
            if course_id:
                # For specific course
                attendance_chart = AttendanceStatsChart()
                stats_data = self.database.get_student_attendance_stats(student_id, course_id)
                status_counts = {status: count for status, count in stats_data.items() if status != 'total_days'}
                chart_data = {'status_counts': status_counts}
                attendance_chart.plot_attendance_pie_chart(chart_data)
                layout.addWidget(attendance_chart)

            info_layout.addRow("Username:", username_label)
            info_layout.addRow("Full Name:", name_label)
            info_layout.addRow("Present Days:", QLabel(str(present_count)))
            info_layout.addRow("Late Days:", QLabel(str(late_count)))
            info_layout.addRow("Absent Days:", QLabel(str(absent_count)))
            info_layout.addRow("Unauthorized Departures:", QLabel(str(unauthorized_departure)))
            info_layout.addRow("Attendance Rate:", QLabel(attendance_rate))

        layout.addWidget(info_group)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)

        # Try to get student's face image
        if student_data and len(student_data) > 6 and student_data[6]:  # Check for face_image at index 6
            try:
                img_data = student_data[6]  # Get the binary image data

                # Convert to QImage
                image = QImage()
                image.loadFromData(img_data)

                # Create a pixmap and set it to the label
                pixmap = QPixmap.fromImage(image)
                pixmap = pixmap.scaled(320, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_label.setPixmap(pixmap)

                # Add "Face ID Registered" text overlay
                overlay = QLabel(self.image_label)
                overlay.setText("Face ID Registered")
                overlay.setStyleSheet(
                    "background-color: rgba(0, 0, 0, 120); color: white; "
                    "font-weight: bold; padding: 5px;"
                )
                overlay.setAlignment(Qt.AlignCenter)
                overlay.resize(320, 30)
                overlay.move(0, 290)  # Position at bottom of image
                overlay.show()

                return
            except Exception as e:
                print(f"Error loading image: {e}")
                # Fall through to default image if there's an error

        # If we don't have stored image or there was an error, check if there's a face encoding
        if student_data and len(student_data) > 5 and student_data[5]:  # Check for face_encoding
            # Create a placeholder face image (a green circle with a face icon)
            pixmap = QPixmap(320, 320)
            pixmap.fill(Qt.transparent)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)

            # Draw green background circle
            painter.setBrush(QColor("#e0f0e0"))
            painter.setPen(QPen(QColor("#60a060"), 2))
            painter.drawEllipse(30, 30, 260, 260)

            # Draw a simple face
            painter.setPen(QPen(QColor("#308030"), 4))
            # Draw a smile
            painter.drawArc(90, 120, 140, 100, 45 * 16, 90 * 16)
            # Draw eyes
            painter.drawEllipse(110, 100, 30, 30)
            painter.drawEllipse(180, 100, 30, 30)

            painter.end()

            # Set the image
            self.image_label.setPixmap(pixmap)

            # Add text label on the image
            text_label = QLabel("Face ID Registered", self.image_label)
            text_label.setAlignment(Qt.AlignCenter)
            text_label.setStyleSheet("color: #308030; font-weight: bold; font-size: 14px;")
            text_label.move(100, 280)  # Position at bottom of image
            text_label.show()
        else:
            # Create a placeholder for no face registered (red circle with X)
            pixmap = QPixmap(320, 320)
            pixmap.fill(Qt.transparent)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)

            # Draw red background circle
            painter.setBrush(QColor("#f0e0e0"))
            painter.setPen(QPen(QColor("#a06060"), 2))
            painter.drawEllipse(30, 30, 260, 260)

            # Draw X
            painter.setPen(QPen(QColor("#803030"), 4))
            painter.drawLine(90, 90, 230, 230)
            painter.drawLine(90, 230, 230, 90)

            painter.end()

            # Set the image
            self.image_label.setPixmap(pixmap)

            # Add text label on the image
            text_label = QLabel("No Face ID Registered", self.image_label)
            text_label.setAlignment(Qt.AlignCenter)
            text_label.setStyleSheet("color: #803030; font-weight: bold; font-size: 14px;")
            text_label.move(80, 280)  # Position at bottom of image
            text_label.show()

    def get_attendance_stats(self, student_id):
        """Get attendance statistics for a student"""
        try:
            # Get all attendance records for this student
            self.database.cursor.execute(
                """
                SELECT status FROM attendance
                WHERE student_id = ?
                """,
                (student_id,)
            )
            records = self.database.cursor.fetchall()

            # Count occurrences of each status
            stats = {}
            for record in records:
                status = record[0]
                if status in stats:
                    stats[status] += 1
                else:
                    stats[status] = 1

            return stats
        except:
            return {}

class CancelLectureDialog(QDialog):
    def __init__(self, parent, database, course_id):
        super().__init__(parent)

        self.database = database
        self.course_id = course_id

        # Get course details
        self.course = self.database.get_course_by_id(course_id)
        self.course_name = self.course[2]
        self.course_code = self.course[1]
        self.course_section = self.course[3]
        self.reference_number = course_id

        self.setWindowTitle(f"Cancel Lecture - {self.course_code} {self.course_name}: {self.course_section}")
        self.setMinimumWidth(400)

        self.init_ui()

        # Set up date filter for the date edit widget
        self.date_filter = CourseDateValidator.setup_date_filter(self.date_edit, self.course, self.database)

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Heading
        heading = QLabel(f"Cancel Lecture for {self.course_code} {self.course_name}: {self.course_section}")
        heading.setFont(QFont("Arial", 12, QFont.Bold))
        heading.setAlignment(Qt.AlignCenter)
        heading.setWordWrap(True)
        layout.addWidget(heading)

        # Explanation
        explanation = QLabel("This will mark all students as 'N/A' for attendance for today's lecture.")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignCenter)
        layout.addWidget(explanation)

        # Date selection
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Date:"))

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        date_layout.addWidget(self.date_edit)

        layout.addLayout(date_layout)

        # Reason for cancellation
        layout.addWidget(QLabel("Reason for cancellation:"))
        self.reason_edit = QLineEdit()
        layout.addWidget(self.reason_edit)

        # Buttons
        buttons_layout = QHBoxLayout()

        cancel_lecture_button = QPushButton("Cancel Lecture")
        cancel_lecture_button.clicked.connect(self.cancel_lecture)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.reject)

        buttons_layout.addWidget(cancel_lecture_button)
        buttons_layout.addWidget(close_button)

        layout.addLayout(buttons_layout)

    def cancel_lecture(self):
        date = self.date_edit.date().toString("yyyy-MM-dd")

        # Confirm with the user
        reply = QMessageBox.question(
            self,
            "Confirm Cancellation",
            f"Are you sure you want to cancel the lecture for {self.course_code} {self.course_name}: {self.course_section} on {date}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            success = self.database.cancel_lecture(self.course_id, date)

            if success:
                QMessageBox.information(
                    self,
                    "Success",
                    f"Lecture for {self.course_code} {self.course_name}: {self.course_section} on {date} has been cancelled."
                )
                self.accept()
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "Failed to cancel lecture. Please try again."
                )

class CameraWidget(QWidget):
    def __init__(self, face_recognition_system, database, course_id):
        super().__init__()

        self.face_recognition_system = face_recognition_system
        self.database = database
        self.course_id = course_id

        # Get course info
        self.course = self.database.get_course_by_id(course_id)
        self.course_name = self.course[2]
        self.course_code = self.course[1]
        self.course_section = self.course[3]
        self.classroom = self.course[7]
        self.reference_number = course_id

        self.camera_active = False
        self.camera = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        self.recognized_students = []

        # Check for custom end time
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        self.custom_end_time = self.database.get_custom_end_time(course_id, today)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Course info header
        course_info_layout = QHBoxLayout()

        # Current date and time
        self.datetime_label = QLabel()
        self.datetime_label.setFont(QFont("Arial", 10))
        self.update_datetime()

        # Update datetime every second
        self.datetime_timer = QTimer()
        self.datetime_timer.timeout.connect(self.update_datetime)
        self.datetime_timer.start(1000)

        # Course info
        course_label = QLabel(f"{self.course_code} {self.course_name}: {self.course_section} | Room: {self.classroom}")
        course_label.setFont(QFont("Arial", 10, QFont.Bold))
        course_label.setAlignment(Qt.AlignCenter)

        course_info_layout.addWidget(self.datetime_label)
        course_info_layout.addStretch()
        course_info_layout.addWidget(course_label)
        course_info_layout.addStretch()

        # Add end time label
        self.end_time_label = QLabel()
        self.end_time_label.setFont(QFont("Arial", 10))
        self.update_end_time()
        course_info_layout.addWidget(self.end_time_label)

        layout.addLayout(course_info_layout)

        # Early dismissal status indicator (if applicable)
        if self.early_dismissal_time:
            early_dismissal_label = QLabel(f"Lecture dismissed early at {self.early_dismissal_time}")
            early_dismissal_label.setStyleSheet("color: red; font-weight: bold;")
            early_dismissal_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(early_dismissal_label)

            warning_label = QLabel("Attendance no longer being recorded for this session")
            warning_label.setStyleSheet("color: red;")
            warning_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(warning_label)

        # Camera feed label
        self.camera_label = QLabel()
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setStyleSheet("background-color: black;")

        # Controls
        controls_layout = QHBoxLayout()

        self.start_button = QPushButton("Start Camera")
        self.start_button.clicked.connect(self.toggle_camera)

        # Mark Attendance button
        self.mark_attendance_button = QPushButton("Mark Attendance")
        self.mark_attendance_button.clicked.connect(self.mark_attendance)
        self.mark_attendance_button.setEnabled(False)  # Disabled until camera starts

        # End lecture early button
        self.end_lecture_button = QPushButton("End Lecture Early")
        self.end_lecture_button.clicked.connect(self.end_lecture_early)
        self.end_lecture_button.setDisabled(self.early_dismissal_time is not None)

        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.mark_attendance_button)
        controls_layout.addWidget(self.end_lecture_button)

        # Recognition results
        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["Student ID", "Name", "Status"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Add double-click event to show student image
        self.results_table.doubleClicked.connect(self.show_student_image)

        # Add widgets to layout
        layout.addWidget(self.camera_label)
        layout.addLayout(controls_layout)
        layout.addWidget(QLabel("Recognition Results:"))
        layout.addWidget(self.results_table)

    def update_datetime(self):
        now = datetime.datetime.now()
        self.datetime_label.setText(f"Date: {now.strftime('%Y-%m-%d')} | Time: {now.strftime('%H:%M:%S')}")

    def update_end_time(self):
        """Update the end time displayed in the UI"""
        # Get end time from course - check if lecture has custom end time today
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        custom_end_time = self.database.get_custom_end_time(self.course_id, today)

        if custom_end_time:
            time_obj = datetime.datetime.strptime(custom_end_time, "%H:%M:%S").time()
            custom_end_display = time_obj.strftime("%H:%M")
            self.end_time_label.setText(f"Scheduled End: {self.course[5]} | Today's End: {custom_end_display}")
            self.end_time_label.setStyleSheet("color: blue;")
        else:
            self.end_time_label.setText(f"End Time: {self.course[5]}")
            self.end_time_label.setStyleSheet("")

    def toggle_camera(self):
        if self.camera_active:
            self.stop_camera()
        else:
            self.start_camera()

    def start_camera(self):
        try:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                raise Exception("Could not open camera")

            self.camera_active = True
            self.timer.start(30)  # Update every 30ms (approx 33 fps)
            self.start_button.setText("Stop Camera")
            self.mark_attendance_button.setEnabled(True)
            self.end_lecture_button.setDisabled(self.early_dismissal_time is not None)
        except Exception as e:
            QMessageBox.warning(self, "Camera Error", f"Could not start camera: {str(e)}")

    def stop_camera(self):
        if self.camera is not None:
            self.timer.stop()
            self.camera.release()
            self.camera = None

        self.camera_active = False
        self.start_button.setText("Start Camera")
        self.mark_attendance_button.setEnabled(False)
        self.end_lecture_button.setDisabled(self.early_dismissal_time is not None)

        # Clear the camera label
        self.camera_label.clear()
        self.camera_label.setStyleSheet("background-color: black;")

    def update_frame(self):
        ret, frame = self.camera.read()
        if not ret:
            self.stop_camera()
            QMessageBox.warning(self, "Camera Error", "Failed to capture frame.")
            return

        # Process the frame for face recognition
        recognition_results = self.face_recognition_system.recognize_faces(frame, self.course_id)

        # Update the list of recognized students
        if recognition_results['recognized']:
            self.recognized_students = recognition_results['recognized']
            self.update_results_table()

        # Draw results on frame
        frame = self.face_recognition_system.draw_recognition_results(frame, recognition_results)

        # Add course info overlay
        now = datetime.datetime.now()
        date_text = now.strftime("%Y-%m-%d")
        time_text = now.strftime("%H:%M:%S")
        course_text = f"{self.course_code} {self.course_name}: {self.course_section} | Room: {self.classroom}"

        # Create a dark overlay for text
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 50), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame, 0)

        # Add text
        cv2.putText(frame, f"Date: {date_text} | Time: {time_text}", (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, course_text, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        # Add custom end time notification if applicable
        if self.custom_end_time:
            time_obj = datetime.datetime.strptime(self.custom_end_time, "%H:%M:%S").time()
            custom_end_display = time_obj.strftime("%H:%M")
            end_time_text = f"Today's End Time: {custom_end_display}"
            cv2.rectangle(frame, (0, frame.shape[0]-30), (frame.shape[1], frame.shape[0]), (70, 130, 180), -1) # Blue color
            cv2.putText(frame, end_time_text, (10, frame.shape[0]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Convert frame to QImage and display
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.camera_label.setPixmap(QPixmap.fromImage(qt_image).scaled(
            self.camera_label.width(), self.camera_label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def update_results_table(self):
        self.results_table.setRowCount(0)
        for student in self.recognized_students:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            self.results_table.setItem(row, 0, QTableWidgetItem(student['student_id']))
            self.results_table.setItem(row, 1, QTableWidgetItem(student['name']))
            self.results_table.setItem(row, 2, QTableWidgetItem("Detected"))

    def mark_attendance(self):
        if self.early_dismissal_time:
            QMessageBox.warning(self, "Cannot Mark Attendance", "Lecture has ended early. Attendance cannot be marked.")
            return

        # Get the current recognized student
        if not self.recognized_students:
            QMessageBox.warning(self, "No Student Detected", "Please position your face in front of the camera.")
            return

        # Get the most recently recognized student
        student = self.recognized_students[-1]
        student_id = student['student_id']
        name = student['name']

        # Mark attendance
        now = datetime.datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")

        # Check if already marked attendance
        self.database.cursor.execute(
            "SELECT time FROM attendance WHERE student_id = ? AND course_id = ? AND date = ?",
            (student_id, self.course_id, today)
        )
        result = self.database.cursor.fetchone()

        if result:
            QMessageBox.information(self, "Already Marked", f"Attendance already marked for {name}")
            return

        # Determine status based on time
        course_start = datetime.datetime.strptime(self.course[4], "%H:%M").time()
        late_threshold = (datetime.datetime.combine(now.date(), course_start) +
                         datetime.timedelta(minutes=15)).time()
        current_time_obj = now.time()

        status = "Late" if current_time_obj > late_threshold else "Present"

        # Insert attendance record
        self.database.cursor.execute(
            "INSERT INTO attendance (student_id, course_id, date, time, status) VALUES (?, ?, ?, ?, ?)",
            (student_id, self.course_id, today, current_time, status)
        )
        self.database.conn.commit()

        QMessageBox.information(self, "Success", f"Marked {name} as {status}")
        self.update_results_table()

    def end_lecture_early(self):
        """End the lecture early by setting a custom end time for today"""
        dialog = EndLectureDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            end_time = dialog.time_edit.time().toString("HH:mm:ss")
            today = datetime.datetime.now().strftime("%Y-%m-%d")

            # Update database with custom end time
            success = self.database.end_lecture_early(self.course_id, today, end_time)

            if success:
                # Store the custom end time
                self.custom_end_time = end_time
                # Update UI
                self.update_end_time()

                QMessageBox.information(self, "End Time Updated",
                                       f"The lecture end time for today has been set to {end_time}.")
            else:
                QMessageBox.warning(self, "Error", "Failed to update lecture end time.")

    def show_student_image(self):
        if not self.recognized_students:
            return

        # Get the selected row
        selected_items = self.results_table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        student = self.recognized_students[row]
        student_id = student['student_id']
        name = student['name']

        # Show the student image dialog
        dialog = StudentImageDialog(self, student_id, name, self.face_recognition_system, self.course_id)
        dialog.exec_()

    def closeEvent(self, event):
        # Clean up resources when the widget is closed
        self.stop_camera()
        event.accept()

class ManualAttendanceWidget(QWidget):
    def __init__(self, database, course_id):
        super().__init__()

        self.database = database
        self.course_id = course_id
        self.auto_save_timer = None
        self.pending_saves = set()
        self.last_saved_statuses = {}  # Track last saved status for each student
        self.lecture_cancelled = False  # Track if lecture is cancelled

        # Get course info
        self.course = self.database.get_course_by_id(course_id)
        self.course_name = self.course[2]
        self.course_code = self.course[1]
        self.course_section = self.course[3]
        self.reference_number = course_id

        # Get custom end time if it exists
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        self.custom_end_time = self.database.get_custom_end_time(course_id, today)

        self.init_ui()

        # Set up date filter for the date edit widget
        self.date_filter = CourseDateValidator.setup_date_filter(self.date_edit, self.course, self.database)
        self.date_edit.dateChanged.connect(self.on_date_changed)

        # Load all enrolled students
        self.load_students()
        
        # Setup timer to update time
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)  # Update every second
        
        # Load existing attendance records for today
        self.load_existing_attendance()
        
        # Setup auto-save timer
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self.process_pending_saves)
        self.auto_save_timer.start(2000)  # Save changes every 2 seconds

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Course info header
        course_header = QLabel(f"{self.course_code} {self.course_name}: {self.course_section}")
        course_header.setFont(QFont("Arial", 12, QFont.Bold))
        course_header.setAlignment(Qt.AlignCenter)
        layout.addWidget(course_header)

        # Date and time selection
        date_time_layout = QHBoxLayout()

        # Date selection
        date_layout = QVBoxLayout()
        date_layout.addWidget(QLabel("Date:"))

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        date_layout.addWidget(self.date_edit)

        date_time_layout.addLayout(date_layout)
        date_time_layout.addStretch()

        # Time input
        time_layout = QVBoxLayout()
        time_layout.addWidget(QLabel("Current Time:"))

        # Add current time
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M:%S")

        self.time_label = QLabel(current_time)
        self.time_label.setStyleSheet("font-weight: bold;")
        time_layout.addWidget(self.time_label)

        date_time_layout.addLayout(time_layout)

        # Add status indicator
        self.status_indicator = QLabel("Ready")
        self.status_indicator.setStyleSheet("color: green;")
        date_time_layout.addWidget(self.status_indicator)

        layout.addLayout(date_time_layout)

        # Custom end time display (if applicable)
        if self.custom_end_time:
            end_time_layout = QHBoxLayout()
            end_time_label = QLabel("Custom End Time:")
            end_time_value = QLabel(self.custom_end_time)
            end_time_value.setStyleSheet("color: blue; font-weight: bold;")
            end_time_layout.addWidget(end_time_label)
            end_time_layout.addWidget(end_time_value)
            layout.addLayout(end_time_layout)

        # Add status indicator
        self.status_indicator = QLabel("Ready")
        self.status_indicator.setStyleSheet("color: green;")
        date_time_layout.addWidget(self.status_indicator)

        layout.addLayout(date_time_layout)

        # Student search section
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search Students:"))

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type student name or ID...")
        self.search_input.textChanged.connect(self.filter_students)
        
        # Clear search button
        clear_button = QPushButton("Clear")
        clear_button.clicked.connect(self.clear_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(clear_button)

        layout.addLayout(search_layout)

        # Single list of students with status dropdown
        self.students_table = QTableWidget(0, 3)  # ID, Name, Status
        self.students_table.setHorizontalHeaderLabels(["ID", "Name", "Status"])
        self.students_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.students_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.students_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.students_table.setMinimumHeight(300)
        layout.addWidget(self.students_table)

        # Buttons layout
        buttons_layout = QHBoxLayout()

        # Cancel lecture button
        cancel_lecture_button = QPushButton("Cancel Lecture")
        cancel_lecture_button.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        cancel_lecture_button.clicked.connect(self.cancel_lecture)
        
        # End lecture early button
        self.end_lecture_button = QPushButton("End Lecture Early")
        self.end_lecture_button.setStyleSheet("background-color: #ff9800; color: white; font-weight: bold;")
        self.end_lecture_button.clicked.connect(self.end_lecture_early)
        
        buttons_layout.addWidget(cancel_lecture_button)
        buttons_layout.addWidget(self.end_lecture_button)
        
        layout.addLayout(buttons_layout)
        
        # Information label for auto-save
        auto_save_info = QLabel("Changes are automatically saved. No need to manually save.")
        auto_save_info.setStyleSheet("color: #666; font-style: italic;")
        auto_save_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(auto_save_info)

    def end_lecture_early(self):
        """End the lecture early for the current date by setting a custom end time"""
        date = self.date_edit.date().toString("yyyy-MM-dd")

        # Check if lecture is already cancelled
        if self.lecture_cancelled:
            QMessageBox.warning(self, "Cannot Update End Time", "Lecture has already been cancelled.")
            return

        # Create and show the end lecture dialog
        dialog = EndLectureDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            end_time = dialog.time_edit.time().toString("HH:mm:ss")

            try:
                # Update database with custom end time
                success = self.database.end_lecture_early(self.course_id, date, end_time)

                if success:
                    # Update UI
                    self.status_indicator.setText(f"Custom end time set: {end_time}")
                    self.status_indicator.setStyleSheet("color: blue; font-weight: bold;")

                    QMessageBox.information(self, "Success", f"Lecture end time updated to {end_time}")

                else:
                    QMessageBox.critical(self, "Error", "Failed to update lecture end time")

            except Exception as e:
                print(f"Error setting custom end time: {e}")
                QMessageBox.critical(self, "Error", f"Failed to update lecture end time: {str(e)}")

    def update_time(self):
        """Update the current time display"""
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M:%S")
        self.time_label.setText(current_time)

    def load_students(self):
        """Load all enrolled students into the table with dropdown status selection"""
        # Get enrolled students
        self.enrolled_students = self.database.get_enrolled_students(self.course_id)
        
        # Clear table
        self.students_table.setRowCount(0)
        
        # Populate table with students
        for i, student in enumerate(self.enrolled_students):
            student_id = student[0]
            name = student[2]
            
            self.students_table.insertRow(i)
            self.students_table.setItem(i, 0, QTableWidgetItem(student_id))
            self.students_table.setItem(i, 1, QTableWidgetItem(name))
            
            # Create dropdown for status selection
            status_combo = QComboBox()
            status_combo.addItem(STATUS_PRESENT)
            status_combo.addItem(STATUS_ABSENT)
            status_combo.addItem(STATUS_LATE)
            status_combo.addItem(STATUS_UNAUTHORIZED_DEPARTURE)
            
            # Store a reference to the combo box
            setattr(self, f"status_combo_{student_id}", status_combo)
            
            # Connect combo box to auto-save
            status_combo.currentTextChanged.connect(lambda status, sid=student_id: self.on_status_changed(sid))
            
            # Add to table
            self.students_table.setCellWidget(i, 2, status_combo)

    def load_existing_attendance(self):
        """Load existing attendance records for the current date"""
        date = self.date_edit.date().toString("yyyy-MM-dd")

        # Reset lecture cancelled flag
        self.lecture_cancelled = False
        self.status_indicator.setText("Ready")
        self.status_indicator.setStyleSheet("color: green;")

        # Re-enable all dropdowns first
        for i in range(self.students_table.rowCount()):
            combo = self.students_table.cellWidget(i, 2)
            if combo and isinstance(combo, QComboBox):
                combo.setEnabled(True)

        # Check for custom end time
        custom_end_time = self.database.get_custom_end_time(self.course_id, date)
        if custom_end_time:
            self.status_indicator.setText(f"Custom end time: {custom_end_time}")
            self.status_indicator.setStyleSheet("color: blue;")

        # Check for cancel status - specifically for this course and date
        try:
            self.database.cursor.execute(
                """
                SELECT is_cancelled FROM attendance
                WHERE course_id = ? AND date = ? AND is_cancelled = 1
                LIMIT 1
                """,
                (self.course_id, date)
            )
            result = self.database.cursor.fetchone()

            if result and result[0] == 1:
                self.lecture_cancelled = True
                self.status_indicator.setText("Lecture Cancelled")
                self.status_indicator.setStyleSheet("color: red; font-weight: bold;")

                # Disable all controls if the lecture is cancelled
                for i in range(self.students_table.rowCount()):
                    combo = self.students_table.cellWidget(i, 2)
                    if combo and isinstance(combo, QComboBox):
                        combo.setEnabled(False)

                # Early return since we don't need to load individual statuses for cancelled lecture
                print(f"Lecture cancelled for course {self.course_id} on {date}")
                return
        except Exception as e:
            print(f"Error checking lecture cancelled status: {e}")

        # If we get here, the lecture is not cancelled
        # Get existing attendance records
        try:
            self.database.cursor.execute(
                """
                SELECT student_id, status FROM attendance
                WHERE course_id = ? AND date = ? AND is_cancelled = 0
                """,
                (self.course_id, date)
            )
            records = self.database.cursor.fetchall()

            print(f"Found {len(records)} attendance records for date {date}")

            # Update the UI to match existing records
            for student_id, status in records:
                print(f"Setting status for student {student_id} to {status}")
                self.set_student_status(student_id, status)
                # Update the last saved status
                self.last_saved_statuses[student_id] = status
        except Exception as e:
            print(f"Error loading existing attendance: {e}")

    def on_date_changed(self):
        """Handle date change by loading attendance for the new date"""
        # Reset all students to default status first
        for student in self.enrolled_students:
            student_id = student[0]
            self.set_student_status(student_id, STATUS_PRESENT)
        
        # Clear the last saved statuses
        self.last_saved_statuses = {}
        
        # Load attendance for the new date
        self.load_existing_attendance()

    def filter_students(self):
        """Filter the students table based on search text"""
        search_text = self.search_input.text().strip().lower()
        
        if not search_text:
            # Show all rows
            for row in range(self.students_table.rowCount()):
                self.students_table.setRowHidden(row, False)
            return
            
        # Hide rows that don't match the search text
        for row in range(self.students_table.rowCount()):
            student_id = self.students_table.item(row, 0).text().lower()
            name = self.students_table.item(row, 1).text().lower()
            
            if search_text in student_id or search_text in name:
                self.students_table.setRowHidden(row, False)
            else:
                self.students_table.setRowHidden(row, True)
    
    def clear_search(self):
        """Clear the search field and show all students"""
        self.search_input.clear()
        for row in range(self.students_table.rowCount()):
            self.students_table.setRowHidden(row, False)

    def on_status_changed(self, student_id):
        """Called when a student's status changes to queue auto-save"""
        if self.lecture_cancelled:
            # Don't allow changes if lecture is cancelled
            return
            
        current_status = self.get_student_status(student_id)
        
        # Print for debugging
        print(f"Status changed for student {student_id} to {current_status}")
        
        # Check if status has actually changed from what was last saved
        if student_id in self.last_saved_statuses and self.last_saved_statuses[student_id] == current_status:
            return
            
        # Add to pending saves
        self.pending_saves.add(student_id)
        self.status_indicator.setText("Changes pending...")
        self.status_indicator.setStyleSheet("color: orange;")
        
    def process_pending_saves(self):
        """Process all pending status changes"""
        if not self.pending_saves or self.lecture_cancelled:
            return
            
        date = self.date_edit.date().toString("yyyy-MM-dd")
        time = self.time_label.text()
        
        save_count = 0
        error_count = 0
        
        self.status_indicator.setText("Saving changes...")
        self.status_indicator.setStyleSheet("color: blue;")
        QApplication.processEvents()
        
        for student_id in list(self.pending_saves):
            status = self.get_student_status(student_id)
            
            try:
                # Mark attendance in database
                result = self.database.mark_attendance(student_id, self.course_id, date, time, status)
                if result:
                    save_count += 1
                    # Update last saved status
                    self.last_saved_statuses[student_id] = status
                    print(f"Successfully saved status {status} for student {student_id}")
                else:
                    error_count += 1
                    print(f"Failed to save status for student {student_id}")
            except Exception as e:
                print(f"Error saving attendance for student {student_id}: {e}")
                error_count += 1
                
            # Remove from pending list regardless of result
            self.pending_saves.discard(student_id)
        
        # Update status indicator
        if error_count == 0 and save_count > 0:
            self.status_indicator.setText(f"Saved {save_count} changes")
            self.status_indicator.setStyleSheet("color: green;")
        elif error_count > 0:
            self.status_indicator.setText(f"Saved {save_count}, {error_count} errors")
            self.status_indicator.setStyleSheet("color: red;")
        
        # Only reload parent window data if we actually saved something
        if save_count > 0:
            parent = self.window()
            if hasattr(parent, 'load_attendance_records'):
                parent.load_attendance_records()
        
    def set_student_status(self, student_id, status):
        """Set the status dropdown for a student"""
        status_combo = getattr(self, f"status_combo_{student_id}", None)
        if not status_combo:
            print(f"Status combo not found for student {student_id}")
            return
            
        # Block signals temporarily to prevent auto-save while setting up
        status_combo.blockSignals(True)
        
        # Find and set the index for the status
        index = status_combo.findText(status)
        if index >= 0:
            status_combo.setCurrentIndex(index)
            print(f"Set status for student {student_id} to {status} (index {index})")
        else:
            print(f"Could not find status '{status}' in combo box for student {student_id}")
            
        # Unblock signals
        status_combo.blockSignals(False)

    def get_student_status(self, student_id):
        """Get the selected status for a student"""
        status_combo = getattr(self, f"status_combo_{student_id}", None)
        if not status_combo:
            print(f"Status combo not found for student {student_id} when getting status")
            return STATUS_PRESENT  # Default if not found
            
        # Return the current text of the combo box
        status = status_combo.currentText()
        return status

    def cancel_lecture(self):
        """Cancel the lecture for the current date"""
        date = self.date_edit.date().toString("yyyy-MM-dd")

        # Confirm with the user
        reply = QMessageBox.question(
            self,
            "Confirm Cancellation",
            f"Are you sure you want to cancel the lecture for {self.course_code} {self.course_name}: {self.course_section} on {date}?\n\n"
            "This will mark all students as N/A and cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                print(f"Attempting to cancel lecture for course {self.course_id} on {date}")
                success = self.database.cancel_lecture(self.course_id, date)

                if success:
                    self.lecture_cancelled = True
                    self.status_indicator.setText("Lecture Cancelled")
                    self.status_indicator.setStyleSheet("color: red; font-weight: bold;")

                    # Disable all controls
                    for i in range(self.students_table.rowCount()):
                        combo = self.students_table.cellWidget(i, 2)
                        if combo and isinstance(combo, QComboBox):
                            combo.setEnabled(False)

                    QMessageBox.information(
                        self,
                        "Success",
                        f"Lecture for {date} has been cancelled."
                    )

                    # Reload parent window data if needed
                    parent = self.window()
                    if hasattr(parent, 'load_attendance_records'):
                        parent.load_attendance_records()

                    print(f"Successfully cancelled lecture for course {self.course_id} on {date}")
                else:
                    QMessageBox.warning(
                        self,
                        "Error",
                        "Failed to cancel lecture. Please try again."
                    )
                    print(f"Failed to cancel lecture for course {self.course_id} on {date}")
            except Exception as e:
                print(f"Error cancelling lecture: {e}")
                QMessageBox.critical(
                    self,
                    "Error",
                    f"An error occurred while cancelling the lecture: {str(e)}"
                )
    
    def closeEvent(self, event):
        """Clean up resources when widget is closed"""
        if hasattr(self, 'time_timer') and self.time_timer.isActive():
            self.time_timer.stop()
        if hasattr(self, 'auto_save_timer') and self.auto_save_timer.isActive():
            self.auto_save_timer.stop()
            
        # Process any remaining saves
        if self.pending_saves and not self.lecture_cancelled:
            self.process_pending_saves()
            
        event.accept()

class TeacherWindow(QMainWindow):
    def __init__(self, database, face_recognition_system, teacher_id):
        super().__init__()

        self.database = database
        self.face_recognition_system = face_recognition_system
        self.teacher_id = teacher_id
        self.attendance_tracker = AttendanceTracker(database)

        self.teacher_data = self.database.get_user_by_id(teacher_id)

        self.setWindowTitle(f"Teacher Panel - {self.teacher_data[3]}")
        self.setMinimumSize(800, 600)

        self.init_ui()
        self.load_courses()

    def init_ui(self):
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # Create tab widget
        tab_widget = QTabWidget()
        main_layout.addWidget(tab_widget)

        # Create tabs
        self.profile_tab = QWidget()
        self.manual_attendance_tab = QWidget()
        self.records_tab = QWidget()
        self.stats_tab = QWidget()
        self.student_tab = QWidget()

        tab_widget.addTab(self.profile_tab, "My Profile")
        tab_widget.addTab(self.manual_attendance_tab, "Manual Attendance")
        tab_widget.addTab(self.records_tab, "View Records")
        tab_widget.addTab(self.stats_tab, "Statistics")
        tab_widget.addTab(self.student_tab, "Student Attendance")

        # Set up each tab
        self.setup_profile_tab()
        self.setup_manual_attendance_tab()
        self.setup_records_tab()
        self.setup_stats_tab()
        self.setup_student_tab()

        # Logout button
        logout_button = QPushButton("Logout")
        logout_button.clicked.connect(self.logout)
        main_layout.addWidget(logout_button)

    def generate_attendance_report(self):
        """Generate a comprehensive attendance report for the selected course"""
        course_id = self.record_course_combo.currentData()
        if not course_id:
            QMessageBox.warning(self, "No Course Selected", "Please select a course to generate a report.")
            return

        # Get course details
        course = self.database.get_course_by_id(course_id)
        course_code = course[1]  # Code (since reference_number is at index 0)
        course_name = course[2]  # Name
        course_section = course[3]  # Section

        # Ask for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Attendance Report",
            f"Attendance_Report {course_code}-{course_section}.csv",
            "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            # Get all students enrolled in this course
            enrolled_students = self.database.get_enrolled_students(course_id)

            # Attendance statistics per student
            student_stats = []
            for student in enrolled_students:
                student_id = student[0]
                student_name = student[2]  # Name is at index 2

                # Get attendance records for this student
                self.database.cursor.execute(
                    """
                    SELECT date, status, time, second_time, is_cancelled 
                    FROM attendance
                    WHERE student_id = ? AND course_id = ?
                    ORDER BY date
                    """,
                    (student_id, course_id)
                )
                records = self.database.cursor.fetchall()

                # Count attendance statuses
                total_classes = 0
                present_count = 0
                late_count = 0
                absent_count = 0
                unauthorized_count = 0

                # Track all dates for this student
                attendance_dates = {}

                for record in records:
                    date, status, time, second_time, is_cancelled = record

                    # Skip cancelled classes
                    if is_cancelled:
                        continue

                    total_classes += 1

                    if status == STATUS_PRESENT:
                        present_count += 1
                    elif status == STATUS_LATE:
                        late_count += 1
                    elif status == STATUS_ABSENT:
                        absent_count += 1
                    elif status == STATUS_UNAUTHORIZED_DEPARTURE:
                        unauthorized_count += 1

                    # Store time info for the report
                    attendance_dates[date] = {
                        'status': status,
                        'time': time,
                        'second_time': second_time
                    }

                # Calculate attendance percentage
                if total_classes > 0:
                    attendance_percentage = (present_count + late_count) / total_classes * 100
                else:
                    attendance_percentage = 0

                # Determine status based on attendance percentage
                if attendance_percentage >= 90:
                    status = "GOOD STANDING"
                elif attendance_percentage >= 85:
                    status = "WARNING"
                elif attendance_percentage >= 80:
                    status = "AT RISK"
                else:
                    status = "DENIED"

                # Add to student stats
                student_stats.append({
                    'id': student_id,
                    'name': student_name,
                    'present': present_count,
                    'late': late_count,
                    'absent': absent_count,
                    'unauthorized': unauthorized_count,
                    'total': total_classes,
                    'percentage': attendance_percentage,
                    'status': status,
                    'dates': attendance_dates
                })

            # Generate CSV content
            with open(file_path, 'w') as f:
                # Write header
                f.write(f"Attendance Report for {course_code}: {course_name} (Section {course_section})\n")
                f.write(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                # Course summary
                f.write("COURSE SUMMARY\n")
                f.write(f"Total Students Enrolled: {len(enrolled_students)}\n\n")

                # Student attendance summary
                f.write("STUDENT ATTENDANCE SUMMARY\n")
                f.write("Student ID,Name,Present,Late,Absent,Unauthorized Departure,Total Classes,Attendance %,Status\n")

                for student in student_stats:
                    f.write(f"{student['id']},{student['name']},{student['present']},{student['late']},{student['absent']},{student['unauthorized']},{student['total']},{student['percentage']:.1f}%,{student['status']}\n")

                f.write("\n")

                # Detailed attendance records
                f.write("DETAILED ATTENDANCE RECORDS\n")
                f.write("Student ID,Name,Date,Status,First Check-in,Second Check-in\n")

                # Get all class dates for this course
                self.database.cursor.execute(
                    """
                    SELECT DISTINCT date FROM attendance
                    WHERE course_id = ? AND is_cancelled = 0
                    ORDER BY date
                    """,
                    (course_id,)
                )
                all_dates = [row[0] for row in self.database.cursor.fetchall()]

                # For each student and each date
                for student in student_stats:
                    for date in all_dates:
                        if date in student['dates']:
                            record = student['dates'][date]
                            status = record['status']
                            time = record['time'] if record['time'] else ''
                            second_time = record['second_time'] if record['second_time'] else ''
                            f.write(f"{student['id']},{student['name']},{date},{status},{time},{second_time}\n")

            QMessageBox.information(self, "Report Generated", f"Attendance report saved to:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate report: {str(e)}")

    def setup_profile_tab(self):
        layout = QVBoxLayout(self.profile_tab)

        # Profile header
        header_layout = QHBoxLayout()

        # Profile info section
        info_group = QGroupBox("Personal Information")
        info_layout = QFormLayout(info_group)

        # User details
        self.username_label = QLabel()
        self.name_label = QLabel()
        self.role_label = QLabel()

        info_layout.addRow("Username:", self.username_label)
        info_layout.addRow("Full Name:", self.name_label)
        info_layout.addRow("Role:", self.role_label)

        header_layout.addWidget(info_group)
        layout.addLayout(header_layout)

        # Course assignment section
        courses_group = QGroupBox("Assigned Courses")
        courses_layout = QVBoxLayout(courses_group)

        self.assigned_courses_table = QTableWidget(0, 9)
        self.assigned_courses_table.setHorizontalHeaderLabels([
            "ID", "Ref #", "Code", "Section", "Name", "Days", "Time", "Classroom", "Date Range"
        ])
        self.assigned_courses_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.assigned_courses_table.setEditTriggers(QTableWidget.NoEditTriggers)

        courses_layout.addWidget(self.assigned_courses_table)
        layout.addWidget(courses_group)

        # Actions section
        actions_group = QGroupBox("Account Actions")
        actions_layout = QVBoxLayout(actions_group)

        change_password_button = QPushButton("Change Password")
        change_password_button.clicked.connect(self.change_password)

        actions_layout.addWidget(change_password_button)

        layout.addWidget(actions_group)

        # Add stretching space at the bottom
        layout.addStretch(1)

    def setup_manual_attendance_tab(self):
        layout = QVBoxLayout(self.manual_attendance_tab)

        # Course selection
        course_layout = QHBoxLayout()
        course_layout.addWidget(QLabel("Select Course:"))

        self.manual_course_combo = QComboBox()
        self.manual_course_combo.currentIndexChanged.connect(self.on_manual_course_changed)
        course_layout.addWidget(self.manual_course_combo)

        # Refresh button to reload courses
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.load_courses)
        course_layout.addWidget(refresh_button)

        layout.addLayout(course_layout)

        # Instructions label
        instructions = QLabel("Select a course from the dropdown to manage attendance manually.\n"
                            "You can search for students, select them, and mark their attendance status.")
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setStyleSheet("color: #666; margin: 10px;")
        layout.addWidget(instructions)

        # Manual attendance widget container
        self.manual_container = QWidget()
        self.manual_container_layout = QVBoxLayout(self.manual_container)

        # Placeholder text
        placeholder = QLabel("Select a course to start manual attendance")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setFont(QFont("Arial", 14))
        self.manual_container_layout.addWidget(placeholder)

        layout.addWidget(self.manual_container)

    def setup_records_tab(self):
        layout = QVBoxLayout(self.records_tab)

        # Filter controls
        filter_layout = QHBoxLayout()

        # Course selection
        filter_layout.addWidget(QLabel("Course:"))
        self.record_course_combo = QComboBox()
        # Connect course selection to date filter setup
        self.record_course_combo.currentIndexChanged.connect(self.setup_record_date_filter)
        filter_layout.addWidget(self.record_course_combo)

        # Date selection
        filter_layout.addWidget(QLabel("Date:"))
        self.record_date = QDateEdit()
        self.record_date.setCalendarPopup(True)
        self.record_date.setDate(QDate.currentDate())
        filter_layout.addWidget(self.record_date)

        # View button
        view_button = QPushButton("View Records")
        view_button.clicked.connect(self.load_attendance_records)
        filter_layout.addWidget(view_button)

        layout.addLayout(filter_layout)

        # Records table - updated to include time
        self.records_table = QTableWidget(0, 6)
        self.records_table.setHorizontalHeaderLabels(["Student ID", "Name", "Status", "First Check-in", "Second Check-in", "Cancelled"])
        self.records_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.records_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.records_table.doubleClicked.connect(self.show_student_image_from_records)

        layout.addWidget(self.records_table)

        # Add Generate Report button - NEW CODE
        report_button_layout = QHBoxLayout()
        report_button_layout.addStretch(1)

        generate_report_button = QPushButton("Generate Attendance Report")
        generate_report_button.setStyleSheet("background-color: #4285F4; color: white; font-weight: bold; padding: 8px;")
        generate_report_button.clicked.connect(self.generate_attendance_report)

        report_button_layout.addWidget(generate_report_button)
        report_button_layout.addStretch(1)

        layout.addLayout(report_button_layout)

    def setup_record_date_filter(self):
        """Set up date filter for the records tab based on selected course"""
        if self.record_course_combo.count() == 0:
            return

        course_id = self.record_course_combo.currentData()
        if course_id is None:
            return

        # Get course details
        course = self.database.get_course_by_id(course_id)
        if course:
            # Set up date filter
            self.record_date_filter = CourseDateValidator.setup_date_filter(self.record_date, course, self.database)

    def load_courses(self):
        # Load profile info
        self.username_label.setText(self.teacher_data[1])
        self.name_label.setText(self.teacher_data[3])
        self.role_label.setText(self.teacher_data[4])

        # Clear combos
        self.manual_course_combo.clear()
        self.record_course_combo.clear()

        # Clear assigned courses table
        self.assigned_courses_table.setRowCount(0)

        # Get courses assigned to this teacher
        courses = self.database.get_teacher_courses(self.teacher_id)

        # Add to combo boxes
        for course in courses:
            # Make sure we have all the required fields
            if len(course) < 7:  # Need at least 7 fields for basic display
                continue

            reference_number = course[0]  # Now the primary key
            code = course[2]
            name = course[3]
            section = course[4]
            start_time = course[5]
            end_time = course[6]
            classroom = course[7] if len(course) > 7 else "N/A"
            days = course[8] if len(course) > 8 else "N/A"
            start_date = course[9] if len(course) > 9 else "N/A"
            end_date = course[10] if len(course) > 10 else "N/A"

            display_text = f"{code}-{name}: {section}"

            self.manual_course_combo.addItem(display_text, reference_number)
            self.record_course_combo.addItem(display_text, reference_number)

            # Add to assigned courses table
            row = self.assigned_courses_table.rowCount()
            self.assigned_courses_table.insertRow(row)

            self.assigned_courses_table.setItem(row, 0, QTableWidgetItem(str(reference_number)))  # Reference number
            self.assigned_courses_table.setItem(row, 1, QTableWidgetItem(code))  # Code
            self.assigned_courses_table.setItem(row, 2, QTableWidgetItem(section))  # Section
            self.assigned_courses_table.setItem(row, 3, QTableWidgetItem(name))  # Name
            self.assigned_courses_table.setItem(row, 4, QTableWidgetItem(days))  # Days

            # Format time as Start-End
            time_str = f"{start_time} - {end_time}"
            self.assigned_courses_table.setItem(row, 5, QTableWidgetItem(time_str))  # Time

            self.assigned_courses_table.setItem(row, 6, QTableWidgetItem(classroom))  # Classroom

            # Format date range
            if start_date != "N/A" and end_date != "N/A":
                date_range = f"{start_date} to {end_date}"
                self.assigned_courses_table.setItem(row, 7, QTableWidgetItem(date_range))
            else:
                self.assigned_courses_table.setItem(row, 7, QTableWidgetItem("N/A"))

        # Set up initial date filter for records tab
        if self.record_course_combo.count() > 0:
            self.setup_record_date_filter()

        # Load stats course combo
        self.stats_course_combo.clear()
        self.student_course_combo.clear()
        for course in courses:
            if len(course) < 5:  # Need at least these fields
                continue
            reference_number = course[0]  # Now the primary key
            code = course[2]
            name = course[3]
            section = course[4]
            display_text = f"{code}-{name}: {section}"
            self.stats_course_combo.addItem(display_text, reference_number)
            self.student_course_combo.addItem(display_text, reference_number)

    def on_manual_course_changed(self):
        """Create and add the manual attendance widget when a course is selected"""
        try:
            # Clear the manual container
            while self.manual_container_layout.count():
                child = self.manual_container_layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

            # Get selected course ID
            if self.manual_course_combo.count() == 0:
                return

            course_id = self.manual_course_combo.currentData()
            if course_id is None:
                placeholder = QLabel("No course selected")
                placeholder.setAlignment(Qt.AlignCenter)
                self.manual_container_layout.addWidget(placeholder)
                return

            # Create and add the manual attendance widget
            manual_widget = ManualAttendanceWidget(self.database, course_id)
            self.manual_container_layout.addWidget(manual_widget)
            
            # Log success
            print(f"Manual attendance widget created for course ID: {course_id}")
            
        except Exception as e:
            # Show error in UI for better debugging
            error_label = QLabel(f"Error loading manual attendance widget: {str(e)}")
            error_label.setStyleSheet("color: red;")
            error_label.setWordWrap(True)
            self.manual_container_layout.addWidget(error_label)
            
            # Also print to console
            print(f"Error in on_manual_course_changed: {e}")
            import traceback
            traceback.print_exc()

    def load_attendance_records(self):
        """Load attendance records for the selected course and date"""
        if self.record_course_combo.count() == 0:
            return

        course_id = self.record_course_combo.currentData()
        if course_id is None:
            return

        # Get course details
        course = self.database.get_course_by_id(course_id)
        if not course:
            return

        # Set up date filter if needed
        if not hasattr(self, 'record_date_filter'):
            self.record_date_filter = CourseDateValidator.setup_date_filter(self.record_date, course, self.database)

        # Get the selected date
        date = self.record_date.date().toString("yyyy-MM-dd")

        # Clear existing records
        self.records_table.setRowCount(0)

        # Get attendance records for the selected course and date
        records = self.database.get_attendance_records(course_id, date)

        # Populate table with records
        for i, record in enumerate(records):
            if not record or len(record) < 5:  # Make sure we have enough data
                continue

            student_id, name, status, time, second_time, is_cancelled = record

            self.records_table.insertRow(i)
            self.records_table.setItem(i, 0, QTableWidgetItem(str(student_id)))
            self.records_table.setItem(i, 1, QTableWidgetItem(name))

            # Add status with appropriate styling
            status_item = QTableWidgetItem(status)
            if status == STATUS_PRESENT:
                status_item.setForeground(QBrush(QColor("green")))
            elif status == STATUS_LATE:
                status_item.setForeground(QBrush(QColor("orange")))
            elif status == STATUS_ABSENT:
                status_item.setForeground(QBrush(QColor("red")))
            elif status == STATUS_UNAUTHORIZED_DEPARTURE:
                status_item.setForeground(QBrush(QColor("purple")))

            self.records_table.setItem(i, 2, status_item)

            # Add time columns
            self.records_table.setItem(i, 3, QTableWidgetItem(time if time else ""))
            self.records_table.setItem(i, 4, QTableWidgetItem(second_time if second_time else ""))

            # Add cancelled status
            cancelled_text = "Yes" if is_cancelled else "No"
            cancelled_item = QTableWidgetItem(cancelled_text)
            if is_cancelled:
                cancelled_item.setForeground(QBrush(QColor("red")))
            self.records_table.setItem(i, 5, cancelled_item)

    def setup_stats_tab(self):
        layout = QVBoxLayout(self.stats_tab)

        # Course selection section
        course_layout = QHBoxLayout()
        course_layout.addWidget(QLabel("Course:"))

        self.stats_course_combo = QComboBox()
        self.stats_course_combo.currentIndexChanged.connect(self.load_section_stats)
        course_layout.addWidget(self.stats_course_combo)

        layout.addLayout(course_layout)

        # Charts and statistics section
        charts_layout = QHBoxLayout()

        # Course attendance chart
        self.attendance_chart = AttendanceStatsChart()
        charts_layout.addWidget(self.attendance_chart)

        # Right side course statistics
        stats_panel = QWidget()
        stats_layout = QVBoxLayout(stats_panel)

        # Course statistics
        self.stats_group = QGroupBox("Course Statistics")
        stats_group_layout = QFormLayout(self.stats_group)

        self.total_students_label = QLabel()
        self.avg_attendance_label = QLabel()
        self.total_classes_label = QLabel()
        self.present_rate_label = QLabel()
        self.late_rate_label = QLabel()
        self.absent_rate_label = QLabel()
        self.unauthorized_rate_label = QLabel()

        stats_group_layout.addRow("Total Students:", self.total_students_label)
        stats_group_layout.addRow("Total Classes Held:", self.total_classes_label)
        stats_group_layout.addRow("Average Attendance Rate:", self.avg_attendance_label)
        stats_group_layout.addRow("Present Rate:", self.present_rate_label)
        stats_group_layout.addRow("Late Rate:", self.late_rate_label)
        stats_group_layout.addRow("Absent Rate:", self.absent_rate_label)
        stats_group_layout.addRow("Unauthorized Departure Rate:", self.unauthorized_rate_label)

        stats_layout.addWidget(self.stats_group)
        charts_layout.addWidget(stats_panel)

        layout.addLayout(charts_layout)

        # Student search section at the bottom
        layout.addWidget(QLabel("Search Student for Individual Stats:"))

        search_layout = QHBoxLayout()

        self.student_search = QLineEdit()
        self.student_search.setPlaceholderText("Type student name or ID...")
        self.student_search.textChanged.connect(self.search_students)

        self.student_results = QComboBox()
        self.student_results.setMaxVisibleItems(10)
        self.student_results.currentIndexChanged.connect(self.load_student_stats)

        search_layout.addWidget(self.student_search)
        search_layout.addWidget(self.student_results)

        layout.addLayout(search_layout)

        # Student attendance records
        self.student_records_table = QTableWidget(0, 4)
        self.student_records_table.setHorizontalHeaderLabels(["Date", "Status", "First Check-in", "Second Check-in"])
        self.student_records_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.student_records_table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Student chart
        self.student_chart = AttendanceStatsChart()

        # Add both to a split layout
        student_data_layout = QHBoxLayout()
        student_data_layout.addWidget(self.student_records_table)
        student_data_layout.addWidget(self.student_chart)

        layout.addLayout(student_data_layout)

    def search_students(self):
        if self.stats_course_combo.count() == 0:
            return

        course_id = self.stats_course_combo.currentData()
        if not course_id:
            return

        search_text = self.student_search.text().strip()
        if not search_text:
            self.student_results.clear()
            return

        # Search using exact sequence matching in database
        search_results = self.database.search_enrolled_students(course_id, search_text)

        # Update dropdown
        self.student_results.clear()
        for student in search_results:
            student_id, _, name = student
            self.student_results.addItem(f"{name} (ID: {student_id})", student_id)

    def load_student_stats(self):
        if self.student_results.count() == 0 or self.stats_course_combo.count() == 0:
            return

        student_id = self.student_results.currentData()
        course_id = self.stats_course_combo.currentData()

        if not student_id or not course_id:
            return

        # Get attendance records for this student in this course
        self.database.cursor.execute(
            """
            SELECT date, status, time, second_time 
            FROM attendance
            WHERE student_id = ? AND course_id = ?
            ORDER BY date DESC
            """,
            (student_id, course_id)
        )

        records = self.database.cursor.fetchall()

        # Display in table
        self.student_records_table.setRowCount(0)

        for i, record in enumerate(records):
            date, status, time, second_time = record

            self.student_records_table.insertRow(i)
            self.student_records_table.setItem(i, 0, QTableWidgetItem(date))
            self.student_records_table.setItem(i, 1, QTableWidgetItem(status))
            self.student_records_table.setItem(i, 2, QTableWidgetItem(time if time else ""))
            self.student_records_table.setItem(i, 3, QTableWidgetItem(second_time if second_time else ""))

        # Update student chart
        stats_data = self.database.get_student_attendance_stats(student_id, course_id)
        status_counts = {status: count for status, count in stats_data.items() if status != 'total_days'}
        chart_data = {'status_counts': status_counts}
        self.student_chart.plot_attendance_pie_chart(chart_data)

    def load_section_stats(self):
        if self.stats_course_combo.count() == 0:
            return

        course_id = self.stats_course_combo.currentData()
        if not course_id:
            return

        # Get course statistics
        stats = self.database.get_course_attendance_stats(course_id)

        # Update UI with statistics
        self.total_students_label.setText(str(stats['total_students']))
        self.total_classes_label.setText(str(stats['total_classes']))

        if 'attendance_rate' in stats:
            self.avg_attendance_label.setText(f"{stats['attendance_rate']:.1f}%")
            self.present_rate_label.setText(f"{stats['present_rate']:.1f}%")
            self.late_rate_label.setText(f"{stats['late_rate']:.1f}%")
            self.absent_rate_label.setText(f"{stats['absent_rate']:.1f}%")
            self.unauthorized_rate_label.setText(f"{stats['unauthorized_rate']:.1f}%")
        else:
            self.avg_attendance_label.setText("N/A")
            self.present_rate_label.setText("N/A")
            self.late_rate_label.setText("N/A")
            self.absent_rate_label.setText("N/A")
            self.unauthorized_rate_label.setText("N/A")

        # Update chart
        self.attendance_chart.plot_attendance_pie_chart(stats)

    def show_student_image_from_records(self):
        selected_row = self.records_table.currentRow()
        if selected_row < 0:
            return

        student_id = self.records_table.item(selected_row, 0).text()
        name = self.records_table.item(selected_row, 1).text()

        # Get the current course ID
        course_id = self.record_course_combo.currentData()

        # Show student image dialog with attendance records
        dialog = StudentImageDialog(self, student_id, name, self.face_recognition_system, course_id)
        dialog.exec_()

    def closeEvent(self, event):
        self.database.update_partial_attendance()

        if hasattr(self, 'camera_container'):
            for i in range(self.camera_container_layout.count()):
                widget = self.camera_container_layout.itemAt(i).widget()
                if widget and hasattr(widget, 'stop_camera'):
                    widget.stop_camera()

        event.accept()
        
    def logout(self):
        # Hide this window instead of closing it
        self.hide()

        try:
            # Attempt to find the main app instance in the main module
            import sys
            import main

            # The app instance should be in the main module
            if hasattr(main, 'app'):
                main.app.show_login_window()
                return
        except ImportError:
            pass

        # Fallback approach: search QApplication for login window
        from PyQt5.QtWidgets import QApplication
        app = QApplication.instance()

        # Try to find the login window in all top-level widgets
        login_window = None
        for widget in app.topLevelWidgets():
            if type(widget).__name__ == 'LoginWindow':
                login_window = widget
                login_window.show()
                return

        import os
        python = sys.executable
        os.execl(python, python, *sys.argv)

    def change_password(self):
        dialog = ChangePasswordDialog(self, self.database, self.teacher_id)
        dialog.exec_()
        
    def setup_student_tab(self):
        """Set up the student attendance tab with simplified layout"""
        layout = QVBoxLayout(self.student_tab)
        
        # Top section - Course selection with filter controls
        top_section = QHBoxLayout()
        
        # Course selection
        course_section = QVBoxLayout()
        course_section.addWidget(QLabel("Select Course:"))
        
        self.student_course_combo = QComboBox()
        self.student_course_combo.currentIndexChanged.connect(self.load_student_attendance)
        course_section.addWidget(self.student_course_combo)
        
        top_section.addLayout(course_section, 1)  # stretch factor 1
        
        # Sort and filter options
        controls_section = QVBoxLayout()
        
        # Sort options
        sort_section = QHBoxLayout()
        sort_section.addWidget(QLabel("Sort by"))
        
        self.sort_options = QButtonGroup(self)
        self.sort_option_asc = QRadioButton("Lowest attendance first")
        self.sort_option_desc = QRadioButton("Highest attendance first")
        self.sort_option_name = QRadioButton("Student name")
        
        self.sort_options.addButton(self.sort_option_asc, 1)
        self.sort_options.addButton(self.sort_option_desc, 2)
        self.sort_options.addButton(self.sort_option_name, 3)
        
        self.sort_option_asc.setChecked(True)  # Default sort option
        
        sort_section.addWidget(self.sort_option_asc)
        sort_section.addWidget(self.sort_option_desc)
        sort_section.addWidget(self.sort_option_name)
        
        # Connect sort change signal
        self.sort_options.buttonClicked.connect(self.refresh_student_attendance)
        
        controls_section.addLayout(sort_section)
        
        # Filter options
        filter_section = QHBoxLayout()
        filter_section.addWidget(QLabel("Filter students"))
        
        self.filter_options = QButtonGroup(self)
        self.filter_all = QRadioButton("All students")
        self.filter_at_risk = QRadioButton("At risk (< 90%)")
        self.filter_warning = QRadioButton("Warning (< 85%)")
        self.filter_critical = QRadioButton("Critical (< 80%)")
        self.filter_denied = QRadioButton("Denied")
        
        self.filter_options.addButton(self.filter_all, 1)
        self.filter_options.addButton(self.filter_at_risk, 2)
        self.filter_options.addButton(self.filter_warning, 3)
        self.filter_options.addButton(self.filter_critical, 4)
        self.filter_options.addButton(self.filter_denied, 5)
        
        self.filter_all.setChecked(True)  # Default show all
        
        filter_section.addWidget(self.filter_all)
        filter_section.addWidget(self.filter_at_risk)
        filter_section.addWidget(self.filter_warning)
        filter_section.addWidget(self.filter_critical)
        filter_section.addWidget(self.filter_denied)
        
        # Connect filter change signal
        self.filter_options.buttonClicked.connect(self.refresh_student_attendance)
        
        controls_section.addLayout(filter_section)
        top_section.addLayout(controls_section, 2)  # stretch factor 2
        
        layout.addLayout(top_section)
        
        # Class attendance summary section
        summary_layout = QHBoxLayout()
        summary_layout.addWidget(QLabel("Class Attendance Summary"))
        
        # Add stats counters
        summary_layout.addSpacing(20)
        summary_layout.addWidget(QLabel("Total:"))
        self.total_students_label = QLabel("0")
        summary_layout.addWidget(self.total_students_label)
        
        summary_layout.addSpacing(20)
        good_label = QLabel("Good:")
        good_label.setStyleSheet("color: green;")
        summary_layout.addWidget(good_label)
        self.good_students_label = QLabel("0")
        self.good_students_label.setStyleSheet("color: green;")
        summary_layout.addWidget(self.good_students_label)
        
        summary_layout.addSpacing(20)
        at_risk_label = QLabel("At Risk:")
        at_risk_label.setStyleSheet("color: orange;")
        summary_layout.addWidget(at_risk_label)
        self.at_risk_students_label = QLabel("0")
        self.at_risk_students_label.setStyleSheet("color: orange;")
        summary_layout.addWidget(self.at_risk_students_label)
        
        summary_layout.addSpacing(20)
        warning_label = QLabel("Warning:")
        warning_label.setStyleSheet("color: #FFC107;")
        summary_layout.addWidget(warning_label)
        self.warning_students_label = QLabel("0")
        self.warning_students_label.setStyleSheet("color: #FFC107;")
        summary_layout.addWidget(self.warning_students_label)
        
        summary_layout.addSpacing(20)
        denied_label = QLabel("Denied:")
        denied_label.setStyleSheet("color: red;")
        summary_layout.addWidget(denied_label)
        self.denied_students_label = QLabel("0")
        self.denied_students_label.setStyleSheet("color: red;")
        summary_layout.addWidget(self.denied_students_label)
        
        summary_layout.addStretch(1)
        
        layout.addLayout(summary_layout)
        
        # Search student section
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search student:"))
        
        self.student_search_input = QLineEdit()
        self.student_search_input.setPlaceholderText("Enter student name or ID...")
        self.student_search_input.textChanged.connect(self.filter_student_table)
        
        search_layout.addWidget(self.student_search_input)
        
        # Reset button
        reset_search_button = QPushButton("Reset")
        reset_search_button.clicked.connect(self.reset_student_search)
        search_layout.addWidget(reset_search_button)
        
        layout.addLayout(search_layout)
        
        # Student table with attendance data - removed Actions column
        self.student_table = QTableWidget(0, 5)  # 5 columns: ID, Name, Attendance, Absence Dates, Status
        self.student_table.setHorizontalHeaderLabels([
            "ID", "Name", "Attendance", "Absence Dates", "Status"
        ])
        self.student_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.student_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # Set specific column widths
        self.student_table.setColumnWidth(2, 200)  # Attendance column
        self.student_table.setColumnWidth(3, 300)  # Absence dates column
        
        # Make student table rows clickable to show student details
        self.student_table.doubleClicked.connect(self.on_student_table_double_clicked)
        
        layout.addWidget(self.student_table)



    def on_student_table_double_clicked(self, index):
        """Handle double-click on student table to show details"""
        row = index.row()
        if row >= 0:
            student_id = self.student_table.item(row, 0).text()
            student_name = self.student_table.item(row, 1).text()
            self.show_student_image(student_id, student_name)

    def load_student_attendance(self):
        """Load students for the selected course with attendance data"""
        course_id = self.student_course_combo.currentData()
        if not course_id:
            self.student_table.setRowCount(0)
            # Reset statistics
            self.update_attendance_statistics(0, 0, 0, 0, 0)
            return
        
        # Get attendance summary for this course
        attendance_summary = self.attendance_tracker.get_course_attendance_summary(course_id)
        self.student_stats = attendance_summary.get('student_stats', [])
        
        # Update statistics in UI
        good_count = attendance_summary.get('good_count', 0)
        warning_count = attendance_summary.get('warning_count', 0)
        risk_count = attendance_summary.get('risk_count', 0)
        denied_count = attendance_summary.get('denied_count', 0)
        total_count = len(self.student_stats)
        
        self.update_attendance_statistics(total_count, good_count, risk_count, warning_count, denied_count)
        
        # Apply sorting and filtering
        self.refresh_student_attendance()



    def refresh_student_attendance(self):
        """Refresh the student attendance table with current sort and filter settings"""
        if not hasattr(self, 'student_stats') or not self.student_stats:
            return
            
        # Apply sorting
        sorted_stats = self.sort_student_stats(self.student_stats)
        
        # Apply filtering
        filtered_stats = self.filter_student_stats(sorted_stats)
        
        # Update table
        self.populate_student_table(filtered_stats)


    def sort_student_stats(self, stats):
        """Sort student stats based on selected option"""
        sorted_stats = stats.copy()
        
        if self.sort_option_asc.isChecked():
            # Sort by attendance percentage (lowest first)
            sorted_stats.sort(key=lambda x: x['percentage'])
        elif self.sort_option_desc.isChecked():
            # Sort by attendance percentage (highest first)
            sorted_stats.sort(key=lambda x: x['percentage'], reverse=True)
        elif self.sort_option_name.isChecked():
            # Sort by student name
            sorted_stats.sort(key=lambda x: x['student_name'].lower())
        
        return sorted_stats

    def filter_student_stats(self, stats):
        """Filter student stats based on selected option"""
        if self.filter_all.isChecked():
            return stats
        
        filtered_stats = []
        
        for student in stats:
            percentage = student['percentage']
            
            if self.filter_denied.isChecked() and percentage < 80:
                filtered_stats.append(student)
            elif self.filter_critical.isChecked() and percentage < 80:
                filtered_stats.append(student)
            elif self.filter_warning.isChecked() and percentage < 85:
                filtered_stats.append(student)
            elif self.filter_at_risk.isChecked() and percentage < 90:
                filtered_stats.append(student)
        
        return filtered_stats

    def populate_student_table(self, student_stats):
        """Populate the student table with compact attendance display"""
        self.student_table.setRowCount(len(student_stats))
        
        for row, stats in enumerate(student_stats):
            student_id = stats['student_id']
            student_name = stats['student_name']
            percentage = stats['percentage']
            
            # ID and Name
            self.student_table.setItem(row, 0, QTableWidgetItem(str(student_id)))
            self.student_table.setItem(row, 1, QTableWidgetItem(student_name))
            
            # Attendance bar (custom widget)
            attendance_widget = CompactAttendanceBar(percentage)
            self.student_table.setCellWidget(row, 2, attendance_widget)
            
            # Absence dates - simplified display
            absence_dates = stats.get('absence_dates', [])
            if absence_dates:
                date_text = ", ".join(absence_dates[:3])
                if len(absence_dates) > 3:
                    date_text += f" +{len(absence_dates) - 3} more"
            else:
                date_text = "None"
                
            self.student_table.setItem(row, 3, QTableWidgetItem(date_text))
            
            # Status with color
            status_item = QTableWidgetItem()
            if percentage < 80:
                status_item.setText("DENIED")
                status_item.setForeground(QBrush(QColor("red")))
            elif percentage < 85:
                status_item.setText("AT RISK")
                status_item.setForeground(QBrush(QColor("orange")))
            elif percentage < 90:
                status_item.setText("WARNING")
                status_item.setForeground(QBrush(QColor("#FFC107")))
            else:
                status_item.setText("GOOD")
                status_item.setForeground(QBrush(QColor("green")))
                
            status_item.setTextAlignment(Qt.AlignCenter)
            status_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.student_table.setItem(row, 4, status_item)


    def update_attendance_statistics(self, total, good, risk, warning, denied):
        """Update the attendance statistics labels"""
        self.total_students_label.setText(str(total))
        self.good_students_label.setText(str(good))
        self.at_risk_students_label.setText(str(risk))
        self.warning_students_label.setText(str(warning))
        self.denied_students_label.setText(str(denied))


    def show_student_image(self, student_id, student_name):
        """Show student image and attendance details dialog"""
        # Create student image dialog
        dialog = StudentImageDialog(self, student_id, student_name, self.face_recognition_system, self.student_course_combo.currentData())
        dialog.exec_()

    def filter_student_table(self):
        """Filter the student table based on search text"""
        search_text = self.student_search_input.text().lower()
        
        for row in range(self.student_table.rowCount()):
            student_id = self.student_table.item(row, 0).text().lower()
            student_name = self.student_table.item(row, 1).text().lower()
            
            if search_text in student_id or search_text in student_name:
                self.student_table.setRowHidden(row, False)
            else:
                self.student_table.setRowHidden(row, True)

    def reset_student_search(self):
        """Reset the student search filter"""
        self.student_search_input.clear()
        for row in range(self.student_table.rowCount()):
            self.student_table.setRowHidden(row, False)

class EndLectureDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Custom End Time")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        # Add explanation
        explanation = QLabel("This will set a custom end time for today's lecture.")
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        # Add time selection
        time_layout = QHBoxLayout()
        time_label = QLabel("End Time:")
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime.currentTime())
        time_layout.addWidget(time_label)
        time_layout.addWidget(self.time_edit)

        # Add buttons
        button_layout = QHBoxLayout()
        confirm_button = QPushButton("Confirm")
        cancel_button = QPushButton("Cancel")

        confirm_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(confirm_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(time_layout)
        layout.addLayout(button_layout)

class CompactAttendanceBar(QWidget):
    """Compact attendance bar for the student table"""
    def __init__(self, percentage):
        super().__init__()
        self.percentage = percentage
        self.setMinimumHeight(30)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get widget dimensions
        width = self.width()
        height = self.height()
        
        # Draw background (gray)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(220, 220, 220)))
        painter.drawRect(0, 0, width, height)
        
        # Determine color based on percentage
        if self.percentage >= 90:
            color = QColor(76, 175, 80)  # Green
        elif self.percentage >= 85:
            color = QColor(255, 193, 7)  # Yellow
        elif self.percentage >= 80:
            color = QColor(255, 152, 0)  # Orange
        else:
            color = QColor(244, 67, 54)  # Red
        
        # Draw foreground (colored)
        bar_width = int(width * self.percentage / 100)
        painter.setBrush(QBrush(color))
        painter.drawRect(0, 0, bar_width, height)
        
        # Draw percentage text
        painter.setPen(Qt.white if bar_width > width / 2 else Qt.black)
        text_rect = QRect(0, 0, width, height)
        painter.drawText(text_rect, Qt.AlignCenter, f"{self.percentage:.1f}%")
