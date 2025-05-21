import sqlite3
import os
import datetime
from config import DATABASE_PATH, STATUS_PRESENT, STATUS_ABSENT, STATUS_LATE, STATUS_NA, STATUS_PARTIAL_ATTENDANCE, STATUS_UNAUTHORIZED_DEPARTURE, LATE_THRESHOLD, EARLY_ARRIVAL_MARGIN, SECOND_CHECKIN_WINDOW

class Database:
    def __init__(self):
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)

        # Check if we need to update the database schema
        self.db_exists = os.path.exists(DATABASE_PATH)

        # Connect to database
        self.conn = sqlite3.connect(DATABASE_PATH)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Create necessary tables if they don't exist"""

        # Users table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT,
            face_encoding BLOB,
            face_image BLOB
        )
        ''')

        # Check if we need to update the tables
        if self.db_exists:
            # Check columns in users table
            self.cursor.execute("PRAGMA table_info(users)")
            user_columns = [column[1] for column in self.cursor.fetchall()]

            if "email" not in user_columns:
                print("Upgrading database: Adding email column to users table")
                self.cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")

            if "face_image" not in user_columns:
                # Add face_image column to users table
                print("Upgrading database: Adding face_image column to users table")
                self.cursor.execute("ALTER TABLE users ADD COLUMN face_image BLOB")

        # Check if courses table exists first
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='courses'")
        table_exists = self.cursor.fetchone() is not None

        if not table_exists:
            # Create the courses table with the right schema if it doesn't exist
            self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS courses (
                reference_number INTEGER PRIMARY KEY,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                section TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                classroom TEXT DEFAULT 'N/A',
                start_date TEXT,
                end_date TEXT,
                days TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri',
                UNIQUE(code, section)
            )
            ''')
        else:
            # Check if we need to update the schema
            self.cursor.execute("PRAGMA table_info(courses)")
            columns = [column[1] for column in self.cursor.fetchall()]

            if 'id' in columns and 'reference_number' in columns:
                print("Migrating courses table to new schema...")

                # Create new table
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS courses_new (
                    reference_number INTEGER PRIMARY KEY,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    section TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    capacity INTEGER NOT NULL,
                    classroom TEXT DEFAULT 'N/A',
                    start_date TEXT,
                    end_date TEXT,
                    days TEXT DEFAULT 'Mon,Tue,Wed,Thu,Fri',
                    UNIQUE(code, section)
                )
                ''')

                # Copy data
                try:
                    self.cursor.execute('''
                    INSERT INTO courses_new (reference_number, code, name, section, start_time, end_time, capacity, 
                                            classroom, start_date, end_date, days)
                    SELECT CAST(reference_number AS INTEGER), code, name, section, start_time, end_time, capacity, 
                           classroom, start_date, end_date, days FROM courses
                    ''')

                    # Drop old table and rename new
                    self.cursor.execute("DROP TABLE courses")
                    self.cursor.execute("ALTER TABLE courses_new RENAME TO courses")
                    self.conn.commit()
                    print("Successfully migrated courses table")
                except Exception as e:
                    print(f"Error migrating courses table: {e}")
                    self.cursor.execute("DROP TABLE IF EXISTS courses_new")
            # If no migration needed, do nothing - table already has correct schema

        # Enrollments table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (reference_number),
            FOREIGN KEY (student_id) REFERENCES users (id),
            UNIQUE(course_id, student_id)
        )
        ''')

        # Course teachers table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS course_teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            teacher_id TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (reference_number),
            FOREIGN KEY (teacher_id) REFERENCES users (id),
            UNIQUE(course_id, teacher_id)
        )
        ''')

        # Attendance table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            course_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT,
            second_time TEXT,
            status TEXT NOT NULL,
            is_cancelled INTEGER DEFAULT 0,
            FOREIGN KEY (student_id) REFERENCES users (id),
            FOREIGN KEY (course_id) REFERENCES courses (reference_number),
            UNIQUE(student_id, course_id, date)
        )
        ''')

        # Create lectures table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS lectures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(reference_number)
        )
        ''')

        # Create absences table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS absences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lecture_id INTEGER NOT NULL,
            student_id TEXT NOT NULL,
            FOREIGN KEY (lecture_id) REFERENCES lectures(id),
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
        ''')

        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS lecture_custom_times (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            custom_end_time TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses (reference_number),
            UNIQUE(course_id, date)
        )
        ''')

        # Create default admin user if no users exist
        self.cursor.execute("SELECT COUNT(*) FROM users")
        if self.cursor.fetchone()[0] == 0:
            self.cursor.execute(
                "INSERT INTO users (id, username, password, name, role) VALUES (?, ?, ?, ?, ?)",
                ("ADMIN001", "admin", "admin123", "System Administrator", "admin")
            )

        self.conn.commit()

    def authenticate_user(self, username, password):
        """Authenticate a user and return their role if successful"""
        try:
            self.cursor.execute(
                "SELECT id, role FROM users WHERE username = ? AND password = ?",
                (username, password)
            )
            result = self.cursor.fetchone()
            if result:
                return {"user_id": result[0], "role": result[1]}
            return None
        except Exception as e:
            print(f"Error authenticating user: {e}")
            return None

    def authenticate_by_id(self, user_id, password):
        """Authenticate a user by ID and password and return their role if successful"""
        try:
            self.cursor.execute(
                "SELECT id, role FROM users WHERE id = ? AND password = ?",
                (user_id, password)
            )
            result = self.cursor.fetchone()
            if result:
                return {"user_id": result[0], "role": result[1]}
            return None
        except Exception as e:
            print(f"Error authenticating user by ID: {e}")
            return None

    # User management methods
    def add_user(self, user_id, username, password, name, role, email=None, face_encoding=None, face_image=None):
        """Add a new user to the database"""
        try:
            self.cursor.execute(
                "INSERT INTO users (id, username, password, name, role, email, face_encoding, face_image) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, password, name, role, email, face_encoding, face_image)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_users_by_role(self, role):
        """Get all users with the specified role"""
        self.cursor.execute("SELECT id, username, name, email FROM users WHERE role = ?", (role,))
        return self.cursor.fetchall()

    def get_user_by_id(self, user_id):
        """Get user details by ID with improved error handling"""
        try:
            self.cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Error getting user by ID {user_id}: {e}")
            return None

    def update_user(self, user_id, username=None, password=None, name=None, role=None, email=None, face_encoding=None, face_image=None):
        """Update an existing user"""
        try:
            # Only update profile information if any field is provided
            if username is not None or name is not None or role is not None or email is not None:
                # First get current values to use as defaults
                self.cursor.execute("SELECT username, name, role, email FROM users WHERE id = ?", (user_id,))
                current = self.cursor.fetchone()

                if not current:
                    print(f"Error: User {user_id} not found")
                    return False

                # Use provided values or keep current ones
                username_val = username if username is not None else current[0]
                name_val = name if name is not None else current[1]
                role_val = role if role is not None else current[2]
                email_val = email if email is not None else current[3] if len(current) > 3 else None

                # For students, ensure username is the same as ID
                if role_val == "student" and username_val != user_id:
                    username_val = user_id

                # Update profile information
                if password is not None:
                    self.cursor.execute(
                        "UPDATE users SET username = ?, password = ?, name = ?, role = ?, email = ? WHERE id = ?",
                        (username_val, password, name_val, role_val, email_val, user_id)
                    )
                else:
                    self.cursor.execute(
                        "UPDATE users SET username = ?, name = ?, role = ?, email = ? WHERE id = ?",
                        (username_val, name_val, role_val, email_val, user_id)
                    )

            # Update face encoding if provided
            if face_encoding is not None:
                self.cursor.execute("UPDATE users SET face_encoding = ? WHERE id = ?", (face_encoding, user_id))

            # Update face image if provided
            if face_image is not None:
                self.cursor.execute("UPDATE users SET face_image = ? WHERE id = ?", (face_image, user_id))

            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating user: {e}")
            return False

    def delete_user(self, user_id):
        """Delete a user from the database"""
        self.cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()

    # Course management methods
    def add_course(self, reference_number, code, name, section, start_time, end_time, capacity,
               classroom="N/A", start_date=None, end_date=None, days="Mon,Tue,Wed,Thu,Fri"):
        """Add a new course to the database"""
        try:
            # Make sure reference_number is an integer
            reference_number = int(reference_number)

            # Execute the SQL statement
            self.cursor.execute(
                """
                INSERT INTO courses (reference_number, code, name, section, start_time, end_time, capacity, classroom, start_date, end_date, days)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (reference_number, code, name, section, start_time, end_time, capacity, classroom, start_date, end_date, days)
            )

            # Commit changes
            self.conn.commit()

            print(f"Successfully added course with reference_number={reference_number}")
            return True
        except Exception as e:
            print(f"Error adding course: {e}")
            # Roll back any partial changes
            self.conn.rollback()
            return False

    def get_all_courses(self):
        """Get all courses with updated column order"""
        self.cursor.execute(
            """
            SELECT reference_number, code, name, section, start_time, end_time, capacity, 
                   classroom, start_date, end_date, days 
            FROM courses
            ORDER BY code, section
            """
        )
        return self.cursor.fetchall()

    def get_course_by_id(self, reference_number):
        """Get course details by reference number (now the primary key)"""
        try:
            reference_number = int(reference_number)
        except ValueError:
            print(f"Invalid reference number: {reference_number}. Must be an integer.")
            return None

        self.cursor.execute(
            """
            SELECT reference_number, code, name, section, start_time, end_time, capacity, 
                   classroom, start_date, end_date, days
            FROM courses WHERE reference_number = ?
            """,
            (reference_number,)
        )
        return self.cursor.fetchone()

    def get_current_courses(self):
        """Get courses that are currently in session based on time"""
        now = datetime.datetime.now()
        current_time = now.strftime("%H:%M")
        current_date = now.strftime("%Y-%m-%d")
        weekday = now.strftime("%a")  # Get abbreviated weekday name (Mon, Tue, etc.)

        # Get all courses for today
        self.cursor.execute(
            """
            SELECT reference_number, code, name, section, start_time, end_time, classroom
            FROM courses
            WHERE days LIKE ?
              AND (start_date IS NULL OR date(?) >= date(start_date))
              AND (end_date IS NULL OR date(?) <= date(end_date))
            """,
            (f"%{weekday}%", current_date, current_date)
        )

        all_courses = self.cursor.fetchall()
        current_courses = []

        # Filter courses based on time in Python
        now_time = datetime.datetime.strptime(current_time, "%H:%M").time()

        for course in all_courses:
            start_time = datetime.datetime.strptime(course[4], "%H:%M").time()
            end_time = datetime.datetime.strptime(course[5], "%H:%M").time()

            # Calculate early arrival time
            early_time = (datetime.datetime.combine(datetime.date.today(), start_time) -
                          datetime.timedelta(minutes=EARLY_ARRIVAL_MARGIN)).time()

            # Check if current time is between early arrival time and end time
            if (early_time <= now_time <= end_time):
                current_courses.append(course)

        return current_courses


    def update_course(self, reference_number, code, name, section, start_time, end_time, capacity,
                  classroom="N/A", start_date=None, end_date=None, days="Mon,Tue,Wed,Thu,Fri"):
        """Update an existing course"""
        try:
            self.cursor.execute(
                """
                UPDATE courses
                SET code = ?, name = ?, section = ?, start_time = ?, end_time = ?, capacity = ?, classroom = ?, start_date = ?, end_date = ?, days = ?
                WHERE reference_number = ?
                """,
                (code, name, section, start_time, end_time, capacity, classroom, start_date, end_date, days, reference_number)
            )
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating course: {e}")
            # Roll back any partial changes
            self.conn.rollback()
            return False

    def delete_course(self, reference_number):
        """Delete a course and its enrollments"""
        try:
            # First delete all enrollments for this course
            self.cursor.execute(
                """
                DELETE FROM enrollments
                WHERE course_id = ?
                """,
                (reference_number,)
            )

            # Delete all teacher assignments for this course
            self.cursor.execute(
                """
                DELETE FROM course_teachers
                WHERE course_id = ?
                """,
                (reference_number,)
            )

            # Delete the course
            self.cursor.execute(
                """
                DELETE FROM courses
                WHERE reference_number = ?
                """,
                (reference_number,)
            )

            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting course: {e}")
            # Roll back any partial changes
            self.conn.rollback()
            return False

    # Enrollment methods
    def enroll_student(self, course_id, student_id):
        """Enroll a student in a course with enhanced validation to prevent enrolling in multiple sections"""
        try:
            # Check if student is already enrolled in this section
            self.cursor.execute(
                """
                SELECT COUNT(*) FROM enrollments
                WHERE course_id = ? AND student_id = ?
                """,
                (course_id, student_id)
            )
            is_enrolled_in_section = self.cursor.fetchone()[0] > 0

            if is_enrolled_in_section:
                print(f"Student {student_id} is already enrolled in section {course_id}")
                return False

            # Get the course code for the section
            self.cursor.execute(
                """
                SELECT code FROM courses WHERE reference_number = ?
                """,
                (course_id,)
            )
            result = self.cursor.fetchone()
            if not result:
                print(f"Could not find course code for section {course_id}")
                return False

            course_code = result[0]

            # Check if student is already enrolled in another section of the same course
            self.cursor.execute(
                """
                SELECT e.course_id 
                FROM enrollments e
                JOIN courses c ON e.course_id = c.reference_number
                WHERE e.student_id = ? AND c.code = ? AND c.reference_number != ?
                """,
                (student_id, course_code, course_id)
            )
            result = self.cursor.fetchone()

            if result:
                print(f"Student {student_id} is already enrolled in another section of course {course_code}")
                return False

            # Check if course has capacity
            enrollment_data = self.get_enrollment_data(course_id)

            if not enrollment_data or enrollment_data['enrolled'] >= enrollment_data['capacity']:
                print(f"Section {course_id} is at full capacity")
                return False

            # All checks passed, enroll the student
            self.cursor.execute(
                "INSERT INTO enrollments (course_id, student_id) VALUES (?, ?)",
                (course_id, student_id)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError as e:
            print(f"IntegrityError enrolling student {student_id} in course {course_id}: {e}")
            return False
        except Exception as e:
            print(f"Error enrolling student {student_id} in course {course_id}: {e}")
            self.conn.rollback()
            return False

    def unenroll_student(self, course_id, student_id):
        """Remove a student from a course"""
        self.cursor.execute(
            "DELETE FROM enrollments WHERE course_id = ? AND student_id = ?",
            (course_id, student_id)
        )
        self.conn.commit()

    def get_enrollment_data(self, reference_number):
        """Get enrollment data for a course by reference number"""
        try:
            reference_number = int(reference_number)
        except ValueError:
            print(f"Invalid reference number: {reference_number}. Must be an integer.")
            return None

        # Get enrolled students count
        self.cursor.execute(
            """
            SELECT COUNT(*) FROM enrollments
            WHERE course_id = ?
            """,
            (reference_number,)
        )
        enrolled_count = self.cursor.fetchone()[0]

        # Get course capacity
        self.cursor.execute(
            """
            SELECT capacity FROM courses
            WHERE reference_number = ?
            """,
            (reference_number,)
        )
        capacity = self.cursor.fetchone()[0]

        return {
            'enrolled': enrolled_count,
            'capacity': capacity,
            'available': capacity - enrolled_count
        }

    def get_enrolled_students(self, course_id):
        """Get all students enrolled in a course by reference number"""
        self.cursor.execute(
            """
            SELECT u.id, u.username, u.name
            FROM users u
            JOIN enrollments e ON u.id = e.student_id
            WHERE e.course_id = ?
            """,
            (course_id,)
        )
        return self.cursor.fetchall()

    def search_enrolled_students(self, course_id, search_text):
        """Search for students enrolled in a course by exact sequence matching"""
        search_pattern = f"%{search_text}%"
        self.cursor.execute(
            """
            SELECT u.id, u.username, u.name
            FROM users u
            JOIN enrollments e ON u.id = e.student_id
            WHERE e.course_id = ? AND (u.name LIKE ? OR u.id LIKE ?)
            """,
            (course_id, search_pattern, search_pattern)
        )
        return self.cursor.fetchall()

    def search_students_exact(self, search_text, limit=20):
        """Search for students with exact character sequence matching"""
        search_pattern = f"%{search_text}%"
        self.cursor.execute(
            """
            SELECT id, name FROM users 
            WHERE (name LIKE ? OR id LIKE ?) AND role = 'student'
            LIMIT ?
            """,
            (search_pattern, search_pattern, limit)
        )
        return self.cursor.fetchall()

    def get_student_courses(self, student_id):
        """Get all courses a student is enrolled in"""
        self.cursor.execute(
            """
            SELECT c.reference_number, c.code, c.name, c.section, c.start_time, c.end_time, c.classroom, c.days
            FROM courses c
            JOIN enrollments e ON c.reference_number = e.course_id
            WHERE e.student_id = ?
            """,
            (student_id,)
        )
        return self.cursor.fetchall()

    def get_next_course_section_info(self, course_code):
        """Get the next sequential section number and reference number for a course.

        Args:
            course_code: The course code to look up

        Returns:
            tuple: (next_section_number, next_reference_number)
        """
        try:
            # Get the last section for this course (sort by section number)
            self.cursor.execute(
                """
                SELECT section, reference_number FROM courses
                WHERE code = ?
                ORDER BY CAST(section AS INTEGER) DESC
                LIMIT 1
                """,
                (course_code,)
            )
            last_section_data = self.cursor.fetchone()

            if last_section_data:
                last_section, last_reference = last_section_data

                # Generate next section number (increment from the last section)
                try:
                    # Try to convert to integer and increment
                    next_section = int(last_section) + 1
                except (ValueError, TypeError):
                    # If conversion fails, default to 171
                    next_section = 171

                # Generate next reference number (increment from the last reference number)
                try:
                    next_reference = int(last_reference) + 1
                except (ValueError, TypeError):
                    # If conversion fails, use None for manual entry
                    next_reference = None
            else:
                # No existing sections, default to 171 and None
                next_section = 171
                next_reference = None

            return (next_section, next_reference)
        except Exception as e:
            print(f"Error getting next course section info: {e}")
            return (171, None)  # Default values

    # Teacher-course assignment methods
    def assign_teacher(self, course_id, teacher_id):
        """Assign a teacher to a course"""
        try:
            self.cursor.execute(
                "INSERT INTO course_teachers (course_id, teacher_id) VALUES (?, ?)",
                (course_id, teacher_id)
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def unassign_teacher(self, course_id, teacher_id):
        """Remove a teacher from a course"""
        self.cursor.execute(
            "DELETE FROM course_teachers WHERE course_id = ? AND teacher_id = ?",
            (course_id, teacher_id)
        )
        self.conn.commit()

    def get_teacher_courses(self, teacher_id):
        """Get all courses assigned to a teacher"""
        self.cursor.execute(
            """
            SELECT c.reference_number, c.code, c.name, c.section, c.start_time, c.end_time, c.classroom, c.days,
                   c.start_date, c.end_date
            FROM courses c
            JOIN course_teachers ct ON c.reference_number = ct.course_id
            WHERE ct.teacher_id = ?
            """,
            (teacher_id,)
        )
        return self.cursor.fetchall()

    def get_course_teachers(self, course_id):
        """Get all teachers assigned to a course"""
        self.cursor.execute(
            """
            SELECT u.id, u.username, u.name
            FROM users u
            JOIN course_teachers ct ON u.id = ct.teacher_id
            WHERE ct.course_id = ? AND u.role = 'teacher'
            """,
            (course_id,)
        )
        return self.cursor.fetchall()

    # Attendance methods
    def mark_attendance(self, student_id, course_id, date, time, status):
        """Mark attendance for a student"""
        try:
            # Check if this is the first or second attendance of the day
            self.cursor.execute(
                """
                SELECT time, second_time, is_cancelled FROM attendance 
                WHERE student_id = ? AND course_id = ? AND date = ?
                """,
                (student_id, course_id, date)
            )
            result = self.cursor.fetchone()

            if result:
                # If the class is cancelled, don't update attendance
                if result[2] == 1:
                    return False

                # Record already exists, this is second attendance
                first_time = result[0]
                second_time = result[1]

                if second_time is None:
                    # Update with second attendance time
                    self.cursor.execute(
                        """
                        UPDATE attendance SET second_time = ?, status = ?
                        WHERE student_id = ? AND course_id = ? AND date = ?
                        """,
                        (time, status, student_id, course_id, date)
                    )
                else:
                    # Both attendance records already exist, don't update
                    return False
            else:
                # First attendance of the day
                self.cursor.execute(
                    """
                    INSERT INTO attendance (student_id, course_id, date, time, status)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (student_id, course_id, date, time, status)
                )

            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error marking attendance: {e}")
            return False

    def auto_mark_attendance(self, student_id, course_id):
        """Automatically mark attendance based on current time with updated timing rules"""
        now = datetime.datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")
        current_time_obj = datetime.datetime.strptime(current_time, "%H:%M:%S").time()

        # Get course details
        course = self.get_course_by_id(course_id)
        if not course:
            return False

        # Get start and end times and convert to datetime.time objects
        course_start_str = course[4]  # start_time
        course_end_str = course[5]    # end_time

        course_start = datetime.datetime.strptime(course_start_str, "%H:%M").time()

        # Check for custom end time
        custom_end_time = self.get_custom_end_time(course_id, today)
        if custom_end_time:
            course_end = datetime.datetime.strptime(custom_end_time, "%H:%M:%S").time()
        else:
            course_end = datetime.datetime.strptime(course_end_str, "%H:%M").time()

        # Calculate time objects for various thresholds
        early_arrival = (datetime.datetime.combine(datetime.date.today(), course_start) -
                         datetime.timedelta(minutes=EARLY_ARRIVAL_MARGIN)).time()

        late_threshold = (datetime.datetime.combine(datetime.date.today(), course_start) +
                          datetime.timedelta(minutes=LATE_THRESHOLD)).time()

        # Check if this is the first or second attendance
        self.cursor.execute(
            """
            SELECT time, second_time, is_cancelled FROM attendance 
            WHERE student_id = ? AND course_id = ? AND date = ?
            """,
            (student_id, course_id, today)
        )
        result = self.cursor.fetchone()

        try:
            if result:
                # If the class is cancelled, don't update attendance
                if result[2] == 1:
                    return False

                # Record exists, check if this should be a second check-in
                first_time = result[0]
                second_time = result[1]

                # Calculate second check-in window based on actual end time
                second_checkin_start = (datetime.datetime.combine(datetime.date.today(), course_end) -
                                      datetime.timedelta(minutes=SECOND_CHECKIN_WINDOW)).time()

                second_checkin_end = (datetime.datetime.combine(datetime.date.today(), course_end) +
                                    datetime.timedelta(minutes=SECOND_CHECKIN_WINDOW)).time()

                # Only allow second check-in within the specified window
                if second_time is None and second_checkin_start <= current_time_obj <= second_checkin_end:
                    # Update with second attendance time
                    self.cursor.execute(
                        """
                        UPDATE attendance SET second_time = ?
                        WHERE student_id = ? AND course_id = ? AND date = ?
                        """,
                        (current_time, student_id, course_id, today)
                    )
                    self.conn.commit()
                    return True
                else:
                    # Outside second check-in window or already has second check-in
                    return False
            else:
                # Calculate early departure threshold based on course end time
                early_departure = (datetime.datetime.combine(datetime.date.today(), course_end) -
                                 datetime.timedelta(minutes=10)).time()  # Using a 10-minute window before end

                # First attendance of the day - only allow within the valid window
                if early_arrival <= current_time_obj <= early_departure:
                    # Determine status based on arrival time
                    if current_time_obj > late_threshold:
                        status = STATUS_LATE
                    else:
                        status = STATUS_PRESENT

                    # Insert first attendance record
                    self.cursor.execute(
                        """
                        INSERT INTO attendance (student_id, course_id, date, time, status)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (student_id, course_id, today, current_time, status)
                    )
                    self.conn.commit()
                    return True
                else:
                    # Outside valid first check-in window
                    return False

        except Exception as e:
            print(f"Error auto-marking attendance: {e}")
            return False

    def update_partial_attendance(self):
        """
        Update attendance statuses at the end of day:
        - Mark students with only first check-in as Unauthorized Departure
        - Keep late status for students who were late
        """
        try:
            # Get current date
            today = datetime.datetime.now().strftime("%Y-%m-%d")

            # Find present students with first check-in but no second check-in
            self.cursor.execute(
                """
                UPDATE attendance 
                SET status = ?
                WHERE date = ? AND time IS NOT NULL AND second_time IS NULL
                AND status = ? AND is_cancelled = 0
                """,
                (STATUS_UNAUTHORIZED_DEPARTURE, today, STATUS_PRESENT)
            )

            # Late students with no second check-in remain Late (no change needed)

            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error updating partial attendance: {e}")
            return False

    def end_lecture_early(self, course_id, date, time):
        """Record that a lecture ended early by updating its end time for the specific date"""
        try:
            # Store the custom end time for this specific lecture
            self.cursor.execute(
                """
                INSERT OR REPLACE INTO lecture_custom_times 
                (course_id, date, custom_end_time) 
                VALUES (?, ?, ?)
                """,
                (course_id, date, time)
            )

            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error ending lecture early: {e}")
            return False

    def get_custom_end_time(self, course_id, date):
        """Get the custom end time for a specific lecture if it exists"""
        try:
            self.cursor.execute(
                """
                SELECT custom_end_time FROM lecture_custom_times
                WHERE course_id = ? AND date = ?
                """,
                (course_id, date)
            )
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error getting custom end time: {e}")
            return None

    def cancel_lecture(self, course_id, date):
        """Cancel a lecture for the specified course (using reference number) and date"""
        try:
            print(f"Database: Cancelling lecture for course {course_id} on date {date}")

            # First check if this lecture is already cancelled
            self.cursor.execute(
                """
                SELECT COUNT(*) FROM attendance
                WHERE course_id = ? AND date = ? AND is_cancelled = 1
                """,
                (course_id, date)
            )
            already_cancelled = self.cursor.fetchone()[0] > 0

            if already_cancelled:
                print(f"Lecture already cancelled for course {course_id} on date {date}")
                return True  # Already cancelled is considered success

            # Check if there are any attendance records for this course and date
            self.cursor.execute(
                """
                SELECT COUNT(*) FROM attendance
                WHERE course_id = ? AND date = ?
                """,
                (course_id, date)
            )

            count = self.cursor.fetchone()[0]
            print(f"Found {count} existing attendance records")

            if count > 0:
                # Update existing records to mark them as cancelled
                print("Updating existing records to cancelled")
                self.cursor.execute(
                    """
                    UPDATE attendance SET status = ?, is_cancelled = 1
                    WHERE course_id = ? AND date = ?
                    """,
                    (STATUS_NA, course_id, date)
                )
            else:
                # Get all students enrolled in this course
                print("No existing records, creating cancelled records for all enrolled students")
                students = self.get_enrolled_students(course_id)
                print(f"Found {len(students)} enrolled students")

                # Create attendance records for all students marked as N/A
                for student in students:
                    student_id = student[0]
                    self.cursor.execute(
                        """
                        INSERT INTO attendance (student_id, course_id, date, status, is_cancelled)
                        VALUES (?, ?, ?, ?, 1)
                        """,
                        (student_id, course_id, date, STATUS_NA)
                    )

            self.conn.commit()
            print(f"Successfully cancelled lecture for course {course_id} on date {date}")
            return True
        except Exception as e:
            print(f"Error cancelling lecture: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_attendance_records(self, course_id, date=None):
        """Get attendance records for a course"""
        if date:
            self.cursor.execute(
                """
                SELECT u.id, u.name, a.status, a.time, a.second_time, a.is_cancelled
                FROM users u
                JOIN attendance a ON u.id = a.student_id
                WHERE a.course_id = ? AND a.date = ?
                ORDER BY u.name
                """,
                (course_id, date)
            )
        else:
            self.cursor.execute(
                """
                SELECT u.id, u.name, a.date, a.status, a.time, a.second_time, a.is_cancelled
                FROM users u
                JOIN attendance a ON u.id = a.student_id
                WHERE a.course_id = ?
                ORDER BY a.date DESC, u.name
                """,
                (course_id,)
            )
        return self.cursor.fetchall()

    def get_student_attendance_stats(self, student_id, course_id=None):
        """Get attendance statistics for a student"""
        if course_id:
            # For a specific course
            self.cursor.execute(
                """
                SELECT status, COUNT(*) 
                FROM attendance 
                WHERE student_id = ? AND course_id = ? AND is_cancelled = 0
                GROUP BY status
                """,
                (student_id, course_id)
            )
        else:
            # For all courses
            self.cursor.execute(
                """
                SELECT status, COUNT(*) 
                FROM attendance 
                WHERE student_id = ? AND is_cancelled = 0
                GROUP BY status
                """,
                (student_id,)
            )

        # Convert to a dictionary
        results = self.cursor.fetchall()
        stats = {status: count for status, count in results}

        # Calculate total classes (excluding cancelled)
        if course_id:
            self.cursor.execute(
                """
                SELECT COUNT(DISTINCT date) 
                FROM attendance 
                WHERE student_id = ? AND course_id = ? AND is_cancelled = 0
                """,
                (student_id, course_id)
            )
        else:
            self.cursor.execute(
                """
                SELECT COUNT(DISTINCT date, course_id) 
                FROM attendance 
                WHERE student_id = ? AND is_cancelled = 0
                """,
                (student_id,)
            )

        total_days = self.cursor.fetchone()[0]
        stats['total_days'] = total_days

        return stats

    def get_course_attendance_stats(self, course_id):
        """Get attendance statistics for a course"""
        # Get total enrolled students
        self.cursor.execute(
            """
            SELECT COUNT(*) FROM enrollments
            WHERE course_id = ?
            """,
            (course_id,)
        )
        total_students = self.cursor.fetchone()[0]

        # Get total class days (excluding cancelled)
        self.cursor.execute(
            """
            SELECT COUNT(DISTINCT date) FROM attendance
            WHERE course_id = ? AND is_cancelled = 0
            """,
            (course_id,)
        )
        total_classes = self.cursor.fetchone()[0]

        # Get counts by status
        self.cursor.execute(
            """
            SELECT status, COUNT(*) FROM attendance
            WHERE course_id = ? AND is_cancelled = 0
            GROUP BY status
            """,
            (course_id,)
        )
        status_counts = dict(self.cursor.fetchall())

        # Get attendance trends by date
        self.cursor.execute(
            """
            SELECT date, status, COUNT(*) 
            FROM attendance
            WHERE course_id = ? AND is_cancelled = 0
            GROUP BY date, status
            ORDER BY date
            """,
            (course_id,)
        )

        # Process date-based attendance data
        date_results = self.cursor.fetchall()
        attendance_by_date = {}

        for date, status, count in date_results:
            if date not in attendance_by_date:
                attendance_by_date[date] = {}
            attendance_by_date[date][status] = count

        # Calculate percentages
        stats = {
            'total_students': total_students,
            'total_classes': total_classes,
            'status_counts': status_counts,
            'attendance_by_date': attendance_by_date
        }

        if total_students > 0 and total_classes > 0:
            total_possible = total_students * total_classes
            present_count = status_counts.get(STATUS_PRESENT, 0)
            late_count = status_counts.get(STATUS_LATE, 0)
            absent_count = status_counts.get(STATUS_ABSENT, 0)
            unauthorized_count = status_counts.get(STATUS_UNAUTHORIZED_DEPARTURE, 0)

            stats['present_rate'] = (present_count / total_possible) * 100 if total_possible > 0 else 0
            stats['late_rate'] = (late_count / total_possible) * 100 if total_possible > 0 else 0
            stats['absent_rate'] = (absent_count / total_possible) * 100 if total_possible > 0 else 0
            stats['unauthorized_rate'] = (unauthorized_count / total_possible) * 100 if total_possible > 0 else 0
            stats['attendance_rate'] = ((present_count + late_count) / total_possible) * 100 if total_possible > 0 else 0

        return stats

    def get_student_face_encodings(self):
        """Get all student face encodings"""
        self.cursor.execute(
            "SELECT id, face_encoding FROM users WHERE role = ? AND face_encoding IS NOT NULL",
            ("student",)
        )
        return self.cursor.fetchall()

    def is_student_enrolled_in_course(self, student_id, course_id):
        """Check if a student is enrolled in a specific course"""
        self.cursor.execute(
            """
            SELECT COUNT(*) FROM enrollments
            WHERE student_id = ? AND course_id = ?
            """,
            (student_id, course_id)
        )
        return self.cursor.fetchone()[0] > 0

    def add_lecture(self, course_id, date):
        """Add a new lecture for a course"""
        self.cursor.execute(
            "INSERT INTO lectures (course_id, date) VALUES (?, ?)",
            (course_id, date)
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def get_lecture(self, course_id, date):
        """Get a lecture by course_id and date"""
        self.cursor.execute(
            "SELECT id FROM lectures WHERE course_id = ? AND date = ?",
            (course_id, date)
        )
        result = self.cursor.fetchone()
        return result[0] if result else None

    def mark_student_absent(self, student_id, lecture_id):
        """Mark a student as absent for a lecture"""
        # Check if record already exists
        self.cursor.execute(
            "SELECT id FROM absences WHERE student_id = ? AND lecture_id = ?",
            (student_id, lecture_id)
        )
        if not self.cursor.fetchone():
            self.cursor.execute(
                "INSERT INTO absences (student_id, lecture_id) VALUES (?, ?)",
                (student_id, lecture_id)
            )
            self.conn.commit()
            return True
        return False

    def remove_student_absence(self, student_id, lecture_id):
        """Remove a student's absence for a lecture"""
        self.cursor.execute(
            "DELETE FROM absences WHERE student_id = ? AND lecture_id = ?",
            (student_id, lecture_id)
        )
        self.conn.commit()
        return self.cursor.rowcount > 0

    def get_student_absences(self, student_id, course_id=None):
        """Get all absences for a student, optionally filtered by course"""
        if course_id:
            self.cursor.execute(
                """
                SELECT l.id, l.date, c.code, c.name, c.section
                FROM absences a
                JOIN lectures l ON a.lecture_id = l.id
                JOIN courses c ON l.course_id = c.id
                WHERE a.student_id = ? AND c.id = ?
                ORDER BY l.date DESC
                """,
                (student_id, course_id)
            )
        else:
            self.cursor.execute(
                """
                SELECT l.id, l.date, c.code, c.name, c.section
                FROM absences a
                JOIN lectures l ON a.lecture_id = l.id
                JOIN courses c ON l.course_id = c.id
                WHERE a.student_id = ?
                ORDER BY l.date DESC
                """,
                (student_id,)
            )
        return self.cursor.fetchall()

    def get_course_absences(self, course_id):
        """Get all absences for a course"""
        self.cursor.execute(
            """
            SELECT a.student_id, u.name, l.date
            FROM absences a
            JOIN lectures l ON a.lecture_id = l.id
            JOIN users u ON a.student_id = u.id
            WHERE l.course_id = ?
            ORDER BY l.date DESC, u.name
            """,
            (course_id,)
        )
        return self.cursor.fetchall()

    def get_student_attendance_stats_with_absences(self, student_id, course_id=None):
        """Get attendance statistics including absence percentage for a student"""
        # Get total number of lectures
        if course_id:
            self.cursor.execute(
                "SELECT COUNT(*) FROM lectures WHERE course_id = ?",
                (course_id,)
            )
            total_lectures = self.cursor.fetchone()[0]
            
            self.cursor.execute(
                """
                SELECT COUNT(*) FROM absences a
                JOIN lectures l ON a.lecture_id = l.id
                WHERE a.student_id = ? AND l.course_id = ?
                """,
                (student_id, course_id)
            )
        else:
            # Get all courses this student is enrolled in
            self.cursor.execute(
                "SELECT course_id FROM enrollments WHERE student_id = ?",
                (student_id,)
            )
            enrolled_courses = [row[0] for row in self.cursor.fetchall()]
            
            if not enrolled_courses:
                return {
                    'total_lectures': 0,
                    'absence_count': 0,
                    'absence_percentage': 0,
                    'attendance_percentage': 100.0,
                    'absence_dates': []
                }
            
            # Get total lectures for all enrolled courses
            placeholders = ','.join(['?'] * len(enrolled_courses))
            self.cursor.execute(
                f"SELECT COUNT(*) FROM lectures WHERE course_id IN ({placeholders})",
                enrolled_courses
            )
            total_lectures = self.cursor.fetchone()[0]
            
            # Get absences for all enrolled courses
            self.cursor.execute(
                f"""
                SELECT COUNT(*) FROM absences a
                JOIN lectures l ON a.lecture_id = l.id
                WHERE a.student_id = ? AND l.course_id IN ({placeholders})
                """,
                [student_id] + enrolled_courses
            )
        
        absence_count = self.cursor.fetchone()[0]
        
        # Get absence dates
        if course_id:
            self.cursor.execute(
                """
                SELECT l.date, c.code, c.section
                FROM absences a
                JOIN lectures l ON a.lecture_id = l.id
                JOIN courses c ON l.course_id = c.id
                WHERE a.student_id = ? AND l.course_id = ?
                ORDER BY l.date DESC
                """,
                (student_id, course_id)
            )
        else:
            # Get all courses this student is enrolled in
            self.cursor.execute(
                "SELECT course_id FROM enrollments WHERE student_id = ?",
                (student_id,)
            )
            enrolled_courses = [row[0] for row in self.cursor.fetchall()]
            
            if not enrolled_courses:
                return {
                    'total_lectures': 0,
                    'absence_count': 0,
                    'absence_percentage': 0,
                    'attendance_percentage': 100.0,
                    'absence_dates': []
                }
            
            # Get absence dates for all enrolled courses
            placeholders = ','.join(['?'] * len(enrolled_courses))
            self.cursor.execute(
                f"""
                SELECT l.date, c.code, c.section
                FROM absences a
                JOIN lectures l ON a.lecture_id = l.id
                JOIN courses c ON l.course_id = c.id
                WHERE a.student_id = ? AND l.course_id IN ({placeholders})
                ORDER BY l.date DESC
                """,
                [student_id] + enrolled_courses
            )
        
        absence_records = self.cursor.fetchall()
        absence_dates = [f"{date} ({code}-{section})" for date, code, section in absence_records]
        
        # Calculate percentages
        if total_lectures > 0:
            absence_percentage = (absence_count / total_lectures) * 100
            attendance_percentage = 100 - absence_percentage
        else:
            absence_percentage = 0
            attendance_percentage = 100
        
        return {
            'total_lectures': total_lectures,
            'absence_count': absence_count,
            'absence_percentage': absence_percentage,
            'attendance_percentage': attendance_percentage,
            'absence_dates': absence_dates
        }

    def get_course_attendance_summary(self, course_id):
        """Get attendance summary for all students in a course"""
        # Get all students enrolled in this course
        self.cursor.execute(
            """
            SELECT e.student_id, u.name
            FROM enrollments e
            JOIN users u ON e.student_id = u.id
            WHERE e.course_id = ?
            """,
            (course_id,)
        )
        students = self.cursor.fetchall()

        # Get total number of lectures for this course
        self.cursor.execute(
            "SELECT COUNT(*) FROM lectures WHERE course_id = ?",
            (course_id,)
        )
        total_lectures = self.cursor.fetchone()[0]

        if total_lectures == 0:
            return {
                'good_count': len(students),
                'warning_count': 0,
                'risk_count': 0,
                'denied_count': 0,
                'student_stats': []
            }

        good_count = 0
        warning_count = 0
        risk_count = 0
        denied_count = 0

        student_stats = []

        for student_id, student_name in students:
            # Get absences for this student
            self.cursor.execute(
                """
                SELECT COUNT(*) FROM absences a
                JOIN lectures l ON a.lecture_id = l.id
                WHERE a.student_id = ? AND l.course_id = ?
                """,
                (student_id, course_id)
            )
            absence_count = self.cursor.fetchone()[0]

            # Get absence dates
            self.cursor.execute(
                """
                SELECT l.date
                FROM absences a
                JOIN lectures l ON a.lecture_id = l.id
                WHERE a.student_id = ? AND l.course_id = ?
                ORDER BY l.date DESC
                """,
                (student_id, course_id)
            )
            absence_dates = [row[0] for row in self.cursor.fetchall()]

            # Calculate attendance percentage
            attendance_percentage = 100.0 * (total_lectures - absence_count) / total_lectures

            # Add to appropriate category
            if attendance_percentage >= 90:
                good_count += 1
            elif attendance_percentage >= 85:
                warning_count += 1
            elif attendance_percentage >= 80:
                risk_count += 1
            else:
                denied_count += 1

            # Add to student stats
            student_stats.append({
                'student_id': student_id,
                'student_name': student_name,
                'percentage': attendance_percentage,
                'absence_count': absence_count,
                'total_lectures': total_lectures,
                'absence_dates': absence_dates,
                'max_absence_percentage': 20.0
            })

        return {
            'good_count': good_count,
            'warning_count': warning_count,
            'risk_count': risk_count,
            'denied_count': denied_count,
            'student_stats': student_stats,
            'total_lectures': total_lectures
        }

    def close(self):
        """Close the database connection with proper cleanup"""
        try:
            if hasattr(self, 'conn') and self.conn:
                # Commit any pending changes
                self.conn.commit()
                # Close the connection
                self.conn.close()
            return True
        except Exception as e:
            print(f"Error closing database: {e}")
            return False
