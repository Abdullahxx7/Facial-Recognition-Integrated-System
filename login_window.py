from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QComboBox,
    QDialog, QFormLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from config import APP_TITLE, ROLE_ADMIN, ROLE_TEACHER, ROLE_STUDENT

class TakeAttendanceDialog(QDialog):
    def __init__(self, parent, database, face_recognition_system, open_attendance_window, user_id):
        super().__init__(parent)

        self.database = database
        self.face_recognition_system = face_recognition_system
        self.open_attendance_window = open_attendance_window
        self.user_id = user_id

        self.setWindowTitle("Take Attendance")
        self.setMinimumSize(400, 200)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Instruction
        instruction = QLabel("Select a course to take attendance:")
        instruction.setAlignment(Qt.AlignCenter)
        layout.addWidget(instruction)

        # Course selection
        form_layout = QFormLayout()

        self.course_combo = QComboBox()
        self.load_current_courses()

        form_layout.addRow("Current Course:", self.course_combo)
        layout.addLayout(form_layout)

        # Buttons
        buttons_layout = QHBoxLayout()

        proceed_button = QPushButton("Proceed")
        proceed_button.clicked.connect(self.proceed)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        buttons_layout.addWidget(proceed_button)
        buttons_layout.addWidget(cancel_button)

        layout.addLayout(buttons_layout)

    def load_current_courses(self):
        try:
            # Get courses that are currently in session
            current_courses = self.database.get_current_courses()

            if not current_courses:
                self.course_combo.addItem("No courses available at this time", None)
                return

            for course in current_courses:
                if len(course) >= 6:  # Make sure we have enough data
                    reference_number = course[0]  # The primary key
                    code = course[1]
                    name = course[2]
                    section = course[3]
                    # Fixed index: classroom is at index 6 in the SQL result
                    room = course[6] if len(course) > 6 else "N/A"

                    self.course_combo.addItem(
                        f"{code}: {name} ({section}) - Room: {room}",
                        reference_number
                    )
                else:
                    # Handle incomplete course data
                    if len(course) > 0:
                        reference_number = course[0]
                        self.course_combo.addItem(f"Course (ID: {reference_number})", reference_number)
        except Exception as e:
            print(f"Error loading current courses: {e}")
            self.course_combo.addItem("Error loading courses", None)

    def proceed(self):
        if self.course_combo.count() == 0:
            QMessageBox.warning(self, "No Courses", "No courses are available at this time.")
            return

        course_id = self.course_combo.currentData()
        if course_id is None:
            QMessageBox.warning(self, "Invalid Selection", "Please select a valid course.")
            return

        # Open attendance window
        self.accept()
        self.open_attendance_window(self.user_id, course_id)

class LoginWindow(QMainWindow):
    def __init__(self, database, face_recognition_system, open_admin_window, open_teacher_window, open_student_window, open_attendance_window):
        super().__init__()

        self.database = database
        self.face_recognition_system = face_recognition_system
        self.open_admin_window = open_admin_window
        self.open_teacher_window = open_teacher_window
        self.open_student_window = open_student_window
        self.open_attendance_window = open_attendance_window

        self.setWindowTitle(APP_TITLE)
        self.setMinimumSize(400, 350)

        self.init_ui()

    def init_ui(self):
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setAlignment(Qt.AlignCenter)

        # Title
        title_label = QLabel(APP_TITLE)
        title_label.setFont(QFont("Arial", 18, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)

        # Login form
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)

        # Username
        username_label = QLabel("Username or ID:")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username or ID")

        # Password
        password_label = QLabel("Password:")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter your password")
        self.password_input.setEchoMode(QLineEdit.Password)

        # Login button
        login_button = QPushButton("Login")
        login_button.clicked.connect(self.handle_login)

        # Make Enter key trigger login
        self.password_input.returnPressed.connect(login_button.click)

        # Take Attendance button
        take_attendance_button = QPushButton("Take Attendance")
        take_attendance_button.clicked.connect(self.show_take_attendance_dialog)

        # Add widgets to form layout
        form_layout.addWidget(username_label)
        form_layout.addWidget(self.username_input)
        form_layout.addWidget(password_label)
        form_layout.addWidget(self.password_input)
        form_layout.addWidget(login_button)

        # Add form layout to main layout
        main_layout.addLayout(form_layout)

        # Add Take Attendance button
        main_layout.addWidget(take_attendance_button)

        # Add some spacing
        main_layout.addSpacing(20)

        # Default credentials notice
        default_credentials = QLabel("Default Admin: username 'admin', password 'admin123'")
        default_credentials.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(default_credentials)

        # Error message label (hidden by default)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red; font-weight: bold;")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.setVisible(False)
        main_layout.addWidget(self.error_label)

    def handle_login(self):
        # Clear any previous error messages
        self.error_label.setVisible(False)

        username = self.username_input.text()
        password = self.password_input.text()

        if not username or not password:
            self.show_error("Please enter both username/ID and password.")
            return

        try:
            # First try to authenticate with username
            user_info = self.database.authenticate_user(username, password)

            # If that fails, try authenticating with the ID (for students who use ID as login)
            if not user_info:
                user_info = self.database.authenticate_by_id(username, password)

            if user_info:
                print(f"Successfully authenticated user: {user_info['user_id']} with role: {user_info['role']}")
                self.close()

                # Open appropriate window based on user role
                if user_info["role"] == ROLE_ADMIN:
                    self.open_admin_window(user_info["user_id"])
                elif user_info["role"] == ROLE_TEACHER:
                    self.open_teacher_window(user_info["user_id"])
                elif user_info["role"] == ROLE_STUDENT:
                    self.open_student_window(user_info["user_id"])
                else:
                    self.show_error(f"Unknown role: {user_info['role']}")
            else:
                self.show_error("Invalid username/ID or password.")
        except Exception as e:
            print(f"Login error: {e}")
            import traceback
            traceback.print_exc()
            self.show_error(f"Login failed: {str(e)}")

    def show_error(self, message):
        """Display an error message in the UI"""
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        # Also show a message box for immediate attention
        QMessageBox.warning(self, "Login Error", message)

    def show_take_attendance_dialog(self):
        try:
            # For now, default to 'admin' as the user_id for demonstration. In a real app, use the logged-in user.
            user_id = 'admin'
            dialog = TakeAttendanceDialog(
                self,
                self.database,
                self.face_recognition_system,
                self.open_attendance_window,
                user_id
            )
            dialog.exec_()
        except Exception as e:
            print(f"Error showing attendance dialog: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to open attendance dialog: {str(e)}")
