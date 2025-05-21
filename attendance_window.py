from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QDialog, QTimeEdit
)
from PyQt5.QtCore import Qt, QTimer, QTime
from PyQt5.QtGui import QFont, QImage, QPixmap
import cv2
import datetime

class AttendanceWindow(QMainWindow):
    def __init__(self, database, face_recognition_system, user_id, course_id):
        super().__init__()

        self.database = database
        self.face_recognition_system = face_recognition_system
        self.user_id = user_id
        self.course_id = course_id

        # Track liveness verification status
        self.liveness_verified = False

        # Get course details
        self.course = self.database.get_course_by_id(course_id)
        self.course_name = self.course[2]
        self.course_code = self.course[1]
        self.course_section = self.course[3]
        self.classroom = self.course[7]
        self.reference_number = course_id

        # Check for custom end time
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        self.custom_end_time = self.database.get_custom_end_time(course_id, today)

        self.setWindowTitle(f"Attendance - {self.course_code}-{self.course_section} {self.course_name}")
        self.setMinimumSize(800, 600)

        # Initialize camera variables
        self.camera = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)

        self.recognized_students = []

        self.init_ui()
        self.start_camera()

    def init_ui(self):
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

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
        course_label = QLabel(f"{self.course_code}-{self.course_section} {self.course_name} | Room: {self.classroom}")
        course_label.setFont(QFont("Arial", 10, QFont.Bold))
        course_label.setAlignment(Qt.AlignCenter)

        course_info_layout.addWidget(self.datetime_label)
        course_info_layout.addStretch()
        course_info_layout.addWidget(course_label)
        course_info_layout.addStretch()

        # Add start and end time label - updated to show both start and end times
        start_time = self.course[4]  # Start time from course data
        end_time = self.course[5]    # Scheduled end time

        if self.custom_end_time:
            time_obj = datetime.datetime.strptime(self.custom_end_time, "%H:%M:%S").time()
            custom_end_display = time_obj.strftime("%H:%M")
            self.time_label = QLabel(f"Start: {start_time} | Scheduled End: {end_time} | Today's End: {custom_end_display}")
            self.time_label.setStyleSheet("color: blue;")
        else:
            self.time_label = QLabel(f"Start: {start_time} | End: {end_time}")

        self.time_label.setFont(QFont("Arial", 10))
        course_info_layout.addWidget(self.time_label)

        main_layout.addLayout(course_info_layout)

        # Camera feed
        self.camera_label = QLabel()
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setStyleSheet("background-color: black;")
        main_layout.addWidget(self.camera_label)

        # Recognition results table
        self.results_table = QTableWidget(0, 3)
        self.results_table.setHorizontalHeaderLabels(["Student ID", "Name", "Status"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.results_table.setEditTriggers(QTableWidget.NoEditTriggers)
        main_layout.addWidget(self.results_table)

        # Buttons layout
        buttons_layout = QHBoxLayout()

        # Mark Attendance button
        self.mark_attendance_button = QPushButton("Mark Attendance")
        self.mark_attendance_button.clicked.connect(self.mark_attendance)
        buttons_layout.addWidget(self.mark_attendance_button)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close_window)
        buttons_layout.addWidget(close_button)

        main_layout.addLayout(buttons_layout)

    def update_datetime(self):
        now = datetime.datetime.now()
        self.datetime_label.setText(f"Date: {now.strftime('%Y-%m-%d')} | Time: {now.strftime('%H:%M:%S')}")

    def start_camera(self):
        try:
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                raise Exception("Could not open camera")

            self.timer.start(30)  # Update every 30ms (approx 33 fps)
        except Exception as e:
            QMessageBox.warning(self, "Camera Error", f"Could not start camera: {str(e)}")

    def stop_camera(self):
        if self.camera is not None:
            self.timer.stop()
            self.camera.release()
            self.camera = None

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

        # Add custom end time notification if applicable
        if self.custom_end_time:
            time_obj = datetime.datetime.strptime(self.custom_end_time, "%H:%M:%S").time()
            custom_end_display = time_obj.strftime("%H:%M")
            end_time_text = f"Today's End Time: {custom_end_display}"
            cv2.rectangle(frame, (0, frame.shape[0]-30), (frame.shape[1], frame.shape[0]), (70, 130, 180), -1)
            cv2.putText(frame, end_time_text, (10, frame.shape[0]-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Convert frame to QImage and display
        rgb_image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.camera_label.setPixmap(
            QPixmap.fromImage(qt_image).scaled(
                self.camera_label.width(),
                self.camera_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )


    def update_results_table(self):
        self.results_table.setRowCount(0)
        for student in self.recognized_students:
            row = self.results_table.rowCount()
            self.results_table.insertRow(row)
            self.results_table.setItem(row, 0, QTableWidgetItem(student['student_id']))
            self.results_table.setItem(row, 1, QTableWidgetItem(student['name']))
            self.results_table.setItem(row, 2, QTableWidgetItem("Detected"))

    def mark_attendance(self):
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

        # Get course end time (use custom end time if available)
        course_end_time = self.custom_end_time if self.custom_end_time else self.course[5]

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

    def close_window(self):
        self.stop_camera()
        self.close()

    def closeEvent(self, event):
        self.stop_camera()
        event.accept()
