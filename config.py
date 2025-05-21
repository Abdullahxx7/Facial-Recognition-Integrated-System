# Configuration settings for the Face Recognition Attendance System

# Application settings
APP_TITLE = "FARIS - فارس"

# Database settings
DATABASE_PATH = "data/attendance.db"

# Face recognition settings
FACE_RECOGNITION_TOLERANCE = 0.98
VIT_MODEL_PATH = "models/vit_face_recognition.pth"  # Path to the trained ViT model
VIT_IMAGE_SIZE = 224  # Input image size for ViT model
VIT_PATCH_SIZE = 16  # Patch size for ViT model
VIT_EMBED_DIM = 768  # Embedding dimension for ViT model
VIT_DEPTH = 12  # Number of transformer layers
VIT_NUM_HEADS = 12  # Number of attention heads
VIT_MLP_RATIO = 4.0  # MLP ratio for transformer layers
VIT_DROP_RATE = 0.1  # Dropout rate

# User roles
ROLE_ADMIN = "admin"
ROLE_TEACHER = "teacher"
ROLE_STUDENT = "student"

# Attendance status types
STATUS_PRESENT = "Present"
STATUS_ABSENT = "Absent"
STATUS_LATE = "Late"
STATUS_NA = "N/A"
STATUS_PARTIAL_ATTENDANCE = "Partial Attendance"
STATUS_UNAUTHORIZED_DEPARTURE = "Unauthorized Departure"

# Time settings
EARLY_ARRIVAL_MARGIN = 5  # Minutes before start time to be considered early
LATE_THRESHOLD = 15  # Minutes after start time to be considered late
EARLY_DEPARTURE_THRESHOLD = 15  # Minutes before end time to be considered early departure
SECOND_CHECKIN_WINDOW = 5  # Minutes before and after end time for second check-in
