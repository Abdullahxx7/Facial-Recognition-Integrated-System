import os
import cv2
import numpy as np
import pickle
from database import Database
from vit_face_recognition import ViTFaceRecognitionSystem

def migrate_encodings():
    # Initialize database and face recognition system
    db = Database()
    face_recognition = ViTFaceRecognitionSystem(db)
    
    # Get all students with face encodings
    student_encodings = db.get_student_face_encodings()
    
    # Process each student
    for student_id, old_encoding in student_encodings:
        if old_encoding:
            try:
                # Get student's data including face image
                student_data = db.get_user_by_id(student_id)
                if not student_data:
                    print(f"Student {student_id} not found in database")
                    continue
                
                # Get face image from database
                face_image_blob = student_data[7]  # face_image is at index 7
                if not face_image_blob:
                    print(f"No face image found for student {student_id}")
                    continue
                
                # Convert BLOB to image
                nparr = np.frombuffer(face_image_blob, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if image is None:
                    print(f"Could not decode image for student {student_id}")
                    continue
                
                # Generate new encoding
                new_encoding = face_recognition.encode_face(image)
                if new_encoding is None:
                    print(f"Could not generate new encoding for student {student_id}")
                    continue
                
                # Update database
                db.update_user(student_id, face_encoding=new_encoding)
                print(f"Successfully migrated encoding for student {student_id}")
                
            except Exception as e:
                print(f"Error processing student {student_id}: {str(e)}")
    
    print("Migration completed")

if __name__ == "__main__":
    migrate_encodings() 