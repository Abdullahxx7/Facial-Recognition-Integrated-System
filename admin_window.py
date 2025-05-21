import math
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QInputDialog, QLineEdit, QPushButton, QComboBox, QTableWidget,
    QTableWidgetItem, QFormLayout, QTimeEdit, QSpinBox, QMessageBox,
    QHeaderView, QDialog, QDialogButtonBox, QFileDialog, QGroupBox,
    QScrollArea, QDateEdit, QCheckBox, QGridLayout, QSizePolicy, QFrame, QProgressBar,QListWidget, QListWidgetItem, QButtonGroup, QRadioButton
)
from PyQt5.QtCore import Qt, QTime, QTimer, QDate, QSize
from PyQt5.QtGui import QFont, QImage, QPixmap, QPainter, QPen, QColor, QBrush

from datetime import datetime

import cv2
import numpy as np
import os

from config import ROLE_TEACHER, ROLE_STUDENT, ROLE_ADMIN
from attendance_widgets import AdminAttendanceOverviewWidget, TeacherAttendanceWidget
from attendance_tracker import AttendanceTracker

import re
import filetype

class AddUserDialog(QDialog):
    def __init__(self, parent, database):
        super().__init__(parent)

        self.database = database
        self.camera = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.captured_image = None
        self.image_from_file = None

        self.setWindowTitle("Add New User")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)

        # Initialize role attribute with a default before get_next_available_id is called
        self.default_role = ROLE_STUDENT  # Default role

        # Get next available ID
        self.next_id = self.get_next_available_id()

        self.init_ui()

    def get_next_available_id(self):
        """Get the next available ID based on role and existing IDs in the database"""
        try:
            # Before init_ui, use the default role
            if hasattr(self, 'role'):
                selected_role = self.role.currentText()
            else:
                selected_role = self.default_role

            # Different ID ranges based on role
            if selected_role == ROLE_STUDENT:
                # Student IDs start from 4460000001
                prefix = "446"
                min_id = 4460000001
            else:
                # Admin and Teacher IDs start from 1000000001
                prefix = "100"
                min_id = 1000000001

            # Query existing IDs with the appropriate prefix
            self.database.cursor.execute(
                "SELECT id FROM users WHERE id LIKE ? AND id GLOB '[0-9]*'",
                (f"{prefix}%",)
            )
            existing_ids = self.database.cursor.fetchall()

            # Convert to integers when possible and find max
            numeric_ids = []
            for id_tuple in existing_ids:
                try:
                    numeric_ids.append(int(id_tuple[0]))
                except (ValueError, TypeError):
                    pass  # Skip non-numeric IDs

            if numeric_ids:
                # Return the next ID after the maximum existing ID
                next_id = max(numeric_ids) + 1
                # Make sure it's not less than our minimum starting ID
                return str(max(next_id, min_id))
            else:
                # No existing IDs with this prefix, return the starting ID
                return str(min_id)
        except Exception as e:
            print(f"Error getting next ID: {e}")
            # Default values in case of an error
            if hasattr(self, 'role') and self.role.currentText() == ROLE_STUDENT:
                return "4460000001"  # Default student ID
            else:
                return "1000000001"  # Default employee ID

    def init_ui(self):
        layout = QVBoxLayout(self)

        # User form
        form_layout = QFormLayout()

        # Role selection (moved to the top)
        self.role = QComboBox()
        self.role.addItems([ROLE_TEACHER, ROLE_STUDENT, ROLE_ADMIN])
        self.role.setCurrentText(self.default_role)  # Set to default role
        self.role.currentTextChanged.connect(self.on_role_changed)
        form_layout.addRow("Role*:", self.role)

        # Auto-generated ID (read-only)
        self.user_id = QLineEdit(self.next_id)
        self.user_id.setReadOnly(True)
        self.user_id.setStyleSheet("background-color: #f0f0f0;")
        form_layout.addRow("User ID (auto-generated):", self.user_id)

        # Username field (editable for all roles)
        self.username = QLineEdit()
        self.username.setPlaceholderText("Letters only (a-z, A-Z)")
        self.username.textChanged.connect(self.validate_username)
        form_layout.addRow("Username*:", self.username)

        # Email field (new)
        self.email = QLineEdit()
        self.email.setPlaceholderText("example@domain.com")
        self.email.textChanged.connect(self.validate_email)
        form_layout.addRow("Email*:", self.email)

        # Password field
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Password*:", self.password)

        # Full name field
        self.name = QLineEdit()
        form_layout.addRow("Full Name*:", self.name)

        layout.addLayout(form_layout)

        # Photo options for student role (initially hidden)
        self.photo_group = QGroupBox("Photo Capture")
        self.photo_group.setVisible(False)
        photo_layout = QVBoxLayout(self.photo_group)

        # Camera feed label
        self.camera_label = QLabel()
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(320, 240)
        self.camera_label.setMaximumSize(320, 240)
        self.camera_label.setStyleSheet("background-color: black;")
        self.camera_label.setText("No image captured")
        photo_layout.addWidget(self.camera_label)

        # Camera controls
        camera_buttons_layout = QHBoxLayout()

        self.start_camera_button = QPushButton("Start Camera")
        self.start_camera_button.clicked.connect(self.toggle_camera)

        self.capture_button = QPushButton("Capture")
        self.capture_button.clicked.connect(self.capture_image)
        self.capture_button.setEnabled(False)

        self.load_image_button = QPushButton("Load Image from Device")
        self.load_image_button.clicked.connect(self.load_image)

        camera_buttons_layout.addWidget(self.start_camera_button)
        camera_buttons_layout.addWidget(self.capture_button)

        photo_layout.addLayout(camera_buttons_layout)
        photo_layout.addWidget(self.load_image_button)

        layout.addWidget(self.photo_group)

        # Validation status label
        self.validation_label = QLabel()
        self.validation_label.setStyleSheet("color: red;")
        layout.addWidget(self.validation_label)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.validate_and_accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

        # Initialize the form based on the default role
        self.on_role_changed(self.role.currentText())

    def validate_username(self):
        """Validate that username contains only letters"""
        username = self.username.text()
        if username and not username.isalpha():
            self.username.setStyleSheet("background-color: #ffe0e0;")  # Light red for invalid
            return False
        else:
            self.username.setStyleSheet("")  # Reset to default
            return True

    def validate_email(self):
        """Validate email format using a simple regex"""
        email = self.email.text()
        # Basic email validation regex
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if email and not re.match(email_regex, email):
            self.email.setStyleSheet("background-color: #ffe0e0;")  # Light red for invalid
            return False
        else:
            self.email.setStyleSheet("")  # Reset to default
            return True

    def on_role_changed(self, role):
        """Update form elements based on selected role"""
        # Update the user ID based on the selected role
        self.user_id.setText(self.get_next_available_id())

        if role == ROLE_STUDENT:
            # Show photo capture section for students
            self.photo_group.setVisible(True)
        else:
            # Hide photo capture section for non-students
            self.photo_group.setVisible(False)
            # Stop camera if it's running
            if self.camera is not None:
                self.stop_camera()

    def toggle_camera(self):
        """Start or stop the camera"""
        if self.camera is None:
            self.start_camera()
        else:
            self.stop_camera()

    def start_camera(self):
        """Start the camera feed"""
        try:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                raise Exception("Could not open camera")

            self.timer.start(30)  # Update every 30ms (approx 33 fps)
            self.start_camera_button.setText("Stop Camera")
            self.capture_button.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "Camera Error", f"Could not start camera: {str(e)}")

    def stop_camera(self):
        """Stop the camera feed"""
        if self.camera is not None:
            self.timer.stop()
            self.camera.release()
            self.camera = None

        self.start_camera_button.setText("Start Camera")
        self.capture_button.setEnabled(False)

    def update_frame(self):
        """Update the camera frame display"""
        ret, frame = self.camera.read()
        if not ret:
            self.stop_camera()
            QMessageBox.warning(self, "Camera Error", "Failed to capture frame.")
            return

        # Convert the frame to a QImage and then to a QPixmap
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        self.camera_label.setPixmap(QPixmap.fromImage(q_image))

        # Store the current frame
        self.current_frame = frame

    def capture_image(self):
        """Capture the current frame from the camera"""
        if hasattr(self, 'current_frame'):
            self.captured_image = self.current_frame.copy()
            self.stop_camera()

            # Show the captured image
            height, width, channel = self.captured_image.shape
            bytes_per_line = 3 * width
            q_image = QImage(self.captured_image.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            self.camera_label.setPixmap(QPixmap.fromImage(q_image))
            self.camera_label.setText("")  # Clear any previous text

    def load_image(self):
        """Load an image from the device"""
        # Stop the camera if it's running
        if self.camera is not None:
            self.stop_camera()

        # Open file dialog to select an image
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select User Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )

        if file_path:
            try:
                # Load the image
                self.image_from_file = cv2.imread(file_path)

                if self.image_from_file is None:
                    raise Exception("Failed to load the image")

                # Convert for display
                height, width, channel = self.image_from_file.shape
                bytes_per_line = 3 * width
                q_image = QImage(self.image_from_file.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
                self.camera_label.setPixmap(QPixmap.fromImage(q_image))
                self.camera_label.setText("")  # Clear any previous text

            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load image: {str(e)}")

    def validate_and_accept(self):
        """Validate all required fields before accepting"""
        errors = []

        # Check username (letters only)
        if not self.username.text():
            errors.append("Username is required")
        elif not self.validate_username():
            errors.append("Username must contain only letters")

        # Check email
        if not self.email.text():
            errors.append("Email is required")
        elif not self.validate_email():
            errors.append("Invalid email format")

        # Check password
        if not self.password.text():
            errors.append("Password is required")

        # Check name
        if not self.name.text():
            errors.append("Full name is required")

        # Check for photo if student
        if self.role.currentText() == ROLE_STUDENT and not (self.captured_image is not None or self.image_from_file is not None):
            errors.append("Photo is required for students (capture or upload)")

        # If we have errors, show them and don't proceed
        if errors:
            self.validation_label.setText("\n".join(errors))
            return

        # If all validations pass, accept the dialog
        self.accept()

    def get_user_data(self):
        """Get the form data as a dictionary"""
        user_id = self.user_id.text()
        username = self.username.text()
        email = self.email.text()
        password = self.password.text()
        name = self.name.text()
        role = self.role.currentText()

        # Prepare the face image if available
        face_image = None
        if role == ROLE_STUDENT:
            if self.captured_image is not None:
                # Convert captured image to binary data
                _, img_encoded = cv2.imencode('.jpg', self.captured_image)
                face_image = img_encoded.tobytes()
            elif self.image_from_file is not None:
                # Convert loaded image to binary data
                _, img_encoded = cv2.imencode('.jpg', self.image_from_file)
                face_image = img_encoded.tobytes()

        return {
            "user_id": user_id,
            "username": username,
            "email": email,
            "password": password,
            "name": name,
            "role": role,
            "face_image": face_image
        }

    def closeEvent(self, event):
        """Clean up camera resources when dialog is closed"""
        if self.camera is not None:
            self.timer.stop()
            self.camera.release()
        event.accept()

class CourseFormWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        form_layout = QFormLayout(self)

        # Basic course info
        self.course_code = QLineEdit()
        self.course_name = QLineEdit()
        self.course_section = QLineEdit()
        self.reference_number = QLineEdit()
        self.course_classroom = QLineEdit()

        # Capacity
        self.course_capacity = QSpinBox()
        self.course_capacity.setMinimum(1)
        self.course_capacity.setMaximum(200)
        self.course_capacity.setValue(30)

        time_layout = QHBoxLayout()

        # Start time controls
        start_time_layout = QHBoxLayout()

        self.start_hour = QComboBox()
        for hour in range(1, 13):
            self.start_hour.addItem(f"{hour:02d}", hour)
        self.start_hour.setCurrentIndex(7)  # Default to 8 AM

        start_time_layout.addWidget(self.start_hour)
        start_time_layout.addWidget(QLabel(":"))

        self.start_minute = QComboBox()
        for minute in range(0, 60, 5):
            self.start_minute.addItem(f"{minute:02d}", minute)
        self.start_minute.setCurrentIndex(0)  # Default to 00 minutes

        start_time_layout.addWidget(self.start_minute)

        self.start_am_pm = QComboBox()
        self.start_am_pm.addItem("AM", "AM")
        self.start_am_pm.addItem("PM", "PM")
        self.start_am_pm.setCurrentIndex(0)  # Default to AM

        start_time_layout.addWidget(self.start_am_pm)
        time_layout.addLayout(start_time_layout)

        # End time controls
        end_time_layout = QHBoxLayout()

        self.end_hour = QComboBox()
        for hour in range(1, 13):
            self.end_hour.addItem(f"{hour:02d}", hour)
        self.end_hour.setCurrentIndex(8)  # Default to 9 AM

        end_time_layout.addWidget(self.end_hour)
        end_time_layout.addWidget(QLabel(":"))

        self.end_minute = QComboBox()
        for minute in range(0, 60, 5):
            self.end_minute.addItem(f"{minute:02d}", minute)
        self.end_minute.setCurrentIndex(0)  # Default to 00 minutes

        end_time_layout.addWidget(self.end_minute)

        self.end_am_pm = QComboBox()
        self.end_am_pm.addItem("AM", "AM")
        self.end_am_pm.addItem("PM", "PM")
        self.end_am_pm.setCurrentIndex(0)  # Default to AM

        end_time_layout.addWidget(self.end_am_pm)
        time_layout.addLayout(end_time_layout)

        # Date range
        date_layout = QHBoxLayout()

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setDisplayFormat("yyyy-MM-dd")

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate().addMonths(4))  # Default to 4 months from now
        self.end_date.setDisplayFormat("yyyy-MM-dd")

        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.end_date)

        # Days of the week
        days_layout = QHBoxLayout()
        self.days_checkboxes = {}

        for day in ["Sun", "Mon", "Tue", "Wed", "Thu"]:
            checkbox = QCheckBox(day)
            checkbox.setChecked(False)  # Changed: Days unchecked by default
            self.days_checkboxes[day] = checkbox
            days_layout.addWidget(checkbox)

        # Add all the form fields
        form_layout.addRow("Course Code:", self.course_code)
        form_layout.addRow("Course Name:", self.course_name)
        form_layout.addRow("Section:", self.course_section)
        form_layout.addRow("Reference Number:", self.reference_number)
        form_layout.addRow("Classroom:", self.course_classroom)
        form_layout.addRow("Capacity:", self.course_capacity)
        form_layout.addRow("Time:", time_layout)
        form_layout.addRow("Date Range:", date_layout)
        form_layout.addRow("Days:", days_layout)

    def load_existing_courses(self):
        """Load existing course codes and names from the database"""
        try:
            # Clear existing items except for "New Course"
            while self.existing_course_combo.count() > 1:
                self.existing_course_combo.removeItem(1)

            # Get unique course codes with names
            if hasattr(self, 'parent') and hasattr(self.parent(), 'database'):
                database = self.parent().database
                
                # Get all courses ordered by code and section
                database.cursor.execute(
                    """
                    SELECT DISTINCT code, name, section, reference_number 
                    FROM courses 
                    ORDER BY code, section
                    """
                )
                courses = database.cursor.fetchall()

                for code, name, section, ref_num in courses:
                    display_text = f"{code}: {name} (Section {section})"
                    self.existing_course_combo.addItem(display_text, (code, name, section, ref_num))

        except Exception as e:
            print(f"Error loading existing courses: {e}")

    def on_course_selected(self, index):
        """Handle when a course is selected from the dropdown"""
        # Get the selected course data
        selected_data = self.existing_course_combo.currentData()

        if not selected_data:  # New course selected
            # Enable all fields and clear them
            self.course_code.setEnabled(True)
            self.course_name.setEnabled(True)
            self.course_code.clear()
            self.course_name.clear()
            self.course_section.setText("171")  # Default first section is 171
            self.reference_number.clear()
            self.reference_number.setPlaceholderText("Enter manually for new course")
            self.course_classroom.clear()

            # Reset other fields to defaults
            for checkbox in self.days_checkboxes.values():
                checkbox.setChecked(False)
        else:
            # Existing course selected, auto-fill code and name
            code, name, section, ref_num = selected_data
            self.course_code.setText(code)
            self.course_name.setText(name)
            self.course_section.setText(section)
            self.reference_number.setText(str(ref_num))

            # Disable code and name fields
            self.course_code.setEnabled(False)
            self.course_name.setEnabled(False)

            # Clear classroom field
            self.course_classroom.clear()

            # Get course details from database
            try:
                if hasattr(self, 'parent') and hasattr(self.parent(), 'database'):
                    database = self.parent().database
                    course = database.get_course_by_id(ref_num)
                    
                    if course:
                        # Update form with course details
                        self.course_classroom.setText(course[7] or "")  # classroom
                        self.course_capacity.setValue(int(course[6]))   # capacity
                        
                        # Parse and set time
                        start_time = course[4]  # start_time
                        end_time = course[5]    # end_time
                        
                        if start_time:
                            start_hour, start_minute, start_ampm = self.parse_time(start_time)
                            self.start_hour.setCurrentText(f"{start_hour:02d}")
                            self.start_minute.setCurrentText(f"{start_minute:02d}")
                            self.start_am_pm.setCurrentText(start_ampm)
                            
                        if end_time:
                            end_hour, end_minute, end_ampm = self.parse_time(end_time)
                            self.end_hour.setCurrentText(f"{end_hour:02d}")
                            self.end_minute.setCurrentText(f"{end_minute:02d}")
                            self.end_am_pm.setCurrentText(end_ampm)
                        
                        # Set dates
                        if course[8]:  # start_date
                            self.start_date.setDate(QDate.fromString(course[8], "yyyy-MM-dd"))
                        if course[9]:  # end_date
                            self.end_date.setDate(QDate.fromString(course[9], "yyyy-MM-dd"))
                            
                        # Set days
                        if course[10]:  # days
                            days = course[10].split(',')
                            for day, checkbox in self.days_checkboxes.items():
                                checkbox.setChecked(day in days)
                                
            except Exception as e:
                print(f"Error loading course details: {e}")

    def parse_time(self, time_str):
        """Parse time string in format HH:MM AM/PM"""
        try:
            time_obj = datetime.strptime(time_str, "%I:%M %p")
            return time_obj.hour, time_obj.minute, time_str.split()[-1]
        except:
            return 8, 0, "AM"  # Default to 8:00 AM if parsing fails

    def get_days_string(self):
        """Convert checkbox selection to day string format"""
        selected_days = []
        for day, checkbox in self.days_checkboxes.items():
            if checkbox.isChecked():
                selected_days.append(day)

        return ",".join(selected_days) if selected_days else ""

    def set_days_from_string(self, days_string):
        """Set checkboxes from day string format"""
        days_list = days_string.split(",") if days_string else []

        for day, checkbox in self.days_checkboxes.items():
            checkbox.setChecked(day in days_list)

    def get_course_data(self):
        """Get all course data as a dictionary"""
        # Convert time selection to 24-hour format for database
        start_hour = int(self.start_hour.currentData())
        start_minute = int(self.start_minute.currentData())
        start_is_pm = self.start_am_pm.currentText() == "PM"

        if start_is_pm and start_hour < 12:
            start_hour += 12
        elif not start_is_pm and start_hour == 12:
            start_hour = 0

        end_hour = int(self.end_hour.currentData())
        end_minute = int(self.end_minute.currentData())
        end_is_pm = self.end_am_pm.currentText() == "PM"

        if end_is_pm and end_hour < 12:
            end_hour += 12
        elif not end_is_pm and end_hour == 12:
            end_hour = 0

        start_time = f"{start_hour:02d}:{start_minute:02d}"
        end_time = f"{end_hour:02d}:{end_minute:02d}"

        reference_number = None
        if self.reference_number.text().strip():
            try:
                reference_number = int(self.reference_number.text().strip())
            except ValueError:
                # Handle invalid reference number in the caller
                pass

        return {
            "reference_number": reference_number,
            "code": self.course_code.text(),
            "name": self.course_name.text(),
            "section": self.course_section.text(),
            "classroom": self.course_classroom.text(),
            "start_time": start_time,
            "end_time": end_time,
            "days": self.get_days_string(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date.date().toString("yyyy-MM-dd"),
            "capacity": self.course_capacity.value(),
        }

    def set_course_data(self, course_data):
        """Set form fields from course data"""
        if not course_data:
            return

        self.course_code.setText(course_data.get("code", ""))
        self.course_name.setText(course_data.get("name", ""))
        self.course_section.setText(course_data.get("section", ""))
        if "reference_number" in course_data:
            self.reference_number.setText(str(course_data["reference_number"]))
        self.course_classroom.setText(course_data.get("classroom", ""))

        # Set times - convert from 24-hour to 12-hour format with AM/PM
        start_time = course_data.get("start_time", "08:00")
        end_time = course_data.get("end_time", "09:00")

        if ":" in start_time:
            start_hour, start_minute = map(int, start_time.split(':'))

            # Convert to 12-hour format
            start_is_pm = start_hour >= 12
            if start_hour > 12:
                start_hour -= 12
            elif start_hour == 0:
                start_hour = 12

            # Set the values in the UI
            self.start_hour.setCurrentIndex(start_hour - 1)  # -1 because index starts at 0 for hour 1
            minute_index = start_minute // 5 if start_minute < 60 else 0
            self.start_minute.setCurrentIndex(minute_index)
            self.start_am_pm.setCurrentText("PM" if start_is_pm else "AM")

        if ":" in end_time:
            end_hour, end_minute = map(int, end_time.split(':'))

            # Convert to 12-hour format
            end_is_pm = end_hour >= 12
            if end_hour > 12:
                end_hour -= 12
            elif end_hour == 0:
                end_hour = 12

            # Set the values in the UI
            self.end_hour.setCurrentIndex(end_hour - 1)  # -1 because index starts at 0 for hour 1
            minute_index = end_minute // 5 if end_minute < 60 else 0
            self.end_minute.setCurrentIndex(minute_index)
            self.end_am_pm.setCurrentText("PM" if end_is_pm else "AM")

        # Set days
        self.set_days_from_string(course_data.get("days", ""))

        # Set dates
        start_date = course_data.get("start_date")
        if start_date:
            try:
                self.start_date.setDate(QDate.fromString(start_date, "yyyy-MM-dd"))
            except:
                self.start_date.setDate(QDate.currentDate())

        end_date = course_data.get("end_date")
        if end_date:
            try:
                self.end_date.setDate(QDate.fromString(end_date, "yyyy-MM-dd"))
            except:
                self.end_date.setDate(QDate.currentDate().addMonths(4))

        # Set capacity
        self.course_capacity.setValue(course_data.get("capacity", 30))

class EnrollStudentDialog(QDialog):
    def __init__(self, parent, database):
        super().__init__(parent)
        self.database = database
        self.setWindowTitle("Enroll Student")
        self.setMinimumWidth(400)
        self.init_ui()
        self.populate_courses()

    def init_ui(self):
        """Initialize the UI with a list of students instead of a dropdown for multiple selection"""
        layout = QVBoxLayout(self)
        self.setMinimumSize(600, 500)

        form_layout = QFormLayout()

        # Course selection
        self.course_combo = QComboBox()
        self.course_combo.currentIndexChanged.connect(self.update_sections)

        # Section selection
        self.section_combo = QComboBox()

        form_layout.addRow("Course:", self.course_combo)
        form_layout.addRow("Section:", self.section_combo)

        # Student selection with search
        student_layout = QVBoxLayout()

        # Add search field
        search_layout = QHBoxLayout()
        self.student_search = QLineEdit()
        self.student_search.setPlaceholderText("Search for students by name or ID...")
        self.student_search.textChanged.connect(self.search_students)
        search_layout.addWidget(self.student_search)

        student_layout.addLayout(search_layout)

        # Select all checkbox
        select_all_layout = QHBoxLayout()
        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        select_all_layout.addWidget(self.select_all_checkbox)
        select_all_layout.addStretch()

        student_layout.addLayout(select_all_layout)

        # Student list with checkboxes instead of combo
        self.student_list = QListWidget()
        self.student_list.setSelectionMode(QListWidget.ExtendedSelection)
        student_layout.addWidget(self.student_list)

        form_layout.addRow("Students:", student_layout)

        # Add the enrollment info display
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: blue;")
        form_layout.addRow("Status:", self.info_label)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.check_and_accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(button_box)

    def populate_courses(self):
        # Clear existing items
        self.course_combo.clear()
        self.student_list.clear()

        # Get unique course codes with names
        self.database.cursor.execute(
            """
            SELECT DISTINCT code, name FROM courses 
            ORDER BY code
            """
        )
        courses = self.database.cursor.fetchall()

        for course in courses:
            code, name = course
            self.course_combo.addItem(f"{code}: {name}", code)

        # Update sections based on initial course selection
        self.update_sections()

    def toggle_select_all(self, state):
        """Toggle select all checkbox state for student list"""
        for i in range(self.student_list.count()):
            item = self.student_list.item(i)
            if state == Qt.Checked:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

    def populate_students(self):
        """Populate student list with all students and checkboxes"""
        self.student_list.clear()

        # Populate students
        students = self.database.get_users_by_role(ROLE_STUDENT)
        for student in students:
            if not student or len(student) < 3:
                continue

            item = QListWidgetItem(f"{student[2]} ({student[0]})")
            item.setData(Qt.UserRole, student[0])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.student_list.addItem(item)

    def search_students(self):
        """Search for students based on input text, updating the list visibility"""
        search_text = self.student_search.text().strip().lower()

        # If search is empty, show all students
        if not search_text:
            # Show all items
            for i in range(self.student_list.count()):
                self.student_list.item(i).setHidden(False)
            return

        # Hide/show students based on search text
        for i in range(self.student_list.count()):
            item = self.student_list.item(i)
            item_text = item.text().lower()

            if search_text in item_text:
                item.setHidden(False)
            else:
                item.setHidden(True)

    def update_sections(self):
        """Update the sections combo based on the selected course code"""
        self.section_combo.clear()

        course_code = self.course_combo.currentData()
        if not course_code:
            return

        # Get all sections for this course
        self.database.cursor.execute(
            """
            SELECT reference_number, section, capacity, 
                  (SELECT COUNT(*) FROM enrollments WHERE course_id = c.reference_number) as enrolled
            FROM courses c
            WHERE code = ?
            ORDER BY section
            """,
            (course_code,)
        )
        sections = self.database.cursor.fetchall()

        for section in sections:
            # Show section with enrolled/capacity info
            reference_number, section_num, capacity, enrolled = section

            section_text = f"{section_num} ({enrolled}/{capacity})"
            self.section_combo.addItem(section_text, reference_number)

        # Populate students if empty
        if self.student_list.count() == 0:
            self.populate_students()

        # Update enrollment status
        self.check_enrollment_status()

    def check_enrollment_status(self):
        if self.section_combo.count() == 0 or self.student_list.count() == 0:
            self.info_label.setText("")
            return

        reference_number = self.section_combo.currentData()

        # Check if section is full
        self.database.cursor.execute(
            """
            SELECT capacity, 
                  (SELECT COUNT(*) FROM enrollments WHERE course_id = c.reference_number) as enrolled
            FROM courses c
            WHERE reference_number = ?
            """,
            (reference_number,)
        )
        result = self.database.cursor.fetchone()

        if result:
            capacity, enrolled = result
            if enrolled >= capacity:
                self.info_label.setText("Section is full")
                self.info_label.setStyleSheet("color: red;")
            else:
                spots_left = capacity - enrolled
                self.info_label.setText(f"Available: {spots_left} spots remaining")
                self.info_label.setStyleSheet("color: green;")
        else:
            self.info_label.setText("")

    def check_and_accept(self):
        """Validate selections and enforce constraints for student enrollment"""
        if self.section_combo.count() == 0 or self.student_list.count() == 0:
            QMessageBox.warning(self, "Error", "Please select course, section and at least one student")
            return

        reference_number = self.section_combo.currentData()

        if not reference_number:
            QMessageBox.warning(self, "Error", "Please select a valid course section")
            return

        # Get the course code for the selected section
        self.database.cursor.execute(
            """
            SELECT code FROM courses WHERE reference_number = ?
            """,
            (reference_number,)
        )
        result = self.database.cursor.fetchone()
        if not result:
            QMessageBox.warning(self, "Error", "Could not find course code for selected section")
            return

        course_code = result[0]

        # Get all selected students
        selected_students = []
        for i in range(self.student_list.count()):
            item = self.student_list.item(i)
            if item.checkState() == Qt.Checked:
                student_id = item.data(Qt.UserRole)
                student_name = item.text().split(" (")[0]  # Extract name from list item
                selected_students.append((student_id, student_name))

        if not selected_students:
            QMessageBox.warning(self, "Error", "Please select at least one student to enroll")
            return

        # Check for students already enrolled in this section
        already_enrolled_in_section = []
        already_enrolled_in_course = []

        for student_id, student_name in selected_students:
            # Check if student is already enrolled in this section
            self.database.cursor.execute(
                """
                SELECT COUNT(*) FROM enrollments
                WHERE course_id = ? AND student_id = ?
                """,
                (reference_number, student_id)
            )
            is_enrolled_in_section = self.database.cursor.fetchone()[0] > 0

            if is_enrolled_in_section:
                already_enrolled_in_section.append(student_name)
                continue

            # Check if student is already enrolled in another section of the same course
            self.database.cursor.execute(
                """
                SELECT e.student_id 
                FROM enrollments e
                JOIN courses c ON e.course_id = c.reference_number
                WHERE e.student_id = ? AND c.code = ? AND c.reference_number != ?
                """,
                (student_id, course_code, reference_number)
            )
            is_enrolled_in_course = self.database.cursor.fetchone() is not None

            if is_enrolled_in_course:
                already_enrolled_in_course.append(student_name)

        # Show warnings if needed
        if already_enrolled_in_section:
            QMessageBox.warning(
                self,
                "Already Enrolled",
                f"The following students are already enrolled in this section:\n\n{', '.join(already_enrolled_in_section)}"
            )

        if already_enrolled_in_course:
            QMessageBox.warning(
                self,
                "Already Enrolled in Course",
                f"The following students are already enrolled in another section of this course:\n\n{', '.join(already_enrolled_in_course)}"
            )

        # If all students are already enrolled, don't proceed
        valid_students = [(s_id, s_name) for s_id, s_name in selected_students
                         if s_name not in already_enrolled_in_section and s_name not in already_enrolled_in_course]

        if not valid_students:
            return

        # Check section capacity
        self.database.cursor.execute(
            """
            SELECT capacity, 
                  (SELECT COUNT(*) FROM enrollments WHERE course_id = c.reference_number) as enrolled
            FROM courses c
            WHERE reference_number = ?
            """,
            (reference_number,)
        )
        result = self.database.cursor.fetchone()

        if result:
            capacity, current_enrolled = result
            available = capacity - current_enrolled

            if available < len(valid_students):
                reply = QMessageBox.question(
                    self,
                    "Capacity Warning",
                    f"This section only has {available} spots available but you're trying to enroll {len(valid_students)} students. Would you like to enroll as many students as possible?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply == QMessageBox.No:
                    return

                # Limit to available capacity
                if available <= 0:
                    QMessageBox.warning(self, "Section Full", "This section is at full capacity.")
                    return

                valid_students = valid_students[:available]

        # All checks passed, accept the dialog
        self.selected_students = valid_students
        self.course_id = reference_number
        self.accept()

    def get_enrollment_data(self):
        """Return enrollment data with multiple students"""
        return {
            "course_id": self.course_id,
            "students": self.selected_students
        }

class FaceRegistrationDialog(QDialog):
    def __init__(self, parent, database, face_recognition_system, student_id):
        super().__init__(parent)

        self.database = database
        self.face_recognition_system = face_recognition_system
        self.student_id = student_id

        self.camera = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        self.face_encoding = None
        self.image_from_file = None
        self.current_image = None

        student_data = self.database.get_user_by_id(student_id)
        student_name = student_data[3] if student_data else f"Student {student_id}"

        self.setWindowTitle(f"Register Face for {student_name}")
        self.setMinimumSize(640, 520)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel("Position the student's face in the camera view and press 'Capture', or load an image from your device.")
        instructions.setAlignment(Qt.AlignCenter)
        layout.addWidget(instructions)

        # Camera feed
        self.camera_label = QLabel()
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setStyleSheet("background-color: black;")
        layout.addWidget(self.camera_label)

        # Camera controls
        camera_buttons_layout = QHBoxLayout()

        self.start_camera_button = QPushButton("Start Camera")
        self.start_camera_button.clicked.connect(self.toggle_camera)

        self.capture_button = QPushButton("Capture")
        self.capture_button.clicked.connect(self.capture_face)
        self.capture_button.setEnabled(False)

        camera_buttons_layout.addWidget(self.start_camera_button)
        camera_buttons_layout.addWidget(self.capture_button)

        layout.addLayout(camera_buttons_layout)

        # Load image button
        load_button_layout = QHBoxLayout()

        self.load_image_button = QPushButton("Load Image from Device")
        self.load_image_button.clicked.connect(self.load_image)

        load_button_layout.addWidget(self.load_image_button)
        layout.addLayout(load_button_layout)

        # Save and cancel buttons
        buttons_layout = QHBoxLayout()

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_face)
        self.save_button.setEnabled(False)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(cancel_button)

        layout.addLayout(buttons_layout)

    def toggle_camera(self):
        if self.camera is None:
            self.start_camera()
        else:
            self.stop_camera()

    def start_camera(self):
        try:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                raise Exception("Could not open camera")

            self.camera_active = True
            self.timer.start(30)  # Update every 30ms (approx 33 fps)
            self.start_camera_button.setText("Stop Camera")
            self.capture_button.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "Camera Error", f"Could not start camera: {str(e)}")

    def stop_camera(self):
        if self.camera is not None:
            self.timer.stop()
            self.camera.release()
            self.camera = None

        self.start_camera_button.setText("Start Camera")
        self.capture_button.setEnabled(False)

    def update_frame(self):
        ret, frame = self.camera.read()
        if not ret:
            self.stop_camera()
            QMessageBox.warning(self, "Camera Error", "Failed to capture frame.")
            return

        # Convert the frame to a QImage and then to a QPixmap
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        self.camera_label.setPixmap(QPixmap.fromImage(q_image))

        # Store the current frame
        self.current_frame = frame

    def load_image(self):
        # Stop the camera if it's running
        if self.camera is not None:
            self.stop_camera()

        # Open file dialog to select an image
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Face Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp)"
        )

        if file_path:
            try:
                # Load the image
                self.image_from_file = cv2.imread(file_path)

                if self.image_from_file is None:
                    raise Exception("Failed to load the image")

                # Store the current image
                self.current_image = self.image_from_file.copy()

                # Convert the image for display
                height, width, channel = self.image_from_file.shape
                bytes_per_line = 3 * width
                q_image = QImage(self.image_from_file.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
                self.camera_label.setPixmap(QPixmap.fromImage(q_image))

                # Try to encode the face immediately
                self.face_encoding = self.face_recognition_system.encode_face(self.image_from_file)

                if self.face_encoding:
                    QMessageBox.information(self, "Success", "Face detected in image! Click 'Save' to register.")
                    self.save_button.setEnabled(True)
                else:
                    QMessageBox.warning(self, "Error", "No face detected in the image. Please try another image.")

            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load image: {str(e)}")

    def capture_face(self):
        if hasattr(self, 'current_frame'):
            # Store the current image
            self.current_image = self.current_frame.copy()

            # Try to encode the face
            self.face_encoding = self.face_recognition_system.encode_face(self.current_frame)

            if self.face_encoding:
                QMessageBox.information(self, "Success", "Face captured successfully! Click 'Save' to register.")
                self.save_button.setEnabled(True)
            else:
                QMessageBox.warning(self, "Error", "No face detected. Please try again.")

    def save_face(self):
        if self.face_encoding and self.current_image is not None:
            # Convert the image to binary data for storage
            _, img_encoded = cv2.imencode('.jpg', self.current_image)
            img_binary = img_encoded.tobytes()

            # Update the user's face encoding and image in the database
            self.database.update_user(
                self.student_id,
                None,  # No username change
                None,  # No password change
                None,  # No name change
                None,  # No role change
                None,  # No email change
                self.face_encoding,
                img_binary  # Store the face image
            )

            # Reload face encodings in the recognition system
            self.face_recognition_system.load_face_encodings()

            QMessageBox.information(self, "Success", "Face registered successfully!")
            self.accept()

    def closeEvent(self, event):
        # Clean up camera resources
        if self.camera is not None:
            self.timer.stop()
            self.camera.release()
        event.accept()

class StudentImageDialog(QDialog):
    def __init__(self, parent, student_id, student_name, face_recognition_system):
        super().__init__(parent)

        self.database = parent.database
        self.face_recognition_system = face_recognition_system

        self.setWindowTitle(f"Student Image: {student_name}")
        self.setMinimumSize(400, 500)

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

            present_count = attendance_stats.get('Present', 0)
            late_count = attendance_stats.get('Late', 0)
            absent_count = attendance_stats.get('Absent', 0)
            early_dismissal_count = attendance_stats.get('Early Dismissal', 0)
            total = present_count + absent_count + late_count + early_dismissal_count

            attendance_rate = f"{present_count}/{total}" if total > 0 else "N/A"

            info_layout.addRow("ID:", QLabel(student_id))
            info_layout.addRow("Username:", username_label)
            info_layout.addRow("Full Name:", name_label)
            info_layout.addRow("Present Days:", QLabel(str(present_count)))
            info_layout.addRow("Late Days:", QLabel(str(late_count)))
            info_layout.addRow("Absent Days:", QLabel(str(absent_count)))
            info_layout.addRow("Early Dismissals:", QLabel(str(early_dismissal_count)))
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

class AdminWindow(QMainWindow):
    def __init__(self, app, database, face_recognition_system, admin_id):
        self.app = app
        super().__init__()

        self.database = database
        self.face_recognition_system = face_recognition_system
        self.admin_id = admin_id
        self.attendance_tracker = AttendanceTracker(database)
        admin_data = self.database.get_user_by_id(admin_id)

        self.setWindowTitle(f"Admin Panel - {admin_data[3]}")
        self.setMinimumSize(800, 600)

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
        self.users_tab = QWidget()
        self.courses_tab = QWidget()
        self.enrollment_tab = QWidget()
        self.teacher_assignment_tab = QWidget()
        self.stats_tab = QWidget()
        self.attendance_tab = QWidget()

        tab_widget.addTab(self.users_tab, "Users")
        tab_widget.addTab(self.courses_tab, "Courses")
        tab_widget.addTab(self.enrollment_tab, "Student Enrollment")
        tab_widget.addTab(self.teacher_assignment_tab, "Teacher Assignment")
        tab_widget.addTab(self.stats_tab, "Statistics & Records")
        tab_widget.addTab(self.attendance_tab, "Attendance Monitoring")

        # Set up each tab
        self.setup_users_tab()
        self.setup_courses_tab()
        self.setup_enrollment_tab()
        self.setup_teacher_assignment_tab()
        self.setup_stats_tab()
        self.setup_attendance_tab()

        # Logout button
        logout_button = QPushButton("Logout")
        logout_button.clicked.connect(self.logout)
        main_layout.addWidget(logout_button)

    def setup_users_tab(self):
        layout = QVBoxLayout(self.users_tab)

        # Search and filter controls
        controls_layout = QHBoxLayout()

        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))

        self.user_search = QLineEdit()
        self.user_search.setPlaceholderText("Search by name or ID...")
        self.user_search.textChanged.connect(self.filter_users_table)
        search_layout.addWidget(self.user_search)

        controls_layout.addLayout(search_layout)

        # Role filter
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Role:"))

        self.role_filter = QComboBox()
        self.role_filter.addItem("All")
        self.role_filter.addItems([ROLE_ADMIN, ROLE_TEACHER, ROLE_STUDENT])
        self.role_filter.currentTextChanged.connect(self.filter_users_table)
        filter_layout.addWidget(self.role_filter)

        controls_layout.addLayout(filter_layout)

        layout.addLayout(controls_layout)

        # Split view - table on left, user details on right
        split_layout = QHBoxLayout()

        # Users table
        table_layout = QVBoxLayout()

        self.users_table = QTableWidget(0, 5)  # Now 5 columns including email
        self.users_table.setHorizontalHeaderLabels(["ID", "Username", "Name", "Email", "Role"])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.users_table.clicked.connect(self.load_user_data)

        table_layout.addWidget(self.users_table)

        # User control buttons
        buttons_layout = QHBoxLayout()

        self.add_user_button = QPushButton("Add User")
        self.add_user_button.clicked.connect(self.show_add_user_dialog)

        self.edit_user_button = QPushButton("Edit User")
        self.edit_user_button.clicked.connect(self.edit_user)
        self.edit_user_button.setEnabled(False)

        self.delete_user_button = QPushButton("Delete User")
        self.delete_user_button.clicked.connect(self.delete_user)
        self.delete_user_button.setEnabled(False)

        self.register_face_button = QPushButton("Register Face")
        self.register_face_button.clicked.connect(self.register_student_face)
        self.register_face_button.setEnabled(False)

        buttons_layout.addWidget(self.add_user_button)
        buttons_layout.addWidget(self.edit_user_button)
        buttons_layout.addWidget(self.delete_user_button)
        buttons_layout.addWidget(self.register_face_button)

        table_layout.addLayout(buttons_layout)

        split_layout.addLayout(table_layout, 3)  # 3:1 ratio

        # User details panel
        details_layout = QVBoxLayout()

        user_info_group = QGroupBox("User Information")
        info_layout = QFormLayout(user_info_group)

        self.user_id_label = QLabel("No user selected")
        self.user_username_label = QLabel("")
        self.user_name_label = QLabel("")
        self.user_role_label = QLabel("")
        self.user_email_label = QLabel("")  # Added email label

        info_layout.addRow("ID:", self.user_id_label)
        info_layout.addRow("Username:", self.user_username_label)
        info_layout.addRow("Name:", self.user_name_label)
        info_layout.addRow("Role:", self.user_role_label)
        info_layout.addRow("Email:", self.user_email_label)  # Display email

        details_layout.addWidget(user_info_group)

        # User image
        image_group = QGroupBox("User Image")
        image_layout = QVBoxLayout(image_group)

        self.user_image_label = QLabel("No image available")
        self.user_image_label.setAlignment(Qt.AlignCenter)
        self.user_image_label.setMinimumSize(200, 200)
        self.user_image_label.setMaximumSize(200, 200)
        self.user_image_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ccc;")

        image_layout.addWidget(self.user_image_label)

        details_layout.addWidget(image_group)
        details_layout.addStretch(1)

        split_layout.addLayout(details_layout, 1)

        layout.addLayout(split_layout)

    def filter_users_table(self):
        """Filter the users table based on search text and role filter"""
        search_text = self.user_search.text().lower()
        role_filter = self.role_filter.currentText()

        for row in range(self.users_table.rowCount()):
            # Get data from row
            user_id = self.users_table.item(row, 0).text().lower()
            username = self.users_table.item(row, 1).text().lower()
            name = self.users_table.item(row, 2).text().lower()
            email = self.users_table.item(row, 3).text().lower() if self.users_table.item(row, 3) else ""
            role = self.users_table.item(row, 4).text()

            # Check if text matches search
            text_match = search_text == "" or search_text in user_id or search_text in username or search_text in name or search_text in email

            # Check if role matches filter
            role_match = role_filter == "All" or role == role_filter

            # Show or hide row
            self.users_table.setRowHidden(row, not (text_match and role_match))

    def setup_courses_tab(self):
        layout = QVBoxLayout(self.courses_tab)

        # Course form at the top
        course_form_group = QGroupBox("Course Details")
        course_form_group.setStyleSheet("QGroupBox { font-weight: bold; }")

        # Create a scroll area for the form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        # Create the course form widget
        self.course_form = CourseFormWidget()
        scroll.setWidget(self.course_form)

        # Add the scroll area to the layout
        course_form_layout = QVBoxLayout(course_form_group)
        course_form_layout.addWidget(scroll)

        layout.addWidget(course_form_group)

        # Course control buttons in the middle
        buttons_layout = QHBoxLayout()

        add_course_button = QPushButton("Add Course")
        add_course_button.clicked.connect(self.add_course)

        update_course_button = QPushButton("Update Course")
        update_course_button.clicked.connect(self.update_course)

        delete_course_button = QPushButton("Delete Course")
        delete_course_button.clicked.connect(self.delete_course)

        buttons_layout.addWidget(add_course_button)
        buttons_layout.addWidget(update_course_button)
        buttons_layout.addWidget(delete_course_button)

        # Add some spacing and centering for the buttons
        button_container = QWidget()
        button_container.setLayout(buttons_layout)

        centered_button_layout = QHBoxLayout()
        centered_button_layout.addStretch()
        centered_button_layout.addWidget(button_container)
        centered_button_layout.addStretch()

        layout.addLayout(centered_button_layout)

        # Courses table at the bottom
        table_group = QGroupBox("Courses")
        table_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        table_layout = QVBoxLayout(table_group)

        # Change from 11 to 10 columns (removing the "ID" column)
        self.courses_table = QTableWidget(0, 10)
        self.courses_table.setHorizontalHeaderLabels([
            "Ref #", "Code", "Name", "Section",
            "Start Time", "End Time", "Capacity", "Classroom",
            "Days", "Date Range"
        ])
        self.courses_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.courses_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.courses_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.courses_table.clicked.connect(self.load_course_data)

        # Set a minimum height for the table to ensure it's visible
        self.courses_table.setMinimumHeight(300)

        table_layout.addWidget(self.courses_table)
        layout.addWidget(table_group)

    def add_course(self):
        """Add a new course with validation"""
        # Get course data from form
        course_data = self.course_form.get_course_data()

        # Validation for required fields
        if not course_data["code"] or not course_data["name"] or not course_data["section"]:
            QMessageBox.warning(self, "Input Error", "Please fill in all required fields.")
            return

        # Get reference number
        reference_number = course_data.get("reference_number")

        # For new courses, always ask for manual input if not provided
        if not reference_number:
            # Suggest a reference number (default or based on existing courses with the same code)
            suggested_ref = 10000  # Default starting reference number

            # Try to get the highest reference number for this course code and increment
            try:
                self.database.cursor.execute(
                    """
                    SELECT MAX(reference_number) FROM courses
                    WHERE code = ?
                    """,
                    (course_data["code"],)
                )
                max_ref = self.database.cursor.fetchone()[0]

                if max_ref:
                    suggested_ref = max_ref + 1
            except Exception as e:
                print(f"Error getting max reference number: {e}")
                # Fallback to default if there's an error

            # Ask user to confirm or change
            reference_number, ok = QInputDialog.getInt(
                self,
                "Enter Reference Number",
                f"Please enter the course reference number for {course_data['code']} section {course_data['section']}:",
                value=suggested_ref,
                min=1,
                max=999999
            )

            if not ok:
                # User cancelled
                return

        # Check if reference number already exists
        self.database.cursor.execute("SELECT COUNT(*) FROM courses WHERE reference_number = ?", (reference_number,))
        exists = self.database.cursor.fetchone()[0] > 0

        if exists:
            QMessageBox.warning(self, "Error", "This reference number already exists. Please use a unique reference number.")
            return

        # Check if code and section combination already exists
        self.database.cursor.execute(
            "SELECT COUNT(*) FROM courses WHERE code = ? AND section = ?",
            (course_data["code"], course_data["section"])
        )
        exists = self.database.cursor.fetchone()[0] > 0

        if exists:
            QMessageBox.warning(self, "Error", "A course with this code and section already exists.")
            return

        # Validate section number format (should start from 171)
        try:
            section_num = int(course_data["section"])
            if section_num < 171:
                QMessageBox.warning(self, "Error", "Section number must be 171 or higher.")
                return
        except (ValueError, TypeError):
            # Non-numeric section, just proceed (though this shouldn't happen)
            pass

        # Add course to database
        try:
            success = self.database.add_course(
                reference_number,
                course_data["code"],
                course_data["name"],
                course_data["section"],
                course_data["start_time"],
                course_data["end_time"],
                course_data["capacity"],
                course_data["classroom"],
                course_data["start_date"],
                course_data["end_date"],
                course_data["days"]
            )

            if success:
                QMessageBox.information(self, "Success", f"New course {course_data['code']} with section {course_data['section']} added successfully.")

                # Refresh the UI
                self.load_courses_table()
                self.load_enrollment_combos()
                self.load_assignment_combos()
                self.load_stats_courses()
            else:
                QMessageBox.warning(self, "Error", "Failed to add course. Course code and section might already exist.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add course: {str(e)}")

    def update_course(self):
        """Update an existing course"""
        selected_row = self.courses_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a course to update.")
            return

        # Get reference number from selected row
        reference_number = int(self.courses_table.item(selected_row, 0).text())

        # Get updated course data from form
        course_data = self.course_form.get_course_data()

        # Validation
        if not course_data["code"] or not course_data["name"] or not course_data["section"]:
            QMessageBox.warning(self, "Input Error", "Please fill in all required fields.")
            return

        # Update course in database
        try:
            success = self.database.update_course(
                reference_number,
                course_data["code"],
                course_data["name"],
                course_data["section"],
                course_data["start_time"],
                course_data["end_time"],
                course_data["capacity"],
                course_data["classroom"],
                course_data["start_date"],
                course_data["end_date"],
                course_data["days"]
            )

            if success:
                QMessageBox.information(self, "Success", "Course updated successfully.")
                self.load_courses_table()
                self.load_enrollment_combos()
                self.load_assignment_combos()
                self.load_stats_courses()
            else:
                QMessageBox.warning(self, "Error", "Failed to update course. Course code and section might already exist.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update course: {str(e)}")

    def setup_enrollment_tab(self):
        layout = QVBoxLayout(self.enrollment_tab)

        # Buttons
        buttons_layout = QHBoxLayout()

        enroll_button = QPushButton("Enroll Student")
        enroll_button.clicked.connect(self.show_enroll_dialog)

        unenroll_button = QPushButton("Unenroll Student")
        unenroll_button.clicked.connect(self.unenroll_student)

        buttons_layout.addWidget(enroll_button)
        buttons_layout.addWidget(unenroll_button)

        layout.addLayout(buttons_layout)

        # Course/Section selection
        selection_layout = QHBoxLayout()

        # Course selection
        course_layout = QVBoxLayout()
        course_layout.addWidget(QLabel("Select Course:"))

        self.enrollment_course_combo = QComboBox()
        self.enrollment_course_combo.currentIndexChanged.connect(self.update_enrollment_sections)
        course_layout.addWidget(self.enrollment_course_combo)

        # Section selection
        section_layout = QVBoxLayout()
        section_layout.addWidget(QLabel("Select Section:"))

        self.enrollment_section_combo = QComboBox()
        self.enrollment_section_combo.currentIndexChanged.connect(self.load_enrollment_data)
        section_layout.addWidget(self.enrollment_section_combo)

        selection_layout.addLayout(course_layout)
        selection_layout.addLayout(section_layout)

        layout.addLayout(selection_layout)

        # Student search
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search Students:"))

        self.enrollment_search = QLineEdit()
        self.enrollment_search.setPlaceholderText("Search by name or ID...")
        self.enrollment_search.textChanged.connect(self.search_enrolled_students)

        search_layout.addWidget(self.enrollment_search)

        reset_search_button = QPushButton("Reset")
        reset_search_button.clicked.connect(self.reset_enrollment_search)
        search_layout.addWidget(reset_search_button)

        layout.addLayout(search_layout)

        # Enrolled students table
        self.enrollment_table = QTableWidget(0, 3)
        self.enrollment_table.setHorizontalHeaderLabels(["ID", "Username", "Name"])
        self.enrollment_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.enrollment_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.enrollment_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.enrollment_table.doubleClicked.connect(self.show_student_image)

        layout.addWidget(QLabel("Enrolled Students:"))
        layout.addWidget(self.enrollment_table)

    def setup_teacher_assignment_tab(self):
        layout = QVBoxLayout(self.teacher_assignment_tab)

        # Search sections for courses and teachers
        search_layout = QHBoxLayout()

        # Course search section
        course_search_layout = QVBoxLayout()
        course_search_layout.addWidget(QLabel("Search Course:"))

        self.assignment_course_search = QLineEdit()
        self.assignment_course_search.setPlaceholderText("Search by course code or name...")
        self.assignment_course_search.textChanged.connect(self.filter_assignment_courses)
        course_search_layout.addWidget(self.assignment_course_search)

        search_layout.addLayout(course_search_layout)

        # Teacher search section
        teacher_search_layout = QVBoxLayout()
        teacher_search_layout.addWidget(QLabel("Search Teacher:"))

        self.assignment_teacher_search = QLineEdit()
        self.assignment_teacher_search.setPlaceholderText("Search by teacher ID or name...")
        self.assignment_teacher_search.textChanged.connect(self.filter_assignment_teachers)
        teacher_search_layout.addWidget(self.assignment_teacher_search)

        search_layout.addLayout(teacher_search_layout)

        # Add search layout to main layout
        layout.addLayout(search_layout)

        # Selection layout
        selection_layout = QHBoxLayout()

        # Course selection
        course_layout = QVBoxLayout()
        course_layout.addWidget(QLabel("Select Course:"))

        self.assignment_course_combo = QComboBox()
        self.assignment_course_combo.currentIndexChanged.connect(self.update_assignment_sections)
        course_layout.addWidget(self.assignment_course_combo)

        # Section selection
        section_layout = QVBoxLayout()
        section_layout.addWidget(QLabel("Select Section:"))

        self.assignment_section_combo = QComboBox()
        self.assignment_section_combo.currentIndexChanged.connect(self.load_assignment_data)
        section_layout.addWidget(self.assignment_section_combo)

        # Teacher selection
        teacher_layout = QVBoxLayout()
        teacher_layout.addWidget(QLabel("Select Teacher:"))

        self.assignment_teacher_combo = QComboBox()
        teacher_layout.addWidget(self.assignment_teacher_combo)

        # Add to selection layout
        selection_layout.addLayout(course_layout)
        selection_layout.addLayout(section_layout)
        selection_layout.addLayout(teacher_layout)

        # Buttons
        buttons_layout = QHBoxLayout()

        assign_button = QPushButton("Assign Teacher")
        assign_button.clicked.connect(self.assign_teacher)

        unassign_button = QPushButton("Unassign Teacher")
        unassign_button.clicked.connect(self.unassign_teacher)

        buttons_layout.addWidget(assign_button)
        buttons_layout.addWidget(unassign_button)

        # Assigned teachers table
        self.assignment_table = QTableWidget(0, 3)
        self.assignment_table.setHorizontalHeaderLabels(["ID", "Username", "Name"])
        self.assignment_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.assignment_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.assignment_table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Add widgets to layout
        layout.addLayout(selection_layout)
        layout.addLayout(buttons_layout)
        layout.addWidget(QLabel("Assigned Teachers:"))
        layout.addWidget(self.assignment_table)

    def filter_assignment_courses(self):
        """Filter courses in the assignment combo box based on search text"""
        search_text = self.assignment_course_search.text().lower()

        # Store previously selected course
        previously_selected_course = self.assignment_course_combo.currentData()

        # Clear the combo box
        self.assignment_course_combo.clear()

        # Get unique course codes with names
        self.database.cursor.execute(
            """
            SELECT DISTINCT code, name FROM courses
            ORDER BY code
            """
        )
        courses = self.database.cursor.fetchall()

        new_index = 0
        selected_index = 0

        # Filter courses and add matching ones to the combo box
        for course in courses:
            code, name = course

            # Check if course matches search criteria
            if not search_text or search_text in code.lower() or search_text in name.lower():
                display_text = f"{code}: {name}"
                self.assignment_course_combo.addItem(display_text, code)

                # Check if this was the previously selected course
                if code == previously_selected_course:
                    selected_index = new_index

                new_index += 1

        # Restore the previous selection if it's still in the list
        if new_index > 0 and selected_index < new_index:
            self.assignment_course_combo.setCurrentIndex(selected_index)
        elif new_index > 0:
            # Select the first item if the previous selection is not available
            self.assignment_course_combo.setCurrentIndex(0)

        # Update sections for the selected course
        self.update_assignment_sections()

    def filter_assignment_teachers(self):
        """Filter teachers in the assignment combo box based on search text"""
        search_text = self.assignment_teacher_search.text().lower()

        # Store previously selected teacher
        previously_selected_teacher = self.assignment_teacher_combo.currentData()

        # Clear the combo box
        self.assignment_teacher_combo.clear()

        # Get teachers
        teachers = self.database.get_users_by_role(ROLE_TEACHER)

        new_index = 0
        selected_index = 0

        # Filter teachers and add matching ones to the combo box
        for teacher in teachers:
            if not teacher or len(teacher) < 3:
                continue

            teacher_id = teacher[0]
            username = teacher[1]
            name = teacher[2]

            # Check if teacher matches search criteria
            if (not search_text or search_text in teacher_id.lower() or
                search_text in username.lower() or search_text in name.lower()):
                display_text = f"{name} ({username})"
                self.assignment_teacher_combo.addItem(display_text, teacher_id)

                # Check if this was the previously selected teacher
                if teacher_id == previously_selected_teacher:
                    selected_index = new_index

                new_index += 1

        # Restore the previous selection if it's still in the list
        if new_index > 0 and selected_index < new_index:
            self.assignment_teacher_combo.setCurrentIndex(selected_index)
        elif new_index > 0:
            # Select the first item if the previous selection is not available
            self.assignment_teacher_combo.setCurrentIndex(0)

    def load_data(self):
        """Load initial data with robust error handling to prevent crashes"""
        try:
            # Load users
            try:
                self.load_users_table()
            except Exception as e:
                print(f"Error loading users table: {e}")
                import traceback
                traceback.print_exc()

            # Load courses
            try:
                self.load_courses_table()
            except Exception as e:
                print(f"Error loading courses table: {e}")
                import traceback
                traceback.print_exc()

            # Load enrollment and assignment combos
            try:
                self.load_enrollment_combos()
            except Exception as e:
                print(f"Error loading enrollment combos: {e}")
                import traceback
                traceback.print_exc()

            try:
                self.load_assignment_combos()
            except Exception as e:
                print(f"Error loading assignment combos: {e}")
                import traceback
                traceback.print_exc()

            try:
                self.load_stats_courses()
            except Exception as e:
                print(f"Error loading stats courses: {e}")
                import traceback
                traceback.print_exc()

        except Exception as e:
            # Catch-all error handler to prevent initialization crashes
            print(f"Critical error in load_data: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Data Loading Error",
                               "There was an error loading some application data. Some features may be unavailable.")

    def load_users_table(self):
        self.users_table.setRowCount(0)

        # Get teachers and students
        teachers = self.database.get_users_by_role(ROLE_TEACHER)
        students = self.database.get_users_by_role(ROLE_STUDENT)
        admins = self.database.get_users_by_role(ROLE_ADMIN)

        all_users = []
        for user in admins:
            # Check if the user tuple has an email field (index 3)
            email = user[3] if len(user) > 3 else ""
            all_users.append((user[0], user[1], user[2], email, ROLE_ADMIN))

        for user in teachers:
            email = user[3] if len(user) > 3 else ""
            all_users.append((user[0], user[1], user[2], email, ROLE_TEACHER))

        for user in students:
            email = user[3] if len(user) > 3 else ""
            all_users.append((user[0], user[1], user[2], email, ROLE_STUDENT))

        # Add users to table
        for i, user in enumerate(all_users):
            self.users_table.insertRow(i)
            for j, value in enumerate(user):
                self.users_table.setItem(i, j, QTableWidgetItem(str(value)))

    def load_courses_table(self):
        self.courses_table.setRowCount(0)

        try:
            courses = self.database.get_all_courses()

            for i, course in enumerate(courses):
                if not course:
                    continue

                self.courses_table.insertRow(i)

                # Extract course data with error handling
                try:
                    # Make sure we have all necessary data (10 fields)
                    if len(course) < 10:
                        print(f"Warning: Course data incomplete: {course}")

                    # Map course data to table columns based on database schema
                    # 0: reference_number, 1: code, 2: name, 3: section, 4: start_time
                    # 5: end_time, 6: capacity, 7: classroom, 8: start_date, 9: end_date, 10: days

                    reference_number = str(course[0]) if len(course) > 0 else ""  # Primary key (reference_number)
                    code = course[1] if len(course) > 1 else ""                   # Code
                    name = course[2] if len(course) > 2 else ""                   # Name
                    section = course[3] if len(course) > 3 else ""                # Section
                    start_time = course[4] if len(course) > 4 else ""             # Start Time
                    end_time = course[5] if len(course) > 5 else ""               # End Time
                    capacity = str(course[6]) if len(course) > 6 else ""          # Capacity
                    classroom = course[7] if len(course) > 7 else ""              # Classroom
                    days = course[10] if len(course) > 10 else ""                 # Days

                    # Format date range
                    start_date = course[8] if len(course) > 8 else ""             # Start date
                    end_date = course[9] if len(course) > 9 else ""               # End date
                    date_range = f"{start_date} to {end_date}" if start_date and end_date else ""

                    # Populate table with each column - ensure indices match table header order
                    self.courses_table.setItem(i, 0, QTableWidgetItem(reference_number))  # Ref Number
                    self.courses_table.setItem(i, 1, QTableWidgetItem(code))              # Code
                    self.courses_table.setItem(i, 2, QTableWidgetItem(name))              # Name
                    self.courses_table.setItem(i, 3, QTableWidgetItem(section))           # Section
                    self.courses_table.setItem(i, 4, QTableWidgetItem(start_time))        # Start Time
                    self.courses_table.setItem(i, 5, QTableWidgetItem(end_time))          # End Time
                    self.courses_table.setItem(i, 6, QTableWidgetItem(capacity))          # Capacity
                    self.courses_table.setItem(i, 7, QTableWidgetItem(classroom))         # Classroom
                    self.courses_table.setItem(i, 8, QTableWidgetItem(days))              # Days
                    self.courses_table.setItem(i, 9, QTableWidgetItem(date_range))        # Date Range
                except Exception as e:
                    print(f"Error loading course {i}: {e}")
                    # Fill remaining cells with empty values
                    for j in range(self.courses_table.columnCount()):
                        if not self.courses_table.item(i, j):
                            self.courses_table.setItem(i, j, QTableWidgetItem(""))
        except Exception as e:
            print(f"Error loading courses table: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to load courses: {str(e)}")

    def load_enrollment_combos(self):
        # Clear combos
        self.enrollment_course_combo.clear()

        # Load unique course codes with names
        self.database.cursor.execute(
            """
            SELECT DISTINCT code, name FROM courses
            ORDER BY code
            """
        )
        courses = self.database.cursor.fetchall()

        for course in courses:
            code, name = course
            self.enrollment_course_combo.addItem(f"{code}: {name}", code)

        # Update sections based on selected course
        self.update_enrollment_sections()

    def search_enrolled_students(self):
        """Search enrolled students by name or ID"""
        search_text = self.enrollment_search.text().lower()

        # If search text is empty, show all enrolled students
        if not search_text:
            for row in range(self.enrollment_table.rowCount()):
                self.enrollment_table.setRowHidden(row, False)
            return

        # Otherwise, filter rows
        for row in range(self.enrollment_table.rowCount()):
            student_id = self.enrollment_table.item(row, 0).text().lower()
            name = self.enrollment_table.item(row, 2).text().lower()

            if search_text in student_id or search_text in name:
                self.enrollment_table.setRowHidden(row, False)
            else:
                self.enrollment_table.setRowHidden(row, True)

    def reset_enrollment_search(self):
        """Reset the enrollment search and show all enrolled students"""
        self.enrollment_search.clear()
        for row in range(self.enrollment_table.rowCount()):
            self.enrollment_table.setRowHidden(row, False)

    def update_enrollment_sections(self):
        """Update the sections combo based on the selected course code"""
        self.enrollment_section_combo.clear()

        course_code = self.enrollment_course_combo.currentData()
        if not course_code:
            return

        # Get all sections for this course with CURRENT enrollment counts
        self.database.cursor.execute(
            """
            SELECT reference_number, section, capacity, 
                  (SELECT COUNT(*) FROM enrollments WHERE course_id = c.reference_number) as enrolled
            FROM courses c
            WHERE code = ?
            ORDER BY section
            """,
            (course_code,)
        )
        sections = self.database.cursor.fetchall()

        for section in sections:
            # section[0] = reference_number, section[1] = section_num, section[2] = capacity, section[3] = enrolled
            reference_number, section_num, capacity, enrolled = section
            self.enrollment_section_combo.addItem(
                f"{section_num} ({enrolled}/{capacity})",
                reference_number
            )

        # Load enrollment data for the first section
        self.load_enrollment_data()

    def load_enrollment_data(self):
        """Load enrolled students for the selected section with immediate data refresh"""
        if self.enrollment_section_combo.count() == 0:
            self.enrollment_table.setRowCount(0)
            return

        course_id = self.enrollment_section_combo.currentData()
        if course_id is None:
            self.enrollment_table.setRowCount(0)
            return

        self.enrollment_table.setRowCount(0)

        # Get the course capacity and current enrollment
        self.database.cursor.execute(
            """
            SELECT capacity, 
                  (SELECT COUNT(*) FROM enrollments WHERE course_id = c.reference_number) as enrolled
            FROM courses c
            WHERE reference_number = ?
            """,
            (course_id,)
        )
        result = self.database.cursor.fetchone()

        # Update section dropdown item to reflect new enrollment count
        if result:
            capacity, enrolled = result
            section_text = self.enrollment_section_combo.currentText()

            if "(" in section_text and ")" in section_text:
                base_text = section_text.split("(")[0]
                new_text = f"{base_text}({enrolled}/{capacity})"
                index = self.enrollment_section_combo.currentIndex()
                self.enrollment_section_combo.setItemText(index, new_text)

        # Get enrolled students with additional student info
        enrolled_students = self.database.get_enrolled_students(course_id)

        for i, student in enumerate(enrolled_students):
            if not student or len(student) < 3:
                continue

            self.enrollment_table.insertRow(i)
            # student[0] = ID, student[1] = username, student[2] = name
            self.enrollment_table.setItem(i, 0, QTableWidgetItem(str(student[0])))
            self.enrollment_table.setItem(i, 1, QTableWidgetItem(str(student[1])))
            self.enrollment_table.setItem(i, 2, QTableWidgetItem(str(student[2])))

    def load_assignment_combos(self):
        # Clear combos
        self.assignment_course_combo.clear()
        self.assignment_teacher_combo.clear()

        # Load unique course codes with names
        self.database.cursor.execute(
            """
            SELECT DISTINCT code, name FROM courses
            ORDER BY code
            """
        )
        courses = self.database.cursor.fetchall()

        for course in courses:
            code, name = course
            self.assignment_course_combo.addItem(f"{code}: {name}", code)

        # Load teachers
        teachers = self.database.get_users_by_role(ROLE_TEACHER)
        for teacher in teachers:
            if not teacher or len(teacher) < 3:
                continue
            self.assignment_teacher_combo.addItem(f"{teacher[2]} ({teacher[1]})", teacher[0])

        # Update sections
        self.update_assignment_sections()

    def update_assignment_sections(self):
        """Update the sections combo based on the selected course code"""
        self.assignment_section_combo.clear()

        course_code = self.assignment_course_combo.currentData()
        if not course_code:
            return

        # Get all sections for this course
        self.database.cursor.execute(
            """
            SELECT reference_number, section
            FROM courses
            WHERE code = ?
            ORDER BY section
            """,
            (course_code,)
        )
        sections = self.database.cursor.fetchall()

        for section in sections:
            if not section or len(section) < 2:
                continue

            reference_number, section_num = section
            self.assignment_section_combo.addItem(
                f"{section_num}",
                reference_number
            )

        # Load assignment data for the first section
        self.load_assignment_data()

    def load_assignment_data(self):
        if self.assignment_section_combo.count() == 0:
            self.assignment_table.setRowCount(0)
            return

        course_id = self.assignment_section_combo.currentData()
        if course_id is None:
            self.assignment_table.setRowCount(0)
            return

        self.assignment_table.setRowCount(0)

        # Get teachers assigned to this course
        assigned_teachers = self.database.get_course_teachers(course_id)

        for i, teacher in enumerate(assigned_teachers):
            if not teacher or len(teacher) < 3:
                continue

            self.assignment_table.insertRow(i)
            # teacher[0] = ID, teacher[1] = username, teacher[2] = name
            self.assignment_table.setItem(i, 0, QTableWidgetItem(str(teacher[0])))
            self.assignment_table.setItem(i, 1, QTableWidgetItem(str(teacher[1])))
            self.assignment_table.setItem(i, 2, QTableWidgetItem(str(teacher[2])))

    def load_user_data(self):
        """Populate the right-hand panel with the user selected in the table.
        Hardened: validates BLOBs and decodes via cv2.imdecode instead of cv2.imread/tempfile.
        """
        from PyQt5.QtGui import QImage, QPixmap
        import numpy as np, cv2

        # Clear previous picture
        self.user_image_label.clear()

        row = self.users_table.currentRow()
        if row < 0:
            return

        uid  = self.users_table.item(row, 0).text()
        uname = self.users_table.item(row, 1).text()
        name  = self.users_table.item(row, 2).text()
        email = self.users_table.item(row, 3).text()
        role  = self.users_table.item(row, 4).text()

        # Basic labels
        self.user_id_label.setText(uid)
        self.user_username_label.setText(uname)
        self.user_name_label.setText(name)
        self.user_role_label.setText(role)
        self.user_email_label.setText(email)

        # Enable edit / delete
        self.edit_user_button.setEnabled(True)
        self.delete_user_button.setEnabled(True)
        self.register_face_button.setEnabled(role == ROLE_STUDENT)

        # Only students have images
        if role != ROLE_STUDENT:
            self.show_neutral_user_icon() if hasattr(self, 'show_neutral_user_icon') else None
            return

        db_row = self.database.get_user_by_id(uid)
        if not db_row:
            self.show_no_face_registered_placeholder() if hasattr(self, 'show_no_face_registered_placeholder') else None
            return

        image_columns = (6, 7, 8)
        for idx in image_columns:
            if idx >= len(db_row):
                continue
            blob = db_row[idx]
            if not blob or not isinstance(blob, (bytes, bytearray)) or len(blob) < 128:
                continue
            if not filetype.is_image(blob):
                continue
            try:
                cv_img = cv2.imdecode(np.frombuffer(blob, np.uint8), cv2.IMREAD_COLOR)
            except cv2.error:
                continue
            if cv_img is None:
                continue

            # Display
            h, w, _ = cv_img.shape
            qimg = QImage(cv_img.data, w, h, 3 * w, QImage.Format_RGB888).rgbSwapped()
            pix = QPixmap.fromImage(qimg).scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.user_image_label.setPixmap(pix)

            # Overlay label
            overlay = QLabel(self.user_image_label)
            overlay.setText("Face ID Registered")
            overlay.setAlignment(Qt.AlignCenter)
            overlay.setStyleSheet("background-color: rgba(0,0,0,120); color: white; font-weight: bold; padding: 5px;")
            overlay.resize(200, 30)
            overlay.move(0, 170)
            overlay.show()
            return

        # fallback
        if len(db_row) > 5 and db_row[5]:
            self.show_face_encoding_placeholder() if hasattr(self, 'show_face_encoding_placeholder') else None
        else:
            self.show_no_face_registered_placeholder() if hasattr(self, 'show_no_face_registered_placeholder') else None

    def show_face_encoding_placeholder(self):
        """Show a placeholder for users with face encoding but no image"""
        # Create a placeholder face image (a green circle with a face icon)
        pixmap = QPixmap(200, 200)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw green background circle
        painter.setBrush(QColor("#e0f0e0"))
        painter.setPen(QPen(QColor("#60a060"), 2))
        painter.drawEllipse(10, 10, 180, 180)

        # Draw a simple face
        painter.setPen(QPen(QColor("#308030"), 3))
        # Draw a smile
        painter.drawArc(50, 50, 100, 100, 45 * 16, 90 * 16)
        # Draw eyes
        painter.drawEllipse(70, 70, 20, 20)
        painter.drawEllipse(110, 70, 20, 20)

        painter.end()

        # Set the image
        self.user_image_label.setPixmap(pixmap)

        # Add text label under the image
        text_label = QLabel("Face ID Registered", self.user_image_label)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setStyleSheet("color: #308030; font-weight: bold;")
        text_label.move(50, 180)  # Position at bottom of image
        text_label.show()

    def show_no_face_registered_placeholder(self):
        """Show a placeholder for students with no face registered"""
        # Create a placeholder for no face registered (red circle with X)
        pixmap = QPixmap(200, 200)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw red background circle
        painter.setBrush(QColor("#f0e0e0"))
        painter.setPen(QPen(QColor("#a06060"), 2))
        painter.drawEllipse(10, 10, 180, 180)

        # Draw X
        painter.setPen(QPen(QColor("#803030"), 4))
        painter.drawLine(50, 50, 150, 150)
        painter.drawLine(50, 150, 150, 50)

        painter.end()

        # Set the image
        self.user_image_label.setPixmap(pixmap)

        # Add text label under the image
        text_label = QLabel("No Face ID Registered", self.user_image_label)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setStyleSheet("color: #803030; font-weight: bold;")
        text_label.move(40, 180)  # Position at bottom of image
        text_label.show()

    def show_neutral_user_icon(self):
        """Show a neutral icon for non-student users"""
        # For non-students, show a neutral icon
        pixmap = QPixmap(200, 200)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw gray background circle
        painter.setBrush(QColor("#e0e0e0"))
        painter.setPen(QPen(QColor("#888888"), 2))
        painter.drawEllipse(10, 10, 180, 180)

        # Draw a user icon
        painter.setPen(QPen(QColor("#555555"), 3))
        # Head
        painter.drawEllipse(75, 50, 50, 50)
        # Body
        painter.drawRoundedRect(60, 110, 80, 70, 10, 10)

        painter.end()

        # Set the image
        self.user_image_label.setPixmap(pixmap)

        # Add text label under the image
        text_label = QLabel("No Image Required", self.user_image_label)
        text_label.setAlignment(Qt.AlignCenter)
        text_label.setStyleSheet("color: #555555; font-weight: bold;")
        text_label.move(50, 180)  # Position at bottom of image
        text_label.show()

    def load_course_data(self):
        selected_row = self.courses_table.currentRow()
        if selected_row < 0:
            return

        # Get data from selected row
        reference_number = int(self.courses_table.item(selected_row, 0).text())
        course = self.database.get_course_by_id(reference_number)

        if not course:
            return

        try:
            course_data = {
                "reference_number": course[0],  # Primary key
                "code": course[1],              # Code
                "name": course[2],              # Name
                "section": course[3],           # Section
                "start_time": course[4],        # Start time
                "end_time": course[5],          # End time
                "capacity": course[6],          # Capacity
                "classroom": course[7],         # Classroom
                "start_date": course[8],        # Start date
                "end_date": course[9],          # End date
                "days": course[10]              # Days
        }
        except IndexError:
            # Handle the case where the course data doesn't have all fields
            QMessageBox.warning(self, "Data Error", "Course data is incomplete or malformed.")
            return

        # Update the form with the course data
        self.course_form.set_course_data(course_data)

    def delete_course(self):
        selected_row = self.courses_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a course to delete.")
            return

        reference_number = int(self.courses_table.item(selected_row, 0).text())

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete this course? This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.database.delete_course(reference_number)
                if success:
                    QMessageBox.information(self, "Success", "Course deleted successfully.")
                    self.load_courses_table()
                    self.load_enrollment_combos()
                    self.load_assignment_combos()
                else:
                    QMessageBox.critical(self, "Error", "Failed to delete course. Please try again.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete course: {str(e)}")

    def show_add_user_dialog(self):
        """Show dialog to add a new user with validation and photo capture"""
        dialog = AddUserDialog(self, self.database)
        if dialog.exec_() == QDialog.Accepted:
            user_data = dialog.get_user_data()

            success = self.database.add_user(
                user_data["user_id"],
                user_data["username"],
                user_data["password"],
                user_data["name"],
                user_data["role"],
                user_data["email"],        # Added email field
                None,                      # No face encoding yet
                user_data["face_image"]    # Include the face image if available
            )

            if success:
                # If user was added successfully and they're a student with a face image
                if user_data["role"] == ROLE_STUDENT and user_data["face_image"]:
                    # Try to generate and save face encoding
                    try:
                        # Load the image from binary data
                        nparr = np.frombuffer(user_data["face_image"], np.uint8)
                        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                        # Generate face encoding
                        face_encoding = self.face_recognition_system.encode_face(img)

                        if face_encoding:
                            # Update the user with the face encoding
                            self.database.update_user(
                                user_data["user_id"],
                                None,  # No username change
                                None,  # No password change
                                None,  # No name change
                                None,  # No role change
                                None,  # No email change
                                face_encoding,  # Add the face encoding
                                None   # No need to update image again
                            )

                            # Reload face encodings in the recognition system
                            self.face_recognition_system.load_face_encodings()
                    except Exception as e:
                        print(f"Error generating face encoding: {e}")
                        # We continue anyway as the user was created

                QMessageBox.information(self, "Success", "User added successfully.")
                self.load_users_table()
                self.load_enrollment_combos()
                self.load_assignment_combos()
            else:
                QMessageBox.warning(self, "Error", "Failed to add user. User ID may already exist.")

    def edit_user(self):
        selected_row = self.users_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a user to edit.")
            return

        user_id = self.users_table.item(selected_row, 0).text()

        # Create a dialog to edit user
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit User")
        dialog.setMinimumWidth(300)

        layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()

        # Show user ID as non-editable
        user_id_label = QLabel(user_id)

        # Get existing values from the table
        current_username = self.user_username_label.text()
        current_name = self.user_name_label.text()
        current_role = self.user_role_label.text()
        current_email = self.user_email_label.text()

        username = QLineEdit(current_username)
        password = QLineEdit()
        password.setEchoMode(QLineEdit.Password)
        password.setPlaceholderText("Leave empty to keep current password")
        name = QLineEdit(current_name)
        email = QLineEdit(current_email)  # Add email field

        role = QComboBox()
        role.addItems([ROLE_TEACHER, ROLE_STUDENT, ROLE_ADMIN])
        current_role_index = role.findText(current_role)
        role.setCurrentIndex(current_role_index)

        # For students, username should not be editable
        if current_role == ROLE_STUDENT:
            username.setText(user_id)
            username.setEnabled(False)

        form_layout.addRow("User ID:", user_id_label)
        form_layout.addRow("Username:", username)
        form_layout.addRow("New Password:", password)
        form_layout.addRow("Full Name:", name)
        form_layout.addRow("Email:", email)  # Add email row
        form_layout.addRow("Role:", role)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        layout.addWidget(button_box)

        if dialog.exec_() == QDialog.Accepted:
            if not username.text() or not name.text():
                QMessageBox.warning(self, "Input Error", "Please fill in username and name.")
                return

            # Password is optional
            password_value = password.text() if password.text() else None

            # For students, ensure username is the same as ID
            username_value = username.text()
            selected_role = role.currentText()
            if selected_role == ROLE_STUDENT and username_value != user_id:
                username_value = user_id

            try:
                self.database.update_user(
                    user_id,
                    username_value,
                    password_value,
                    name.text(),
                    selected_role,
                    email.text()  # Add email to update
                )

                QMessageBox.information(self, "Success", "User updated successfully.")
                self.load_users_table()
                self.load_enrollment_combos()
                self.load_assignment_combos()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update user: {str(e)}")

    def delete_user(self):
        selected_row = self.users_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a user to delete.")
            return

        user_id = self.users_table.item(selected_row, 0).text()
        role = self.users_table.item(selected_row, 4).text()

        # Prevent deleting the only admin
        if role == ROLE_ADMIN:
            # Count how many admins exist
            self.database.cursor.execute("SELECT COUNT(*) FROM users WHERE role = ?", (ROLE_ADMIN,))
            admin_count = self.database.cursor.fetchone()[0]

            if admin_count <= 1:
                QMessageBox.warning(self, "Delete Error", "Cannot delete the only administrator account.")
                return

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete this user? This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.database.delete_user(user_id)
                QMessageBox.information(self, "Success", "User deleted successfully.")
                self.load_users_table()
                self.load_enrollment_combos()
                self.load_assignment_combos()

                # Clear user info
                self.user_id_label.setText("No user selected")
                self.user_username_label.setText("")
                self.user_name_label.setText("")
                self.user_role_label.setText("")
                self.user_email_label.setText("")
                self.user_image_label.setText("No image available")

                # Disable buttons
                self.edit_user_button.setEnabled(False)
                self.delete_user_button.setEnabled(False)
                self.register_face_button.setEnabled(False)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete user: {str(e)}")

    def show_enroll_dialog(self):
        """Show the enrollment dialog with multi-student selection"""
        # Pre-fill with currently selected course/section if available
        pre_selected_course = None
        pre_selected_section = None

        if self.enrollment_section_combo.count() > 0:
            pre_selected_section = self.enrollment_section_combo.currentData()

            # Get the course code for this section
            self.database.cursor.execute(
                "SELECT code FROM courses WHERE reference_number = ?",
                (pre_selected_section,)
            )
            result = self.database.cursor.fetchone()
            if result:
                pre_selected_course = result[0]

        dialog = EnrollStudentDialog(self, self.database)

        # Pre-select the course and section if available
        if pre_selected_course:
            for i in range(dialog.course_combo.count()):
                if dialog.course_combo.itemData(i) == pre_selected_course:
                    dialog.course_combo.setCurrentIndex(i)
                    break

            # Pre-select the section
            if pre_selected_section:
                for i in range(dialog.section_combo.count()):
                    if dialog.section_combo.itemData(i) == pre_selected_section:
                        dialog.section_combo.setCurrentIndex(i)
                        break

        if dialog.exec_() == QDialog.Accepted:
            # Get enrollment data
            enrollment_data = dialog.get_enrollment_data()
            course_id = enrollment_data["course_id"]
            students = enrollment_data["students"]

            success_count = 0
            error_count = 0

            # Enroll each student
            for student_id, student_name in students:
                try:
                    success = self.database.enroll_student(course_id, student_id)
                    if success:
                        success_count += 1
                    else:
                        error_count += 1
                except Exception as e:
                    print(f"Error enrolling student {student_id}: {e}")
                    error_count += 1

            # Show summary message
            if success_count > 0 and error_count == 0:
                QMessageBox.information(self, "Success", f"Successfully enrolled {success_count} students.")
            elif success_count > 0 and error_count > 0:
                QMessageBox.warning(self, "Partial Success", f"Enrolled {success_count} students, but {error_count} enrollments failed.")
            else:
                QMessageBox.critical(self, "Error", "Failed to enroll any students.")

            # Refresh the enrollment data immediately
            self.load_enrollment_data()

            # Refresh enrollment sections to update counts
            self.update_enrollment_sections()

    def unenroll_student(self):
        selected_row = self.enrollment_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a student to unenroll.")
            return

        student_id = self.enrollment_table.item(selected_row, 0).text()
        reference_number = self.enrollment_section_combo.currentData()  # This is the course_id (primary key)

        # Get student name for confirmation
        student_name = self.enrollment_table.item(selected_row, 2).text()

        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Confirm Unenrollment",
            f"Are you sure you want to unenroll {student_name} from the course?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.database.unenroll_student(reference_number, student_id)
                QMessageBox.information(self, "Success", f"{student_name} unenrolled successfully.")

                # Update the enrollment data immediately
                self.load_enrollment_data()

                # Refresh section combo box to update enrollment counts
                course_code = self.enrollment_course_combo.currentData()
                if course_code:
                    # Store current selection
                    current_section = self.enrollment_section_combo.currentData()

                    # Update sections list
                    self.update_enrollment_sections()

                    # Restore selection if possible
                    if current_section:
                        for i in range(self.enrollment_section_combo.count()):
                            if self.enrollment_section_combo.itemData(i) == current_section:
                                self.enrollment_section_combo.setCurrentIndex(i)
                                break
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to unenroll student: {str(e)}")

    def assign_teacher(self):
        if self.assignment_section_combo.count() == 0 or self.assignment_teacher_combo.count() == 0:
            QMessageBox.warning(self, "Error", "No course sections or teachers available.")
            return

        course_id = self.assignment_section_combo.currentData()
        teacher_id = self.assignment_teacher_combo.currentData()

        if not course_id or not teacher_id:
            QMessageBox.warning(self, "Error", "Please select both a course section and a teacher.")
            return

        # Check if this teacher is already assigned to this course
        self.database.cursor.execute(
            """
            SELECT COUNT(*) FROM course_teachers
            WHERE course_id = ? AND teacher_id = ?
            """,
            (course_id, teacher_id)
        )
        already_assigned = self.database.cursor.fetchone()[0] > 0

        if already_assigned:
            QMessageBox.warning(self, "Already Assigned", "This teacher is already assigned to this course section.")
            return

        try:
            success = self.database.assign_teacher(course_id, teacher_id)

            if success:
                QMessageBox.information(self, "Success", "Teacher assigned successfully.")
                self.load_assignment_data()
            else:
                QMessageBox.warning(self, "Error", "Failed to assign teacher. The teacher may already be assigned to this course.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to assign teacher: {str(e)}")

    def unassign_teacher(self):
        selected_row = self.assignment_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a teacher to unassign.")
            return

        teacher_id = self.assignment_table.item(selected_row, 0).text()
        course_id = self.assignment_section_combo.currentData()

        # Confirm with user
        reply = QMessageBox.question(
            self,
            "Confirm Unassignment",
            f"Are you sure you want to unassign this teacher from the course?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.database.unassign_teacher(course_id, teacher_id)
                QMessageBox.information(self, "Success", "Teacher unassigned successfully.")
                self.load_assignment_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to unassign teacher: {str(e)}")

    def register_student_face(self):
        selected_row = self.users_table.currentRow()
        if selected_row < 0:
            QMessageBox.warning(self, "Selection Error", "Please select a student to register face.")
            return

        # Check if selected user is a student
        role = self.users_table.item(selected_row, 4).text()
        if role != ROLE_STUDENT:
            QMessageBox.warning(self, "Selection Error", "Face registration is only available for students.")
            return

        # Get student ID
        student_id = self.users_table.item(selected_row, 0).text()

        # Open face registration dialog
        dialog = FaceRegistrationDialog(
            self,
            self.database,
            self.face_recognition_system,
            student_id
        )
        result = dialog.exec_()

        # If face was registered successfully, update the user info display
        if result == QDialog.Accepted:
            self.load_user_data()

    def show_student_image(self):
        # This is for the enrollment tab
        selected_row = self.enrollment_table.currentRow()
        if selected_row < 0:
            return

        user_id = self.enrollment_table.item(selected_row, 0).text()
        name = self.enrollment_table.item(selected_row, 2).text()

        # Show the student image dialog
        dialog = StudentImageDialog(self, user_id, name, self.face_recognition_system)
        dialog.exec_()

    def setup_stats_tab(self):
        layout = QVBoxLayout(self.stats_tab)

        # Search section
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search Student:"))

        self.student_search = QLineEdit()
        self.student_search.setPlaceholderText("Type student name or ID...")
        self.student_search.textChanged.connect(self.search_students)
        search_layout.addWidget(self.student_search)

        layout.addLayout(search_layout)

        # Student dropdown results
        self.student_results = QComboBox()
        self.student_results.setMaxVisibleItems(10)
        self.student_results.currentIndexChanged.connect(self.load_student_stats)
        layout.addWidget(self.student_results)

        # Section selection for statistics
        section_layout = QHBoxLayout()
        section_layout.addWidget(QLabel("Course Section:"))

        self.stats_course_combo = QComboBox()
        self.stats_course_combo.currentIndexChanged.connect(self.load_section_stats)
        section_layout.addWidget(self.stats_course_combo)

        layout.addLayout(section_layout)

        # Section statistics
        self.stats_group = QGroupBox("Section Statistics")
        stats_group_layout = QFormLayout(self.stats_group)

        self.total_students_label = QLabel()
        self.avg_attendance_label = QLabel()
        self.total_classes_label = QLabel()

        stats_group_layout.addRow("Total Students:", self.total_students_label)
        stats_group_layout.addRow("Average Attendance Rate:", self.avg_attendance_label)
        stats_group_layout.addRow("Total Classes Held:", self.total_classes_label)

        layout.addWidget(self.stats_group)

        # Student attendance records
        student_records_layout = QVBoxLayout()
        student_records_layout.addWidget(QLabel("Student Attendance Records:"))

        self.student_records_table = QTableWidget(0, 6)
        self.student_records_table.setHorizontalHeaderLabels(["Date", "Course", "Section", "Status", "First Check-in", "Second Check-in"])
        self.student_records_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.student_records_table.setEditTriggers(QTableWidget.NoEditTriggers)

        student_records_layout.addWidget(self.student_records_table)
        layout.addLayout(student_records_layout)

        # Load course data
        self.load_stats_courses()

    def load_stats_courses(self):
        """Load courses for the statistics tab dropdown with error handling"""
        try:
            # Clear existing items except "All Courses"
            while self.stats_course_combo.count() > 1:
                self.stats_course_combo.removeItem(1)

            # Get all courses, not just for a specific student
            courses = self.database.get_all_courses()
            if not courses:
                return

            # Add to dropdown
            for course in courses:
                if not course or len(course) < 4:
                    continue

                reference_number = course[0]  # Primary key
                code = course[1] if len(course) > 1 else "N/A"  # Code
                name = course[2] if len(course) > 2 else "N/A"  # Name
                section = course[3] if len(course) > 3 else "N/A"  # Section

                self.stats_course_combo.addItem(f"{code}-{name} {section}", reference_number)
        except Exception as e:
            print(f"Error loading statistics courses: {e}")
            import traceback
            traceback.print_exc()

    def search_students(self):
        search_text = self.student_search.text().strip().lower()
        if not search_text:
            self.student_results.clear()
            return

        # Search by name or ID
        self.database.cursor.execute(
            """
            SELECT id, name FROM users 
            WHERE (LOWER(name) LIKE ? OR id LIKE ?) AND role = 'student'
            LIMIT 20
            """,
            (f"%{search_text}%", f"%{search_text}%")
        )

        students = self.database.cursor.fetchall()

        # Update dropdown
        self.student_results.clear()
        for student in students:
            student_id, name = student
            self.student_results.addItem(f"{name} (ID: {student_id})", student_id)

    def load_student_stats(self):
        """Load attendance statistics for a student"""
        if self.student_results.count() == 0:
            return

        student_id = self.student_results.currentData()
        if not student_id:
            return

        # Get all attendance records for this student
        self.database.cursor.execute(
            """
            SELECT a.date, c.code, c.name, c.section, a.status, a.time, a.second_time, a.course_id
            FROM attendance a
            JOIN courses c ON a.course_id = c.reference_number
            WHERE a.student_id = ?
            ORDER BY a.date DESC
            """,
            (student_id,)
        )

        records = self.database.cursor.fetchall()

        # Display in table
        self.student_records_table.setRowCount(0)

        for i, record in enumerate(records):
            date, code, name, section, status, time, second_time, course_id = record

            self.student_records_table.insertRow(i)
            self.student_records_table.setItem(i, 0, QTableWidgetItem(date))
            self.student_records_table.setItem(i, 1, QTableWidgetItem(code))
            self.student_records_table.setItem(i, 2, QTableWidgetItem(section))
            self.student_records_table.setItem(i, 3, QTableWidgetItem(status))
            self.student_records_table.setItem(i, 4, QTableWidgetItem(time if time else ""))
            self.student_records_table.setItem(i, 5, QTableWidgetItem(second_time if second_time else ""))

    def load_section_stats(self):
        if self.stats_course_combo.count() == 0:
            return

        reference_number = self.stats_course_combo.currentData()  # This is the primary key
        if not reference_number:
            return

        # Get total students enrolled
        self.database.cursor.execute(
            """
            SELECT COUNT(*) FROM enrollments
            WHERE course_id = ?
            """,
            (reference_number,)
        )

        total_students = self.database.cursor.fetchone()[0]
        self.total_students_label.setText(str(total_students))

        # Get total classes (unique dates)
        self.database.cursor.execute(
            """
            SELECT COUNT(DISTINCT date) FROM attendance
            WHERE course_id = ?
            """,
            (reference_number,)
        )

        total_classes = self.database.cursor.fetchone()[0]
        self.total_classes_label.setText(str(total_classes))

        # Calculate average attendance rate
        if total_students > 0 and total_classes > 0:
            self.database.cursor.execute(
                """
                SELECT COUNT(*) FROM attendance
                WHERE course_id = ? AND status = 'Present'
                """,
                (reference_number,)
            )

            present_count = self.database.cursor.fetchone()[0]
            total_possible = total_students * total_classes

            if total_possible > 0:
                avg_rate = (present_count / total_possible) * 100
                self.avg_attendance_label.setText(f"{avg_rate:.1f}%")
            else:
                self.avg_attendance_label.setText("N/A")
        else:
            self.avg_attendance_label.setText("N/A")

    def setup_attendance_tab(self):
        """Set up the attendance monitoring tab with enhanced tracking features"""
        attendance_layout = QVBoxLayout(self.attendance_tab)

        # Top controls section
        controls_layout = QHBoxLayout()

        # Course selection
        course_section = QVBoxLayout()
        course_section.addWidget(QLabel("Select Course:"))

        self.attendance_course_combo = QComboBox()
        try:
            # Add error handling around problematic calls
            self.populate_course_combo(self.attendance_course_combo)
        except Exception as e:
            print(f"Error populating attendance course combo: {e}")
            import traceback
            traceback.print_exc()

        try:
            self.attendance_course_combo.currentIndexChanged.connect(self.update_attendance_data)
        except Exception as e:
            print(f"Error connecting signal: {e}")
            import traceback
            traceback.print_exc()

        course_section.addWidget(self.attendance_course_combo)

        controls_layout.addLayout(course_section)

        # Filter options
        filter_section = QVBoxLayout()
        filter_section.addWidget(QLabel("Filter Students:"))

        filter_layout = QHBoxLayout()

        self.filter_all_radio = QRadioButton("All")
        self.filter_at_risk_radio = QRadioButton("At Risk")
        self.filter_denied_radio = QRadioButton("Denied")

        self.filter_button_group = QButtonGroup(self)
        self.filter_button_group.addButton(self.filter_all_radio, 1)
        self.filter_button_group.addButton(self.filter_at_risk_radio, 2)
        self.filter_button_group.addButton(self.filter_denied_radio, 3)

        self.filter_all_radio.setChecked(True)

        filter_layout.addWidget(self.filter_all_radio)
        filter_layout.addWidget(self.filter_at_risk_radio)
        filter_layout.addWidget(self.filter_denied_radio)

        try:
            self.filter_button_group.buttonClicked.connect(self.filter_attendance_table)
        except Exception as e:
            print(f"Error connecting filter button: {e}")
            import traceback
            traceback.print_exc()

        filter_section.addLayout(filter_layout)
        controls_layout.addLayout(filter_section)

        # Search box
        search_section = QVBoxLayout()
        search_section.addWidget(QLabel("Search Student:"))

        search_layout = QHBoxLayout()

        self.attendance_search = QLineEdit()
        self.attendance_search.setPlaceholderText("Enter name or ID...")

        try:
            self.attendance_search.textChanged.connect(self.search_attendance_table)
        except Exception as e:
            print(f"Error connecting search: {e}")
            import traceback
            traceback.print_exc()

        search_layout.addWidget(self.attendance_search)

        search_button = QPushButton("Clear")
        try:
            search_button.clicked.connect(self.clear_attendance_search)
        except Exception as e:
            print(f"Error connecting clear button: {e}")
            import traceback
            traceback.print_exc()

        search_layout.addWidget(search_button)

        search_section.addLayout(search_layout)
        controls_layout.addLayout(search_section)

        attendance_layout.addLayout(controls_layout)

        # Create overview group
        overview_group = QGroupBox("Course Attendance Overview")
        overview_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        overview_layout = QVBoxLayout(overview_group)

        # Create a placeholder label outside of any try blocks
        placeholder_label = QLabel("Attendance Overview Widget Not Available")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #666; font-style: italic;")

        # Try to create the attendance overview widget, but use the placeholder if it fails
        try:
            # Import the widget class here rather than at the top of the file
            from attendance_widgets import AdminAttendanceOverviewWidget
            self.attendance_overview = AdminAttendanceOverviewWidget()
            overview_layout.addWidget(self.attendance_overview)
        except Exception as e:
            print(f"Error creating AdminAttendanceOverviewWidget: {e}")
            import traceback
            traceback.print_exc()
            # Use the placeholder if widget creation fails
            overview_layout.addWidget(placeholder_label)

        # Add explanation text regardless of widget creation success
        explanation = QLabel("Students with attendance below 80% are denied from the course as per university policy.")
        explanation.setAlignment(Qt.AlignCenter)
        explanation.setStyleSheet("font-style: italic; color: #666;")
        overview_layout.addWidget(explanation)

        attendance_layout.addWidget(overview_group)

        # Student table with enhanced information
        table_layout = QVBoxLayout()
        table_label = QLabel("Student Attendance Records")
        table_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        table_layout.addWidget(table_label)

        try:
            self.attendance_table = QTableWidget()
            self.attendance_table.setColumnCount(6)
            self.attendance_table.setHorizontalHeaderLabels([
                "ID", "Name", "Attendance", "Absence Dates", "Status", "Actions"
            ])

            # Set column widths
            self.attendance_table.setColumnWidth(2, 200)  # Attendance column
            self.attendance_table.setColumnWidth(3, 300)  # Absence dates column

            # Make table rows alternate colors for better readability
            self.attendance_table.setAlternatingRowColors(True)

            table_layout.addWidget(self.attendance_table)
        except Exception as e:
            print(f"Error setting up attendance table: {e}")
            import traceback
            traceback.print_exc()

            # Add fallback table
            error_label = QLabel("Error loading attendance table")
            error_label.setStyleSheet("color: red;")
            table_layout.addWidget(error_label)

        # Add button for generating reports
        try:
            report_button = QPushButton("Generate Attendance Report")
            report_button.setStyleSheet("background-color: #4285F4; color: white; font-weight: bold; padding: 8px;")
            report_button.clicked.connect(self.generate_attendance_report)
            table_layout.addWidget(report_button)
        except Exception as e:
            print(f"Error setting up report button: {e}")
            import traceback
            traceback.print_exc()

        attendance_layout.addLayout(table_layout)

    def update_attendance_data(self):
        """Update the attendance data for the selected course"""
        reference_number = self.attendance_course_combo.currentData()  # The primary key
        if not reference_number:
            return

        try:
            # Get course attendance summary
            attendance_summary = self.attendance_tracker.get_course_attendance_summary(reference_number)

            # Store student stats for use in filtering and report generation
            self.attendance_student_stats = attendance_summary.get('student_stats', [])

            # Update the attendance overview widget
            self.attendance_overview.update_data(attendance_summary)

            # Populate the student table
            self.populate_attendance_table(self.attendance_student_stats)

            # Apply current filter
            self.filter_attendance_table()
        except Exception as e:
            print(f"Error updating attendance data: {e}")
            import traceback
            traceback.print_exc()

    def filter_attendance_table(self):
        """Filter the attendance table based on selected filter option"""
        # Get the selected filter option
        if self.filter_all_radio.isChecked():
            # Show all students
            for row in range(self.attendance_table.rowCount()):
                self.attendance_table.setRowHidden(row, False)
        elif self.filter_at_risk_radio.isChecked():
            # Show only students with attendance below 90%
            for row in range(self.attendance_table.rowCount()):
                status_item = self.attendance_table.item(row, 4)
                if status_item and ("WARNING" in status_item.text() or "AT RISK" in status_item.text()):
                    self.attendance_table.setRowHidden(row, False)
                else:
                    self.attendance_table.setRowHidden(row, True)
        elif self.filter_denied_radio.isChecked():
            # Show only students with attendance below 80%
            for row in range(self.attendance_table.rowCount()):
                status_item = self.attendance_table.item(row, 4)
                if status_item and "DENIED" in status_item.text():
                    self.attendance_table.setRowHidden(row, False)
                else:
                    self.attendance_table.setRowHidden(row, True)

        # Apply any search filter that's currently active
        search_text = self.attendance_search.text().lower()
        if search_text:
            self.search_attendance_table()

    def show_student_image(self, student_id, student_name):
        """Show detailed student image and attendance information"""
        dialog = StudentImageDialog(self, student_id, student_name, self.face_recognition_system)
        dialog.exec_()

    def populate_attendance_table(self, student_stats):
        """Populate the attendance table with student attendance data - improved clarity"""
        self.attendance_table.setRowCount(len(student_stats))

        for row, stats in enumerate(student_stats):
            student_id = stats['student_id']
            student_name = stats['student_name']
            percentage = stats['percentage']
            absence_count = stats['absence_count']
            total_lectures = stats['total_lectures']

            # Set student ID and name
            self.attendance_table.setItem(row, 0, QTableWidgetItem(student_id))
            self.attendance_table.setItem(row, 1, QTableWidgetItem(student_name))

            # Create enhanced attendance widget
            attendance_widget = TeacherAttendanceWidget()
            attendance_widget.update_data(stats)

            # Add widget to table
            self.attendance_table.setCellWidget(row, 2, attendance_widget)

            # Add absence dates with clear formatting
            absence_dates = stats.get('absence_dates', [])
            if absence_dates:
                # Bold the first/most recent absence date
                if len(absence_dates) > 0:
                    formatted_dates = [f"<b>{absence_dates[0]}</b>"] + absence_dates[1:]
                    absence_text = ", ".join(formatted_dates)
                else:
                    absence_text = ", ".join(absence_dates)

                dates_item = QTableWidgetItem()
                dates_item.setData(Qt.DisplayRole, f"{len(absence_dates)} absences: {absence_text}")
                # Allow HTML formatting
                dates_item.setData(Qt.TextColorRole, QColor("#333333"))

                # Highlight if many absences
                if len(absence_dates) > math.ceil(total_lectures * 0.15):
                    dates_item.setBackground(QBrush(QColor(255, 235, 235)))  # Light red background
            else:
                dates_item = QTableWidgetItem("No absences")
                dates_item.setForeground(QBrush(QColor("green")))

            self.attendance_table.setItem(row, 3, dates_item)

            # Add status text with appropriate styling
            if percentage >= 90:
                status_text = "GOOD STANDING"
                status_color = QColor(0, 128, 0)  # Green
            elif percentage >= 85:
                status_text = "WARNING (< 90%)"
                status_color = QColor(255, 193, 7)  # Yellow
            elif percentage >= 80:
                status_text = "AT RISK (< 85%)"
                status_color = QColor(255, 128, 0)  # Orange
            else:
                status_text = "DENIED (< 80%)"
                status_color = QColor(255, 0, 0)  # Red

            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QBrush(status_color))
            status_item.setFont(QFont("Arial", 10, QFont.Bold))
            self.attendance_table.setItem(row, 4, status_item)

            # Add action buttons in a widget
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)

            # Add a more detailed view button that shows actual number data
            details_button = QPushButton(f"Details ({absence_count}/{total_lectures})")
            details_button.setToolTip(f"Absence rate: {(absence_count/total_lectures*100):.1f}%")

            notify_button = QPushButton("Notify")

            # Style buttons
            if percentage < 80:
                notify_button.setStyleSheet("background-color: #F44336; color: white;")
                details_button.setStyleSheet("font-weight: bold;")
            elif percentage < 85:
                notify_button.setStyleSheet("background-color: #FF9800; color: white;")

            # Connect buttons to functions
            details_button.clicked.connect(lambda checked, s_id=student_id, name=student_name:
                                        self.show_student_image(s_id, name))

            notify_button.clicked.connect(lambda checked, s_id=student_id, name=student_name:
                                        self.notify_student_attendance(s_id, name, percentage))

            actions_layout.addWidget(details_button)
            actions_layout.addWidget(notify_button)

            self.attendance_table.setCellWidget(row, 5, actions_widget)

    def search_attendance_table(self):
        """Search the attendance table for matching student names or IDs"""
        search_text = self.attendance_search.text().lower()

        for row in range(self.attendance_table.rowCount()):
            student_id = self.attendance_table.item(row, 0).text().lower()
            student_name = self.attendance_table.item(row, 1).text().lower()

            if search_text in student_id or search_text in student_name:
                self.attendance_table.setRowHidden(row, False)
            else:
                self.attendance_table.setRowHidden(row, True)

    def clear_attendance_search(self):
        """Clear the attendance search and show all rows"""
        self.attendance_search.clear()
        for row in range(self.attendance_table.rowCount()):
            self.attendance_table.setRowHidden(row, False)

    def generate_attendance_report(self):
        """Generate a comprehensive attendance report for the selected course"""
        course_id = self.attendance_course_combo.currentData()
        if not course_id:
            QMessageBox.warning(self, "No Course Selected", "Please select a course to generate a report.")
            return

        # Get course details
        course = self.database.get_course_by_id(course_id)
        course_code = course[1]
        course_name = course[2]
        course_section = course[3]

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
            # Generate CSV content
            with open(file_path, 'w') as f:
                # Write header
                f.write(f"Attendance Report for {course_code}: {course_name} (Section {course_section})\n")
                f.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                # Column headers
                f.write("Student ID,Name,Attendance %,Absences,Status,Absence Dates\n")

                # Student data
                for stats in self.attendance_student_stats:
                    student_id = stats['student_id']
                    student_name = stats['student_name']
                    percentage = stats['percentage']
                    absence_count = stats['absence_count']

                    # Determine status
                    if percentage >= 90:
                        status = "GOOD STANDING"
                    elif percentage >= 85:
                        status = "WARNING"
                    elif percentage >= 80:
                        status = "AT RISK"
                    else:
                        status = "DENIED"

                    # Format absence dates
                    absence_dates = "|".join(stats['absence_dates'])

                    # Write row
                    f.write(f"{student_id},{student_name},{percentage:.1f}%,{absence_count},{status},{absence_dates}\n")

            QMessageBox.information(self, "Report Generated", f"Attendance report saved to:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate report: {str(e)}")

    def notify_student_attendance(self, student_id, student_name, attendance_percentage):
        """Send attendance warning notification to a student"""
        # Determine warning level and message
        if attendance_percentage < 80:
            warning_level = "FINAL WARNING"
            message = f"You have exceeded the 20% absence threshold and are DENIED from this course. Please contact your academic advisor immediately."
        elif attendance_percentage < 85:
            warning_level = "SECOND WARNING"
            message = f"Your attendance has dropped to {attendance_percentage:.1f}%, which is approaching the 20% absence threshold. Further absences may result in being denied from the course."
        elif attendance_percentage < 90:
            warning_level = "FIRST WARNING"
            message = f"Your attendance is currently at {attendance_percentage:.1f}%. Please be aware that exceeding the 20% absence threshold will result in being denied from the course."
        else:
            warning_level = "NOTICE"
            message = f"Your attendance is currently at {attendance_percentage:.1f}%. Please maintain your good attendance record."

        # Create notification dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Send Attendance Notification to {student_name}")
        dialog.setMinimumWidth(500)

        layout = QVBoxLayout(dialog)

        # Notification details
        details_group = QGroupBox("Notification Details")
        details_layout = QFormLayout(details_group)

        student_label = QLabel(f"{student_name} (ID: {student_id})")
        student_label.setStyleSheet("font-weight: bold;")
        details_layout.addRow("Student:", student_label)

        attendance_label = QLabel(f"{attendance_percentage:.1f}%")
        if attendance_percentage < 80:
            attendance_label.setStyleSheet("color: red; font-weight: bold;")
        elif attendance_percentage < 85:
            attendance_label.setStyleSheet("color: orange; font-weight: bold;")
        elif attendance_percentage < 90:
            attendance_label.setStyleSheet("color: #FFC107; font-weight: bold;")
        else:
            attendance_label.setStyleSheet("color: green; font-weight: bold;")
        details_layout.addRow("Current Attendance:", attendance_label)

        warning_label = QLabel(warning_level)
        warning_label.setStyleSheet("font-weight: bold;")
        details_layout.addRow("Warning Level:", warning_label)

        layout.addWidget(details_group)

        # Message content
        message_group = QGroupBox("Message")
        message_layout = QVBoxLayout(message_group)

        message_edit = QLineEdit(message)
        message_edit.setReadOnly(False)
        message_layout.addWidget(message_edit)

        layout.addWidget(message_group)

        # Buttons
        buttons_layout = QHBoxLayout()

        send_button = QPushButton("Send Notification")
        send_button.setStyleSheet("background-color: #4285F4; color: white; font-weight: bold;")
        send_button.clicked.connect(dialog.accept)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)

        buttons_layout.addWidget(send_button)
        buttons_layout.addWidget(cancel_button)

        layout.addLayout(buttons_layout)

        # Show dialog
        if dialog.exec_() == QDialog.Accepted:
            QMessageBox.information(self, "Notification Sent", f"Attendance notification sent to {student_name}.")

    def populate_course_combo(self, combo_box):
        """Populate course combo box"""
        combo_box.clear()

        self.database.cursor.execute(
            """
            SELECT reference_number, code, name, section FROM courses
            ORDER BY code, section
            """
        )
        courses = self.database.cursor.fetchall()

        for course in courses:
            reference_number, code, name, section = course
            display_text = f"{code}: {name} (Section {section})"
            combo_box.addItem(display_text, reference_number)

    def logout(self):
        # Hide this window instead of closing it
        self.hide()
        # Show login window again
        self.app.show_login_window()
