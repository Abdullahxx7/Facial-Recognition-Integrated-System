import torch
import torch.nn as nn
import torchvision.transforms as transforms
from transformers import ViTModel, ViTConfig
from PIL import Image
import numpy as np
import cv2
import pickle
import datetime
import os
import time
from config import (
    FACE_RECOGNITION_TOLERANCE,
    STATUS_PRESENT, STATUS_LATE, STATUS_UNAUTHORIZED_DEPARTURE,
    LATE_THRESHOLD, EARLY_ARRIVAL_MARGIN, EARLY_DEPARTURE_THRESHOLD, SECOND_CHECKIN_WINDOW
)

class LivenessDetector:
    def __init__(self):
        # Load eye cascade classifier
        self.eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
        
        # Initialize variables for liveness detection
        self.blink_count = 0
        self.head_movement_count = 0
        self.last_face_position = None
        self.eye_aspect_ratio_threshold = 0.25  # Increased from 0.2 to be more lenient
        self.movement_threshold = 20  # Decreased from 30 to detect smaller movements
        self.required_blinks = 1  # Decreased from 2 to require only one blink
        self.required_movements = 1
        self.texture_threshold = 0.15  # Adjusted texture analysis threshold
        self.face_mesh = None
        try:
            import mediapipe as mp
            self.face_mesh = mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        except ImportError:
            print("MediaPipe not available. Using basic eye detection.")
        self.blink_history = []
        self.movement_history = []
        self.history_size = 5  # Track last 5 frames for more stable detection

    def calculate_eye_aspect_ratio(self, landmarks):
        # Get the landmarks for both eyes
        left_eye = [landmarks[33], landmarks[160], landmarks[158], landmarks[133], landmarks[153], landmarks[144]]
        right_eye = [landmarks[362], landmarks[385], landmarks[387], landmarks[263], landmarks[373], landmarks[380]]
        
        # Calculate EAR for both eyes
        left_ear = self._calculate_ear(left_eye)
        right_ear = self._calculate_ear(right_eye)
        
        # Return the average EAR
        return (left_ear + right_ear) / 2.0

    def _calculate_ear(self, eye_landmarks):
        # Calculate the vertical distances
        v1 = np.linalg.norm(eye_landmarks[1] - eye_landmarks[5])
        v2 = np.linalg.norm(eye_landmarks[2] - eye_landmarks[4])
        
        # Calculate the horizontal distance
        h = np.linalg.norm(eye_landmarks[0] - eye_landmarks[3])
        
        # Calculate the EAR
        ear = (v1 + v2) / (2.0 * h)
        return ear

    def detect_blink(self, landmarks):
        ear = self.calculate_eye_aspect_ratio(landmarks)
        self.blink_history.append(ear)
        if len(self.blink_history) > self.history_size:
            self.blink_history.pop(0)
        
        # Check if we have enough history
        if len(self.blink_history) < self.history_size:
            return False
        
        # Calculate average EAR
        avg_ear = sum(self.blink_history) / len(self.blink_history)
        
        # Detect blink if current EAR is significantly lower than average
        if ear < avg_ear * 0.7:  # More lenient blink detection
            self.blink_count += 1
            return True
        return False

    def detect_head_movement(self, face_position):
        if self.last_face_position is None:
            self.last_face_position = face_position
            return False
        
        # Calculate movement
        movement = np.linalg.norm(np.array(face_position) - np.array(self.last_face_position))
        self.movement_history.append(movement)
        if len(self.movement_history) > self.history_size:
            self.movement_history.pop(0)
        
        # Update last position
        self.last_face_position = face_position
        
        # Check if we have enough history
        if len(self.movement_history) < self.history_size:
            return False
        
        # Calculate average movement
        avg_movement = sum(self.movement_history) / len(self.movement_history)
        
        # Detect movement if current movement is significantly higher than average
        if movement > avg_movement * 1.2:  # More lenient movement detection
            self.head_movement_count += 1
            return True
        return False

    def analyze_texture(self, face_image):
        # Convert to grayscale
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        
        # Apply FFT
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1)
        
        # Calculate texture features
        mean_magnitude = np.mean(magnitude_spectrum)
        std_magnitude = np.std(magnitude_spectrum)
        
        # More lenient texture analysis
        return mean_magnitude > self.texture_threshold and std_magnitude > self.texture_threshold

    def check_liveness(self, face_image, landmarks, face_position):
        # Check for blinks
        if landmarks is not None:
            self.detect_blink(landmarks)
        
        # Check for head movement
        if face_position is not None:
            self.detect_head_movement(face_position)
        
        # Analyze texture
        texture_check = self.analyze_texture(face_image)
        
        # More lenient liveness check
        return (self.blink_count >= self.required_blinks or 
                self.head_movement_count >= self.required_movements) and texture_check

    def reset(self):
        self.blink_count = 0
        self.head_movement_count = 0
        self.last_face_position = None
        self.blink_history = []
        self.movement_history = []

class ViTFaceRecognitionSystem:
    def __init__(self, database, model_path=None):
        self.database = database
        self.known_face_encodings = []
        self.known_face_ids = []
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Initialize liveness detector
        self.liveness_detector = LivenessDetector()

        # Initialize ViT model
        self.model = self._load_vit_model(model_path)
        self.model.to(self.device)
        self.model.eval()

        # Define image transformations
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])

        # Load face detector
        self.face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

        # Load existing face encodings
        self.load_face_encodings()

    def _load_vit_model(self, model_path):
        """Load the ViT model from the specified path"""
        # Load the pretrained ViT model
        model = ViTModel.from_pretrained("google/vit-base-patch16-224-in21k")
        
        # Add a projection head for face embeddings
        model.head = nn.Sequential(
            nn.Linear(model.config.hidden_size, 512),
            nn.LayerNorm(512),
            nn.GELU(),
            nn.Linear(512, 512)  # Output dimension for face encoding
        )
        
        if model_path and os.path.exists(model_path):
            model.load_state_dict(torch.load(model_path, map_location=self.device))
        
        return model

    def load_face_encodings(self):
        """Load face encodings from the database"""
        student_encodings = self.database.get_student_face_encodings()

        self.known_face_encodings = []
        self.known_face_ids = []

        for student_id, face_encoding in student_encodings:
            if face_encoding:
                try:
                    encoding = pickle.loads(face_encoding)
                    # Normalize the encoding
                    encoding = encoding / np.linalg.norm(encoding)
                    self.known_face_encodings.append(encoding)
                    self.known_face_ids.append(student_id)
                    print(f"Loaded face encoding for student {student_id}")
                except Exception as e:
                    print(f"Error loading face encoding for student {student_id}: {e}")

        print(f"Loaded {len(self.known_face_encodings)} face encodings")

    def preprocess_face(self, face_img):
        """Preprocess face image for ViT model"""
        # Convert BGR to RGB
        face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        # Convert to PIL Image
        face_img = Image.fromarray(face_img)
        # Apply transformations
        face_tensor = self.transform(face_img)
        return face_tensor.unsqueeze(0)  # Add batch dimension

    def encode_face(self, image):
        """Generate face encoding from an image using ViT model"""
        # Detect faces
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # More lenient face detection parameters
        faces = self.face_detector.detectMultiScale(
            gray,
            scaleFactor=1.05,  # Reduced from 1.1 to detect faces at different scales
            minNeighbors=3,    # Reduced from 4 to be more lenient
            minSize=(20, 20),  # Minimum face size
            maxSize=(500, 500) # Maximum face size to handle faces at different distances
        )

        if len(faces) == 0:
            print("No faces detected in encode_face")
            return None

        # Get the first face
        x, y, w, h = faces[0]
        face_img = image[y:y+h, x:x+w]

        # Preprocess face
        face_tensor = self.preprocess_face(face_img)
        face_tensor = face_tensor.to(self.device)

        # Get face encoding
        with torch.no_grad():
            outputs = self.model(face_tensor)
            face_encoding = outputs.last_hidden_state[:, 0]  # Use [CLS] token
            face_encoding = self.model.head(face_encoding)  # Project to face embedding space
            face_encoding = face_encoding.cpu().numpy().flatten()

        return pickle.dumps(face_encoding)

    def recognize_faces(self, frame, reference_number=None):
        """Recognize faces in a frame using ViT model with liveness detection"""
        if not self.known_face_encodings:
            print("No face encodings loaded from database")
            return {'recognized': [], 'unrecognized': []}

        # Detect faces
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_detector.detectMultiScale(
            gray,
            scaleFactor=1.05,
            minNeighbors=3,
            minSize=(20, 20),
            maxSize=(500, 500)
        )

        if len(faces) == 0:
            print("No faces detected in frame")
            return {'recognized': [], 'unrecognized': []}

        print(f"Detected {len(faces)} faces in frame")
        recognized_students = []
        unrecognized_faces = []

        for (x, y, w, h) in faces:
            face_rect = (x, y, w, h)
            
            # Perform liveness detection
            if not self.liveness_detector.check_liveness(frame, None, face_rect):
                print("Liveness check failed - possible spoofing attempt")
                unrecognized_faces.append({
                    'location': (y, x+w, y+h, x),
                    'message': "Liveness check failed"
                })
                continue

            face_img = frame[y:y+h, x:x+w]
            print(f"Processing face at position ({x}, {y}) with size {w}x{h}")
            
            # Get face encoding
            face_tensor = self.preprocess_face(face_img)
            face_tensor = face_tensor.to(self.device)
            
            with torch.no_grad():
                outputs = self.model(face_tensor)
                face_encoding = outputs.last_hidden_state[:, 0]
                face_encoding = self.model.head(face_encoding)
                face_encoding = face_encoding.cpu().numpy().flatten()

            # Normalize the face encoding
            face_encoding = face_encoding / np.linalg.norm(face_encoding)

            # Compare with known faces
            distances = []
            for i, known_encoding in enumerate(self.known_face_encodings):
                similarity = np.dot(face_encoding, known_encoding)
                distance = 1 - similarity
                distances.append(distance)
                print(f"Distance to known face {i}: {distance}")

            if len(distances) > 0:
                best_match_index = np.argmin(distances)
                min_distance = distances[best_match_index]
                print(f"Best match distance: {min_distance}, tolerance: {FACE_RECOGNITION_TOLERANCE}")

                if min_distance <= FACE_RECOGNITION_TOLERANCE:
                    student_id = self.known_face_ids[best_match_index]

                    if reference_number is not None:
                        if not self.database.is_student_enrolled_in_course(student_id, reference_number):
                            print(f"Student {student_id} not enrolled in course {reference_number}")
                            unrecognized_faces.append({
                                'location': (y, x+w, y+h, x),
                                'message': "Not enrolled"
                            })
                            continue

                    student_data = self.database.get_user_by_id(student_id)
                    student_name = student_data[3] if student_data else f"Student {student_id}"
                    print(f"Recognized student: {student_name} (ID: {student_id})")

                    recognized_students.append({
                        'student_id': student_id,
                        'name': student_name,
                        'confidence': 1 - (min_distance / FACE_RECOGNITION_TOLERANCE),
                        'location': (y, x+w, y+h, x)
                    })
                else:
                    print(f"Face not recognized - distance {min_distance} exceeds tolerance {FACE_RECOGNITION_TOLERANCE}")
                    unrecognized_faces.append({
                        'location': (y, x+w, y+h, x),
                        'message': "Unknown"
                    })
            else:
                unrecognized_faces.append({
                    'location': (y, x+w, y+h, x),
                    'message': "Unknown"
                })

        return {
            'recognized': recognized_students,
            'unrecognized': unrecognized_faces
        }

    def draw_recognition_results(self, frame, recognition_results):
        """Draw bounding boxes and labels on the frame"""
        # Draw recognized faces with green boxes
        for student in recognition_results['recognized']:
            top, right, bottom, left = student['location']
            student_id = student['student_id']
            name = student['name']
            confidence = student['confidence']

            # Draw rectangle around the face
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)

            # Draw label background
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 255, 0), cv2.FILLED)

            # Put text
            cv2.putText(
                frame,
                f"{name} ({confidence:.2f})",
                (left + 6, bottom - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

        # Draw unrecognized faces with red boxes
        for face in recognition_results['unrecognized']:
            top, right, bottom, left = face['location']
            message = face['message']

            # Draw rectangle around the face
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)

            # Draw label background
            cv2.rectangle(frame, (left, bottom - 35), (right, bottom), (0, 0, 255), cv2.FILLED)

            # Put text
            cv2.putText(
                frame,
                message,
                (left + 6, bottom - 6),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )

        return frame

    def mark_attendance_for_recognized_students(self, recognition_results, reference_number):
        """Mark attendance for recognized students"""
        attendance_results = []

        # Get current date and time
        now = datetime.datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")
        current_time_obj = datetime.datetime.strptime(current_time, "%H:%M:%S").time()

        # Get course details for timing rules
        course = self.database.get_course_by_id(reference_number)
        if not course:
            return attendance_results

        # Get start and end times and convert to datetime.time objects
        course_start_str = course[4]  # start_time
        course_end_str = course[5]    # end_time

        course_start = datetime.datetime.strptime(course_start_str, "%H:%M").time()

        # Check for custom end time
        custom_end_time = self.database.get_custom_end_time(reference_number, today)
        if custom_end_time:
            course_end = datetime.datetime.strptime(custom_end_time, "%H:%M:%S").time()
        else:
            course_end = datetime.datetime.strptime(course_end_str, "%H:%M").time()

        # Calculate time objects for various thresholds
        early_arrival = (datetime.datetime.combine(datetime.date.today(), course_start) -
                        datetime.timedelta(minutes=EARLY_ARRIVAL_MARGIN)).time()

        late_threshold = (datetime.datetime.combine(datetime.date.today(), course_start) +
                        datetime.timedelta(minutes=LATE_THRESHOLD)).time()

        early_departure = (datetime.datetime.combine(datetime.date.today(), course_end) -
                        datetime.timedelta(minutes=EARLY_DEPARTURE_THRESHOLD)).time()

        second_checkin_start = (datetime.datetime.combine(datetime.date.today(), course_end) -
                              datetime.timedelta(minutes=SECOND_CHECKIN_WINDOW)).time()

        second_checkin_end = (datetime.datetime.combine(datetime.date.today(), course_end) +
                            datetime.timedelta(minutes=SECOND_CHECKIN_WINDOW)).time()

        for student in recognition_results['recognized']:
            student_id = student['student_id']
            name = student['name']

            # Check if student is enrolled in this course
            if self.database.is_student_enrolled_in_course(student_id, reference_number):
                # Check if this is the first or second attendance
                self.database.cursor.execute(
                    """
                    SELECT time, second_time, is_cancelled FROM attendance 
                    WHERE student_id = ? AND course_id = ? AND date = ?
                    """,
                    (student_id, reference_number, today)
                )
                result = self.database.cursor.fetchone()

                if result:
                    # If the class is cancelled, don't update attendance
                    if result[2] == 1:
                        attendance_results.append({
                            'student_id': student_id,
                            'name': name,
                            'success': False,
                            'message': "Class cancelled"
                        })
                        continue

                    # Check if this is a second check-in
                    if result[1] is None and second_checkin_start <= current_time_obj <= second_checkin_end:
                        # Update second check-in time
                        self.database.cursor.execute(
                            """
                            UPDATE attendance 
                            SET second_time = ? 
                            WHERE student_id = ? AND course_id = ? AND date = ?
                            """,
                            (current_time, student_id, reference_number, today)
                        )
                        self.database.conn.commit()

                        attendance_results.append({
                            'student_id': student_id,
                            'name': name,
                            'success': True,
                            'message': "Second check-in recorded"
                        })
                    else:
                        attendance_results.append({
                            'student_id': student_id,
                            'name': name,
                            'success': False,
                            'message': "Already checked in"
                        })
                else:
                    # First check-in
                    if current_time_obj < early_arrival:
                        attendance_results.append({
                            'student_id': student_id,
                            'name': name,
                            'success': False,
                            'message': "Too early"
                        })
                    elif current_time_obj > course_end:
                        attendance_results.append({
                            'student_id': student_id,
                            'name': name,
                            'success': False,
                            'message': "Class ended"
                        })
                    else:
                        # Determine attendance status
                        if current_time_obj <= late_threshold:
                            status = STATUS_PRESENT
                        else:
                            status = STATUS_LATE

                        # Insert attendance record
                        self.database.cursor.execute(
                            """
                            INSERT INTO attendance (student_id, course_id, date, time, status)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (student_id, reference_number, today, current_time, status)
                        )
                        self.database.conn.commit()

                        attendance_results.append({
                            'student_id': student_id,
                            'name': name,
                            'success': True,
                            'message': f"Marked as {status}"
                        })
            else:
                attendance_results.append({
                    'student_id': student_id,
                    'name': name,
                    'success': False,
                    'message': "Not enrolled in this course"
                })

        return attendance_results
