import sys
import os

from PyQt5.QtWidgets import QApplication, QSplashScreen
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from database import Database
from vit_face_recognition import ViTFaceRecognitionSystem
from config import APP_TITLE

from login_window import LoginWindow
from admin_window import AdminWindow
from teacher_window import TeacherWindow
from student_window import StudentWindow
from attendance_window import AttendanceWindow

class FaceAttendanceApp:
    def __init__(self):
        # Create application
        self.app = QApplication(sys.argv)
        self.app.setApplicationName(APP_TITLE)

        # Create and show splash screen
        splash_pixmap = QPixmap(300, 200)
        splash_pixmap.fill(Qt.white)
        self.splash = QSplashScreen(splash_pixmap)
        self.splash.showMessage("Initializing database...", Qt.AlignCenter, Qt.black)
        self.splash.show()
        self.app.processEvents()

        # Initialize database
        self.database = Database()

        # Initialize face recognition system
        self.splash.showMessage("Initializing face recognition system...", Qt.AlignCenter, Qt.black)
        self.app.processEvents()
        self.face_recognition = ViTFaceRecognitionSystem(self.database)

        # Close splash screen
        self.splash.close()

        # Show login window
        self.show_login_window()

    def show_login_window(self):
        self.login_window = LoginWindow(
            self.database,
            self.face_recognition,
            self.open_admin_window,
            self.open_teacher_window,
            self.open_student_window,
            self.open_attendance_window
        )
        self.login_window.show()

    def open_admin_window(self, user_id):
        self.admin_window = AdminWindow(self, self.database, self.face_recognition, user_id)
        self.admin_window.show()

    def open_teacher_window(self, user_id):
        self.teacher_window = TeacherWindow(self.database, self.face_recognition, user_id)
        self.teacher_window.show()

    def open_student_window(self, user_id):
        self.student_window = StudentWindow(self.database, self.face_recognition, user_id)
        self.student_window.show()

    def open_attendance_window(self, user_id, course_id):
        self.attendance_window = AttendanceWindow(self.database, self.face_recognition, user_id, course_id)
        self.attendance_window.show()

    def run(self):
        return self.app.exec_()

if __name__ == "__main__":
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)

    # Start application
    app = FaceAttendanceApp()
    sys.exit(app.run())
