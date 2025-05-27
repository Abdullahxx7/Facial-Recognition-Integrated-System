import cv2
import numpy as np
import datetime
from PyQt5.QtWidgets import QApplication

try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: Matplotlib not available. Charts will be disabled.")

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QFormLayout, QLineEdit, QGroupBox,
    QListWidget, QListWidgetItem, QButtonGroup, QRadioButton, QGridLayout,
    QFileDialog, QSizePolicy, QFrame, QProgressBar
)
from PyQt5.QtCore import Qt, QDate, QTimer, QSize
from PyQt5.QtGui import QFont, QBrush, QColor, QPixmap, QImage

from config import STATUS_PRESENT, STATUS_ABSENT, STATUS_LATE, STATUS_UNAUTHORIZED_DEPARTURE

class AttendanceStatsChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Check if matplotlib is available
        self.matplotlib_available = MATPLOTLIB_AVAILABLE
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        if self.matplotlib_available:
            # Create a figure and canvas for matplotlib
            self.figure = Figure(figsize=(8, 5), dpi=100)
            self.canvas = FigureCanvas(self.figure)
            layout.addWidget(self.canvas)
        else:
            # Fallback for when matplotlib is not available
            self.no_chart_label = QLabel("Charts not available (matplotlib required)")
            self.no_chart_label.setAlignment(Qt.AlignCenter)
            self.no_chart_label.setStyleSheet("color: #666; font-style: italic;")
            layout.addWidget(self.no_chart_label)

    def plot_attendance_pie_chart(self, stats_data):
        """Plot a pie chart of attendance statistics"""
        if not self.matplotlib_available:
            return

        try:
            self.figure.clear()

            # Get the axes and plot the pie chart
            ax = self.figure.add_subplot(111)

            # Extract data for the pie chart
            labels = []
            sizes = []
            colors = []

            # Define the status counts
            status_counts = {}
            for status, count in stats_data.items():
                if status != 'total_days':
                    status_counts[status] = count

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
                ax.set_title('My Attendance Distribution')
            else:
                ax.text(0.5, 0.5, 'No attendance data available',
                        horizontalalignment='center', verticalalignment='center',
                        fontsize=12)

            self.canvas.draw()
        except Exception as e:
            print(f"Error plotting pie chart: {e}")
            import traceback
            traceback.print_exc()

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
        try:
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
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update password: {str(e)}")

class StudentWindow(QMainWindow):
    def __init__(self, database, face_recognition_system, student_id):
        super().__init__()

        self.database = database
        self.face_recognition_system = face_recognition_system
        self.student_id = student_id

        # Ensure we get valid student data
        self.student_data = self.database.get_user_by_id(student_id)

        if not self.student_data:
            QMessageBox.critical(self, "Error", "Failed to load student data. Please contact an administrator.")
            self.close()
            return

        # Make sure we have a valid name for the window title
        student_name = self.student_data[3] if len(self.student_data) > 3 else f"Student {student_id}"
        self.setWindowTitle(f"Student Panel - {student_name}")
        self.setMinimumSize(800, 600)

        # Initialize matplotlib components if needed
        try:
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            from matplotlib.figure import Figure
            self.matplotlib_available = True
        except ImportError:
            self.matplotlib_available = False
            print("Warning: Matplotlib not available, charts will be disabled")

        self.init_ui()
        self.load_data()

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
        self.courses_tab = QWidget()
        self.stats_tab = QWidget()

        tab_widget.addTab(self.profile_tab, "My Profile")
        tab_widget.addTab(self.courses_tab, "My Courses")
        tab_widget.addTab(self.stats_tab, "My Statistics")

        # Set up tabs
        self.setup_profile_tab()
        self.setup_courses_tab()
        self.setup_stats_tab()

        # Logout button
        logout_button = QPushButton("Logout")
        logout_button.clicked.connect(self.logout)
        main_layout.addWidget(logout_button)

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

    def setup_profile_tab(self):
        layout = QVBoxLayout(self.profile_tab)

        # Profile header
        header_layout = QHBoxLayout()

        # Profile image section
        image_layout = QVBoxLayout()

        self.profile_image_label = QLabel()
        self.profile_image_label.setAlignment(Qt.AlignCenter)
        self.profile_image_label.setMinimumSize(200, 200)
        self.profile_image_label.setMaximumSize(200, 200)
        self.profile_image_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")
        image_layout.addWidget(self.profile_image_label)

        # Face registration status
        self.face_status_label = QLabel()
        self.face_status_label.setAlignment(Qt.AlignCenter)
        image_layout.addWidget(self.face_status_label)

        header_layout.addLayout(image_layout)

        # Profile info section
        info_group = QGroupBox("Personal Information")
        info_layout = QFormLayout(info_group)

        # User details
        self.username_label = QLabel()
        self.name_label = QLabel()
        self.role_label = QLabel()
        self.id_label = QLabel()

        info_layout.addRow("ID:", self.id_label)
        info_layout.addRow("Username:", self.username_label)
        info_layout.addRow("Full Name:", self.name_label)
        info_layout.addRow("Role:", self.role_label)

        header_layout.addWidget(info_group, 1)  # Give it stretching priority

        layout.addLayout(header_layout)

        # Today's classes section
        todays_classes_group = QGroupBox("Today's Classes")
        todays_classes_layout = QVBoxLayout(todays_classes_group)

        self.todays_classes_table = QTableWidget(0, 5)
        self.todays_classes_table.setHorizontalHeaderLabels(["Code", "Section", "Name", "Time", "Room"])
        self.todays_classes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.todays_classes_table.setEditTriggers(QTableWidget.NoEditTriggers)

        todays_classes_layout.addWidget(self.todays_classes_table)

        layout.addWidget(todays_classes_group)

        # Actions section
        actions_group = QGroupBox("Account Actions")
        actions_layout = QVBoxLayout(actions_group)

        change_password_button = QPushButton("Change Password")
        change_password_button.clicked.connect(self.change_password)

        actions_layout.addWidget(change_password_button)

        layout.addWidget(actions_group)

        # Add stretching space at the bottom
        layout.addStretch(1)

    def setup_courses_tab(self):
        layout = QVBoxLayout(self.courses_tab)

        # Courses section
        layout.addWidget(QLabel("My Courses:"))

        self.courses_table = QTableWidget(0, 7)
        self.courses_table.setHorizontalHeaderLabels([
            "Ref #", "Code", "Name", "Section", "Days", "Time", "Room"
        ])
        self.courses_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.courses_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.courses_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.courses_table.clicked.connect(self.load_attendance_records)

        layout.addWidget(self.courses_table)

        # Attendance records section
        layout.addWidget(QLabel("Attendance Records:"))

        self.attendance_table = QTableWidget(0, 5)
        self.attendance_table.setHorizontalHeaderLabels(["Course", "Date", "Status", "First Check-in", "Second Check-in"])
        self.attendance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.attendance_table.setEditTriggers(QTableWidget.NoEditTriggers)

        layout.addWidget(self.attendance_table)

    def setup_stats_tab(self):
        """Set up the student statistics tab with enhanced attendance tracking"""
        layout = QVBoxLayout(self.stats_tab)

        # Course selection in a card-like container
        course_card = QGroupBox("Course Selection")
        course_card.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 5px; margin-top: 1ex; } "
                                "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }")
        course_layout = QHBoxLayout(course_card)

        course_layout.addWidget(QLabel("Select Course:"))
        self.stats_course_combo = QComboBox()
        self.stats_course_combo.addItem("All Courses", None)  # Option for all courses
        course_layout.addWidget(self.stats_course_combo)

        view_button = QPushButton("View Statistics")
        view_button.setStyleSheet("background-color: #4285F4; color: white; font-weight: bold; padding: 5px 15px;")
        view_button.clicked.connect(self.load_student_statistics)
        course_layout.addWidget(view_button)

        layout.addWidget(course_card)

        # Main stats container
        main_stats_layout = QHBoxLayout()

        # Left side - Attendance Progress and Charts
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Attendance progress card
        progress_card = QGroupBox("My Attendance Status")
        progress_card.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 5px; margin-top: 1ex; } "
                                "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }")
        progress_layout = QVBoxLayout(progress_card)

        # Add attendance status widget
        try:
            from attendance_widgets import AttendanceStatsWidget
            self.attendance_status_widget = AttendanceStatsWidget(compact=False)
        except ImportError:
            # Fallback to basic widget if the import fails
            self.attendance_status_widget = QLabel("Attendance status widget not available")
            print("Warning: AttendanceStatsWidget not available, using fallback")

        progress_layout.addWidget(self.attendance_status_widget)

        left_layout.addWidget(progress_card)

        # Add the chart widget
        chart_card = QGroupBox("Attendance Distribution")
        chart_card.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 5px; margin-top: 1ex; } "
                                "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }")
        chart_layout = QVBoxLayout(chart_card)

        if self.matplotlib_available:
            self.attendance_chart = AttendanceStatsChart()
            chart_layout.addWidget(self.attendance_chart)
        else:
            chart_layout.addWidget(QLabel("Charts not available (matplotlib required)"))

        left_layout.addWidget(chart_card)

        # Right side - Statistics panel with details
        right_panel = QGroupBox("Attendance Details")
        right_panel.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 5px; margin-top: 1ex; } "
                                "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }")
        right_layout = QVBoxLayout(right_panel)

        # Stats layout with improved visuals
        stats_grid = QGridLayout()
        stats_grid.setColumnStretch(1, 1)
        stats_grid.setSpacing(10)

        row = 0
        # Total classes with icon
        stats_grid.addWidget(QLabel("🏫 Total Classes:"), row, 0)
        self.total_classes_label = QLabel("0")
        self.total_classes_label.setStyleSheet("font-weight: bold;")
        stats_grid.addWidget(self.total_classes_label, row, 1)

        row += 1
        # Present count with icon
        stats_grid.addWidget(QLabel("✅ Present:"), row, 0)
        self.present_count_label = QLabel("0")
        self.present_count_label.setStyleSheet("color: green; font-weight: bold;")
        stats_grid.addWidget(self.present_count_label, row, 1)

        row += 1
        # Late count with icon
        stats_grid.addWidget(QLabel("⏰ Late:"), row, 0)
        self.late_count_label = QLabel("0")
        self.late_count_label.setStyleSheet("color: orange; font-weight: bold;")
        stats_grid.addWidget(self.late_count_label, row, 1)

        row += 1
        # Absent count with icon
        stats_grid.addWidget(QLabel("❌ Absent:"), row, 0)
        self.absent_count_label = QLabel("0")
        self.absent_count_label.setStyleSheet("color: red; font-weight: bold;")
        stats_grid.addWidget(self.absent_count_label, row, 1)

        row += 1
        # Unauthorized departures with icon
        stats_grid.addWidget(QLabel("🚪 Unauthorized Departures:"), row, 0)
        self.unauthorized_count_label = QLabel("0")
        self.unauthorized_count_label.setStyleSheet("color: purple; font-weight: bold;")
        stats_grid.addWidget(self.unauthorized_count_label, row, 1)

        row += 1
        # Attendance rate with warning indicators
        stats_grid.addWidget(QLabel("📊 Attendance Rate:"), row, 0)
        self.attendance_rate_label = QLabel("0%")
        self.attendance_rate_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        stats_grid.addWidget(self.attendance_rate_label, row, 1)

        row += 1
        # Status with warning indicators
        stats_grid.addWidget(QLabel("⚠️ Status:"), row, 0)
        self.status_label = QLabel("Good Standing")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
        stats_grid.addWidget(self.status_label, row, 1)

        row += 1
        # Absence threshold explanation
        stats_grid.addWidget(QLabel("ℹ️ Absence Threshold:"), row, 0)
        threshold_label = QLabel("20% (University Policy)")
        threshold_label.setStyleSheet("font-style: italic;")
        stats_grid.addWidget(threshold_label, row, 1)

        right_layout.addLayout(stats_grid)

        # Add the absence date list
        absence_label = QLabel("Recent Absences:")
        absence_label.setStyleSheet("font-weight: bold; margin-top: 15px;")
        right_layout.addWidget(absence_label)

        self.absence_list = QListWidget()
        self.absence_list.setMaximumHeight(150)
        self.absence_list.setAlternatingRowColors(True)
        right_layout.addWidget(self.absence_list)

        main_stats_layout.addWidget(left_panel, 3)  # 60% width
        main_stats_layout.addWidget(right_panel, 2)  # 40% width

        layout.addLayout(main_stats_layout)

        # Attendance details table (simplified)
        details_card = QGroupBox("Attendance Record History")
        details_card.setStyleSheet("QGroupBox { border: 1px solid #ccc; border-radius: 5px; margin-top: 1ex; } "
                                "QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 3px; }")
        details_layout = QVBoxLayout(details_card)

        self.stats_attendance_table = QTableWidget(0, 5)
        self.stats_attendance_table.setHorizontalHeaderLabels(["Course", "Date", "Status", "First Check-in", "Second Check-in"])
        self.stats_attendance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stats_attendance_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stats_attendance_table.setAlternatingRowColors(True)
        details_layout.addWidget(self.stats_attendance_table)

        layout.addWidget(details_card)

    def load_data(self):
        try:
            # Load profile info
            if not self.student_data:
                print("Error: Student data is None")
                return

            self.id_label.setText(self.student_id)
            self.username_label.setText(self.student_data[1] if len(self.student_data) > 1 else "")
            self.name_label.setText(self.student_data[3] if len(self.student_data) > 3 else "")
            self.role_label.setText(self.student_data[4] if len(self.student_data) > 4 else "")

            # Check if face is registered
            has_face_encoding = self.student_data and len(self.student_data) > 5 and self.student_data[5]

            if has_face_encoding:
                self.face_status_label.setText("Face registered for recognition")

                # If there's a stored face image (at index 6)
                if len(self.student_data) > 6 and self.student_data[6]:
                    try:
                        # Convert binary data to QImage
                        img_data = self.student_data[6]
                        image = QImage()
                        image.loadFromData(img_data)

                        # Display the image
                        pixmap = QPixmap.fromImage(image)
                        pixmap = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        self.profile_image_label.setPixmap(pixmap)
                    except Exception as e:
                        print(f"Error loading image: {e}")
                        # Fall back to text if image loading fails
                        self.profile_image_label.setText("Face ID\nRegistered")
                        self.profile_image_label.setStyleSheet(
                            "background-color: #e0f0e0; border: 1px solid #60a060; color: #308030;"
                            "font-weight: bold; font-size: 16px; qproperty-alignment: AlignCenter;"
                        )
                else:
                    # Just show text if no image available
                    self.profile_image_label.setText("Face ID\nRegistered")
                    self.profile_image_label.setStyleSheet(
                        "background-color: #e0f0e0; border: 1px solid #60a060; color: #308030;"
                        "font-weight: bold; font-size: 16px; qproperty-alignment: AlignCenter;"
                    )
            else:
                self.face_status_label.setText("No face registered")
                self.profile_image_label.setText("No Face ID\nRegistered")
                self.profile_image_label.setStyleSheet(
                    "background-color: #f0e0e0; border: 1px solid #a06060; color: #803030;"
                    "font-weight: bold; font-size: 16px; qproperty-alignment: AlignCenter;"
                )

            # Load courses
            self.load_courses()

            # Load today's classes
            self.load_todays_classes()

            # Load statistics
            self.load_statistics_courses()
            self.load_student_statistics()

        except Exception as e:
            print(f"Error loading student data: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"Failed to load student data: {str(e)}")

    def load_courses(self):
        try:
            # Clear table
            self.courses_table.setRowCount(0)

            # Get courses this student is enrolled in
            courses = self.database.get_student_courses(self.student_id)

            if not courses:
                return

            # Add to table
            for i, course in enumerate(courses):
                if not course:
                    continue

                self.courses_table.insertRow(i)

                # Fixed column mapping based on get_student_courses query:
                # 0: reference_number, 1: code, 2: name, 3: section, 4: start_time, 5: end_time, 6: classroom, 7: days
                try:
                    reference_number = course[0] if len(course) > 0 else "N/A"  # reference_number
                    code = course[1] if len(course) > 1 else "N/A"             # code
                    name = course[2] if len(course) > 2 else "N/A"             # name
                    section = course[3] if len(course) > 3 else "N/A"          # section
                    start_time = course[4] if len(course) > 4 else "N/A"       # start_time
                    end_time = course[5] if len(course) > 5 else "N/A"         # end_time
                    classroom = course[6] if len(course) > 6 else "N/A"        # classroom (FIXED)
                    days = course[7] if len(course) > 7 else "N/A"             # days

                    time_str = f"{start_time} - {end_time}"

                    # Table columns: Ref #, Code, Name, Section, Days, Time, Room
                    self.courses_table.setItem(i, 0, QTableWidgetItem(str(reference_number)))  # Ref #
                    self.courses_table.setItem(i, 1, QTableWidgetItem(code))                   # Code
                    self.courses_table.setItem(i, 2, QTableWidgetItem(name))                   # Name
                    self.courses_table.setItem(i, 3, QTableWidgetItem(section))                # Section
                    self.courses_table.setItem(i, 4, QTableWidgetItem(days))                   # Days
                    self.courses_table.setItem(i, 5, QTableWidgetItem(time_str))               # Time
                    self.courses_table.setItem(i, 6, QTableWidgetItem(classroom))              # Room (FIXED)

                except Exception as e:
                    print(f"Error adding course to table: {e}")
                    continue
        except Exception as e:
            print(f"Error loading courses: {e}")
            import traceback
            traceback.print_exc()

    def load_todays_classes(self):
        """Load today's classes with error handling"""
        try:
            # Clear table
            self.todays_classes_table.setRowCount(0)

            # Get today's day of week
            today = datetime.datetime.now().strftime("%a")  # e.g., "Mon", "Tue", etc.

            # Get all courses
            courses = self.database.get_student_courses(self.student_id)
            if not courses:
                return

            # Filter courses for today
            todays_courses = []
            for course in courses:
                if not course:
                    continue

                # Check if days field exists and contains today
                days = course[7] if len(course) > 7 else ""
                if days and today in days:
                    todays_courses.append(course)

            # Add to table
            for i, course in enumerate(todays_courses):
                self.todays_classes_table.insertRow(i)

                # Fixed column mapping
                code = course[1] if len(course) > 1 else "N/A"
                name = course[2] if len(course) > 2 else "N/A"
                section = course[3] if len(course) > 3 else "N/A"
                start_time = course[4] if len(course) > 4 else "N/A"
                end_time = course[5] if len(course) > 5 else "N/A"
                classroom = course[6] if len(course) > 6 else "N/A"  # FIXED

                time_str = f"{start_time} - {end_time}"

                # Table columns: Code, Section, Name, Time, Room
                self.todays_classes_table.setItem(i, 0, QTableWidgetItem(code))      # Code
                self.todays_classes_table.setItem(i, 1, QTableWidgetItem(section))   # Section
                self.todays_classes_table.setItem(i, 2, QTableWidgetItem(name))      # Name
                self.todays_classes_table.setItem(i, 3, QTableWidgetItem(time_str))  # Time
                self.todays_classes_table.setItem(i, 4, QTableWidgetItem(classroom)) # Room (FIXED)
        except Exception as e:
            print(f"Error loading today's classes: {e}")
            import traceback
            traceback.print_exc()

    def load_statistics_courses(self):
        """Load courses for the statistics tab dropdown with error handling"""
        try:
            # Clear existing items except "All Courses"
            while self.stats_course_combo.count() > 1:
                self.stats_course_combo.removeItem(1)

            # Get courses this student is enrolled in
            courses = self.database.get_student_courses(self.student_id)
            if not courses:
                return

            # Add to dropdown
            for course in courses:
                if not course or len(course) < 4:
                    continue

                reference_number = course[0]
                code = course[1] if len(course) > 1 else "N/A"
                name = course[2] if len(course) > 2 else "N/A"
                section = course[3] if len(course) > 3 else "N/A"

                self.stats_course_combo.addItem(f"{code}-{name} {section}", reference_number)
        except Exception as e:
            print(f"Error loading statistics courses: {e}")
            import traceback
            traceback.print_exc()

    def load_student_statistics(self):
        """Load student statistics and update the display"""
        try:
            # Get selected course
            selected_course_data = self.stats_course_combo.currentData()
            course_id = selected_course_data if selected_course_data is not None else None

            # Get attendance statistics
            stats = self.database.get_student_attendance_stats(self.student_id, course_id)
            
            # Update statistics display
            total_days = stats.get('total_days', 0)
            present_count = stats.get(STATUS_PRESENT, 0)
            late_count = stats.get(STATUS_LATE, 0)
            absent_count = stats.get(STATUS_ABSENT, 0)
            unauthorized_count = stats.get(STATUS_UNAUTHORIZED_DEPARTURE, 0)

            # Update labels
            self.total_classes_label.setText(str(total_days))
            self.present_count_label.setText(str(present_count))
            self.late_count_label.setText(str(late_count))
            self.absent_count_label.setText(str(absent_count))
            self.unauthorized_count_label.setText(str(unauthorized_count))

            # Calculate attendance rate
            if total_days > 0:
                attendance_rate = ((present_count + late_count) / total_days) * 100
                self.attendance_rate_label.setText(f"{attendance_rate:.1f}%")

                # Update status based on attendance rate
                if attendance_rate >= 90:
                    status_text = "Good Standing"
                    status_color = "green"
                elif attendance_rate >= 85:
                    status_text = "Warning"
                    status_color = "#FFC107"
                elif attendance_rate >= 80:
                    status_text = "At Risk"
                    status_color = "#FF9800"
                else:
                    status_text = "Below Threshold"
                    status_color = "red"

                self.status_label.setText(status_text)
                self.status_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {status_color};")
                self.attendance_rate_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {status_color};")
            else:
                self.attendance_rate_label.setText("No Data")
                self.status_label.setText("No Data")

            # Update chart if available
            if self.matplotlib_available and hasattr(self, 'attendance_chart'):
                self.attendance_chart.plot_attendance_pie_chart(stats)

            # Load attendance records for the table
            self.load_attendance_records_to_stats_table(course_id)

            # Update absence list
            self.update_absence_list(course_id)

            # Update attendance status widget if available
            if hasattr(self, 'attendance_status_widget') and hasattr(self.attendance_status_widget, 'update_data'):
                attendance_data = {
                    'percentage': ((present_count + late_count) / total_days * 100) if total_days > 0 else 100.0,
                    'absence_count': absent_count + unauthorized_count,
                    'total_lectures': total_days
                }
                self.attendance_status_widget.update_data(attendance_data)

        except Exception as e:
            print(f"Error loading student statistics: {e}")
            import traceback
            traceback.print_exc()

    def load_attendance_records_to_stats_table(self, course_id=None):
        """Load attendance records to the statistics tab table with enhanced formatting and error handling"""
        try:
            # Clear the table
            self.stats_attendance_table.setRowCount(0)

            # Get attendance records
            records = self.database.get_student_attendance(self.student_id, course_id)
            if not records:
                return

            # Add to table with enhanced formatting
            for i, record in enumerate(records):
                if not record or len(record) < 3:
                    continue

                course_name = record[0]
                date = record[1]
                status = record[2]
                first_checkin = record[3] if len(record) > 3 and record[3] else ""
                second_checkin = record[4] if len(record) > 4 and record[4] else ""

                self.stats_attendance_table.insertRow(i)
                self.stats_attendance_table.setItem(i, 0, QTableWidgetItem(course_name))
                self.stats_attendance_table.setItem(i, 1, QTableWidgetItem(date))

                # Format status with color
                status_item = QTableWidgetItem(status)
                if status == STATUS_PRESENT:
                    status_item.setForeground(QBrush(QColor(0, 128, 0)))  # Green
                    status_item.setFont(QFont("Arial", 10, QFont.Bold))
                elif status == STATUS_LATE:
                    status_item.setForeground(QBrush(QColor(255, 165, 0)))  # Orange
                    status_item.setFont(QFont("Arial", 10, QFont.Bold))
                elif status == STATUS_ABSENT:
                    status_item.setForeground(QBrush(QColor(255, 0, 0)))  # Red
                    status_item.setFont(QFont("Arial", 10, QFont.Bold))
                elif status == STATUS_UNAUTHORIZED_DEPARTURE:
                    status_item.setForeground(QBrush(QColor(128, 0, 128)))  # Purple
                    status_item.setFont(QFont("Arial", 10, QFont.Bold))

                self.stats_attendance_table.setItem(i, 2, status_item)
                self.stats_attendance_table.setItem(i, 3, QTableWidgetItem(first_checkin))
                self.stats_attendance_table.setItem(i, 4, QTableWidgetItem(second_checkin))
        except Exception as e:
            print(f"Error loading attendance records to stats table: {e}")
            import traceback
            traceback.print_exc()

    def update_absence_list(self, course_id=None):
        """Update the absence list with recent absences"""
        try:
            self.absence_list.clear()
            
            # Get absence dates (this method needs to be implemented)
            absence_dates = self.get_absence_dates(course_id)
            
            for date in absence_dates[:10]:  # Show only last 10 absences
                self.absence_list.addItem(date)
                
        except Exception as e:
            print(f"Error updating absence list: {e}")

    def get_absence_dates(self, course_id=None):
        """Get a list of dates when the student was absent"""
        try:
            # Query for absences
            if course_id:
                self.database.cursor.execute(
                    """
                    SELECT a.date, c.code, c.section
                    FROM attendance a
                    JOIN courses c ON a.course_id = c.reference_number
                    WHERE a.student_id = ? AND a.course_id = ? AND a.status IN (?, ?)
                    ORDER BY a.date DESC
                    """,
                    (self.student_id, course_id, STATUS_ABSENT, STATUS_UNAUTHORIZED_DEPARTURE)
                )
            else:
                self.database.cursor.execute(
                    """
                    SELECT a.date, c.code, c.section
                    FROM attendance a
                    JOIN courses c ON a.course_id = c.reference_number
                    WHERE a.student_id = ? AND a.status IN (?, ?)
                    ORDER BY a.date DESC
                    """,
                    (self.student_id, STATUS_ABSENT, STATUS_UNAUTHORIZED_DEPARTURE)
                )

            absences = self.database.cursor.fetchall()

            # Format the dates with course info
            formatted_dates = [f"{date} ({code}-{section})" for date, code, section in absences]
            return formatted_dates
        except Exception as e:
            print(f"Error getting absence dates: {e}")
            return []

    def calculate_attendance_rate(self, course_id):
        """Calculate attendance rate with error handling"""
        try:
            # Get attendance records for this course
            records = self.database.get_student_attendance(self.student_id, course_id)

            if not records:
                return "N/A"

            # Count attendance status
            present_count = 0
            total_count = 0

            for record in records:
                if not record or len(record) < 3:
                    continue

                # Skip cancelled lectures
                if len(record) > 5 and record[5] == 1:
                    continue

                status = record[2]
                if status == STATUS_PRESENT or status == STATUS_LATE:
                    present_count += 1

                total_count += 1

            if total_count == 0:
                return "N/A"

            # Calculate rate
            rate = present_count / total_count * 100
            return f"{rate:.1f}% ({present_count}/{total_count})"
        except Exception as e:
            print(f"Error calculating attendance rate: {e}")
            return "Error"

    def load_attendance_records(self):
        """Load attendance records for selected course with error handling"""
        try:
            selected_row = self.courses_table.currentRow()
            if selected_row < 0:
                return

            reference_number_item = self.courses_table.item(selected_row, 0)
            if not reference_number_item:
                return

            reference_number = reference_number_item.text()  # This is the course_id

            # Clear attendance table
            self.attendance_table.setRowCount(0)

            # Get attendance records
            records = self.database.get_student_attendance(self.student_id, reference_number)
            if not records:
                return

            # Add to table - including time and second_time
            for i, record in enumerate(records):
                if not record or len(record) < 3:
                    continue

                self.attendance_table.insertRow(i)

                # Course name, date, status, time, second_time
                self.attendance_table.setItem(i, 0, QTableWidgetItem(str(record[0])))
                self.attendance_table.setItem(i, 1, QTableWidgetItem(str(record[1])))
                self.attendance_table.setItem(i, 2, QTableWidgetItem(str(record[2])))
                self.attendance_table.setItem(i, 3, QTableWidgetItem(str(record[3]) if len(record) > 3 and record[3] else ""))
                self.attendance_table.setItem(i, 4, QTableWidgetItem(str(record[4]) if len(record) > 4 and record[4] else ""))
        except Exception as e:
            print(f"Error loading attendance records: {e}")
            import traceback
            traceback.print_exc()

    def change_password(self):
        """Open change password dialog with error handling"""
        try:
            dialog = ChangePasswordDialog(self, self.database, self.student_id)
            dialog.exec_()
        except Exception as e:
            print(f"Error opening change password dialog: {e}")
            QMessageBox.warning(self, "Error", f"Could not open password dialog: {str(e)}")

class AttendanceStatsWidget(QWidget):
    """Fallback attendance widget for student dashboard if the imported one is not available"""

    def __init__(self, parent=None, compact=False):
        super().__init__(parent)
        self.compact = compact
        self.init_ui()

    def init_ui(self):
        # Create a simple layout with basic information
        layout = QVBoxLayout(self)

        # Attendance percentage label
        self.percentage_label = QLabel("Attendance: 100%")
        self.percentage_label.setStyleSheet("font-size: 16px; font-weight: bold; color: green;")
        layout.addWidget(self.percentage_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Status: Good Standing")
        self.status_label.setStyleSheet("font-weight: bold; color: green;")
        layout.addWidget(self.status_label)

        # Absences info
        self.absences_label = QLabel("Absences: 0/0")
        layout.addWidget(self.absences_label)

    def update_data(self, attendance_data):
        """Update widget with attendance data"""
        percentage = attendance_data.get('percentage', 100.0)
        absence_count = attendance_data.get('absence_count', 0)
        total_lectures = attendance_data.get('total_lectures', 0)

        # Update labels
        self.percentage_label.setText(f"Attendance: {percentage:.1f}%")
        self.absences_label.setText(f"Absences: {absence_count}/{total_lectures}")

        # Update progress bar
        self.progress_bar.setValue(int(percentage))

        # Update status
        if percentage >= 90:
            status_text = "GOOD STANDING"
            status_color = "green"
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: green; }")
        elif percentage >= 85:
            status_text = "WARNING"
            status_color = "#FFC107"
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #FFC107; }")
        elif percentage >= 80:
            status_text = "AT RISK"
            status_color = "#FF9800"
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #FF9800; }")
        else:
            status_text = "DENIED"
            status_color = "red"
            self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: red; }")

        self.status_label.setText(f"Status: {status_text}")
        self.status_label.setStyleSheet(f"font-weight: bold; color: {status_color};")
