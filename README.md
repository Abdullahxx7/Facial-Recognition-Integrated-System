# FARIS - فارس
# Facial Recognition Integrated System

A comprehensive attendance management system using Vision Transformer (ViT) based face recognition technology, built with PyQt5 and SQLite.

## Table of Contents
- [Features](#features)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Project Structure](#project-structure)
- [Usage](#usage)
- [Default Credentials](#default-credentials)
- [Configuration](#configuration)
- [Database Schema](#database-schema)
- [Troubleshooting](#troubleshooting)
- [Development](#development)

## Features

### Core Features
- **Advanced Face Recognition**: Uses Vision Transformer (ViT) model for accurate face recognition
- **Liveness Detection**: Prevents spoofing attempts with blink detection and texture analysis
- **Multi-role Support**: Three distinct user roles (Admin, Teacher, Student)
- **Real-time Attendance**: Camera-based attendance marking with instant recognition
- **Comprehensive Reporting**: Detailed attendance reports and statistics

### Role-Specific Features

#### Administrator
- User management (CRUD operations)
- Course management with scheduling
- Student enrollment management
- Teacher assignment to courses
- System-wide attendance monitoring
- Attendance report generation

#### Teacher
- View assigned courses
- Manual attendance marking
- Camera-based attendance
- Student attendance tracking
- Course statistics and analytics
- Early lecture dismissal
- Lecture cancellation

#### Student
- View enrolled courses
- Check attendance records
- View attendance statistics
- Visual attendance warnings
- Profile management

### Attendance Rules
- **On-time**: Check-in within 15 minutes of class start
- **Late**: Check-in after 15 minutes threshold
- **Absent**: No check-in recorded
- **Unauthorized Departure**: Only first check-in, missing second check-in
- **Denied**: Attendance below 80% (exceeding 20% absence threshold)

## System Requirements

### Hardware
- Webcam for face recognition features
- Minimum 4GB RAM
- 1GB free disk space

### Software
- Python 3.7 or higher
- Windows/Linux/macOS

### Python Dependencies
```
PyQt5>=5.15.0
opencv-python>=4.5.0
numpy>=1.19.0
torch>=1.9.0
torchvision>=0.10.0
transformers>=4.0.0
matplotlib>=3.3.0
mediapipe>=0.8.0 (optional, for enhanced liveness detection)
filetype>=1.0.0
```

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/faris-attendance-system.git
   cd faris-attendance-system
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On Linux/macOS
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create required directories**
   ```bash
   mkdir data
   mkdir models
   ```

5. **Run the application**
   ```bash
   python main.py
   ```

## Project Structure

```
faris-attendance-system/
│
├── main.py                    # Application entry point
├── config.py                  # Configuration settings
├── database.py                # Database operations
├── vit_face_recognition.py    # Face recognition system
│
├── login_window.py            # Login interface
├── admin_window.py            # Administrator interface
├── teacher_window.py          # Teacher interface
├── student_window.py          # Student interface
├── attendance_window.py       # Attendance marking interface
│
├── attendance_widgets.py      # Reusable UI components
├── attendance_tracker.py      # Attendance calculation logic
├── migrate_encodings.py       # Database migration utility
│
├── data/                      # Database storage
│   └── attendance.db          # SQLite database
│
├── models/                    # Model files
│   └── vit_face_recognition.pth  # Trained ViT model
│
└── README.md                  # This file
```

## Usage

### First-Time Setup

1. **Login as Administrator**
   - Username: `admin`
   - Password: `admin123`

2. **Add Users**
   - Navigate to Users tab
   - Click "Add User"
   - For students: capture or upload face photo

3. **Create Courses**
   - Navigate to Courses tab
   - Fill in course details
   - Set schedule (days, time, classroom)

4. **Enroll Students**
   - Navigate to Student Enrollment tab
   - Select course and section
   - Choose students to enroll

5. **Assign Teachers**
   - Navigate to Teacher Assignment tab
   - Select course and teacher

### Daily Operations

#### Taking Attendance (Camera-based)
1. Click "Take Attendance" on login screen
2. Select current course
3. Students position face in camera view
4. System automatically recognizes and marks attendance

#### Manual Attendance (Teachers)
1. Login as teacher
2. Go to Manual Attendance tab
3. Select course and date
4. Mark student attendance status

#### Checking Attendance (Students)
1. Login with student ID
2. View attendance in "My Statistics" tab
3. Monitor attendance warnings

## Default Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |

**Note**: Change default passwords immediately after first login.

## Configuration

Edit `config.py` to modify system settings:

```python
# Face recognition settings
FACE_RECOGNITION_TOLERANCE = 0.98  # Recognition threshold
VIT_IMAGE_SIZE = 224              # Input image size

# Time settings
EARLY_ARRIVAL_MARGIN = 5          # Minutes before class
LATE_THRESHOLD = 15               # Minutes to be marked late
EARLY_DEPARTURE_THRESHOLD = 15    # Minutes before end
SECOND_CHECKIN_WINDOW = 5         # Window for second check-in
```

## Database Schema

### Main Tables

#### users
- `id` (TEXT PRIMARY KEY): User ID
- `username` (TEXT): Login username
- `password` (TEXT): User password
- `name` (TEXT): Full name
- `role` (TEXT): admin/teacher/student
- `email` (TEXT): Email address
- `face_encoding` (BLOB): Face recognition data
- `face_image` (BLOB): Face photo

#### courses
- `reference_number` (INTEGER PRIMARY KEY): Course ID
- `code` (TEXT): Course code
- `name` (TEXT): Course name
- `section` (TEXT): Section number
- `start_time` (TEXT): Class start time
- `end_time` (TEXT): Class end time
- `capacity` (INTEGER): Maximum students
- `classroom` (TEXT): Room location
- `start_date` (TEXT): Course start date
- `end_date` (TEXT): Course end date
- `days` (TEXT): Class days (Mon,Tue,Wed,Thu,Fri)

#### attendance
- `id` (INTEGER PRIMARY KEY): Record ID
- `student_id` (TEXT): Student ID
- `course_id` (INTEGER): Course reference number
- `date` (TEXT): Attendance date
- `time` (TEXT): First check-in time
- `second_time` (TEXT): Second check-in time
- `status` (TEXT): Present/Late/Absent/Unauthorized Departure
- `is_cancelled` (INTEGER): Lecture cancellation flag

## Troubleshooting

### Common Issues

1. **Camera not detected**
   - Check webcam connection
   - Ensure camera permissions are granted
   - Try restarting the application

2. **Face not recognized**
   - Ensure good lighting
   - Face camera directly
   - Re-register face if needed

3. **Database errors**
   - Check data directory exists
   - Verify write permissions
   - Run database migration if upgrading

4. **Import errors**
   - Install all dependencies: `pip install -r requirements.txt`
   - Check Python version compatibility

### Performance Optimization

- Use GPU for face recognition if available
- Reduce camera resolution for faster processing
- Limit concurrent face detections

## Development

### Adding New Features

1. **Database Changes**
   - Update schema in `database.py`
   - Add migration logic in `create_tables()`

2. **UI Components**
   - Create reusable widgets in `attendance_widgets.py`
   - Follow PyQt5 best practices

3. **Face Recognition**
   - Model updates in `vit_face_recognition.py`
   - Retrain with new data if needed

### Testing

```bash
# Run unit tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_database.py
```

## Security Considerations

- Store passwords securely (implement hashing)
- Validate all user inputs
- Implement session timeouts
- Regular database backups
- Audit logging for sensitive operations

## Development Team:

- Abdullah Alhumaidi
- Salem Alqarini
- Nawaf Alnofaie
- Ahmed Alotaibi

## License

This project is licensed under IMSIU License.

## Acknowledgments

- Vision Transformer (ViT) implementation from Hugging Face
- PyQt5 for the GUI framework
- OpenCV for image processing
- MediaPipe for enhanced face detection

---

**Note**: This is an educational/demonstration project. For production use, implement proper security measures including password hashing, HTTPS communication, and data encryption.
