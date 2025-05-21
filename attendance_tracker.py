from datetime import datetime

class AttendanceTracker:
    """Helper class to calculate attendance statistics"""
    def __init__(self, database):
        self.database = database
        self.max_absence_percentage = 20.0  # Default threshold
    
    def get_student_attendance(self, student_id, reference_number):
        """Get attendance statistics for a student in a specific course"""
        # Get total number of lectures for this course
        self.database.cursor.execute(
            """
            SELECT COUNT(DISTINCT date) FROM attendance
            WHERE course_id = ? AND is_cancelled = 0
            """,
            (reference_number,)
        )
        total_lectures = self.database.cursor.fetchone()[0]

        if total_lectures == 0:
            # No lectures yet
            return {
                'percentage': 100.0,
                'absence_count': 0,
                'total_lectures': 0,
                'absence_dates': [],
                'max_absence_percentage': self.max_absence_percentage
            }

        # Get absence count for this student
        self.database.cursor.execute(
            """
            SELECT COUNT(*) FROM attendance
            WHERE student_id = ? AND course_id = ? AND is_cancelled = 0 
            AND status IN ('Absent', 'Unauthorized Departure')
            """,
            (student_id, reference_number)
        )
        absence_count = self.database.cursor.fetchone()[0]

        # Get all attendance records to calculate the dates
        self.database.cursor.execute(
            """
            SELECT date, status FROM attendance
            WHERE student_id = ? AND course_id = ? AND is_cancelled = 0
            AND status IN ('Absent', 'Unauthorized Departure')
            ORDER BY date DESC
            """,
            (student_id, reference_number)
        )
        absences = self.database.cursor.fetchall()
        absence_dates = [row[0] for row in absences]

        # Calculate attendance percentage (present/total)
        attendance_percentage = 100.0 * (total_lectures - absence_count) / total_lectures

        return {
            'percentage': attendance_percentage,
            'absence_count': absence_count,
            'total_lectures': total_lectures,
            'absence_dates': absence_dates,
            'max_absence_percentage': self.max_absence_percentage
        }
    
    def get_course_attendance_summary(self, reference_number):
        """Get attendance summary for all students in a course"""
        # Get all students enrolled in this course
        self.database.cursor.execute(
            """
            SELECT e.student_id, u.name
            FROM enrollments e
            JOIN users u ON e.student_id = u.id
            WHERE e.course_id = ?
            """,
            (reference_number,)
        )
        students = self.database.cursor.fetchall()

        # Get total lectures for this course (not cancelled)
        self.database.cursor.execute(
            """
            SELECT COUNT(DISTINCT date) FROM attendance
            WHERE course_id = ? AND is_cancelled = 0
            """,
            (reference_number,)
        )
        total_lectures = self.database.cursor.fetchone()[0]

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
            # Get all attendance records for this student
            self.database.cursor.execute(
                """
                SELECT date, status FROM attendance
                WHERE student_id = ? AND course_id = ? AND is_cancelled = 0
                """,
                (student_id, reference_number)
            )
            records = self.database.cursor.fetchall()
            
            # Count absences (Absent or Unauthorized Departure)
            absence_count = 0
            absence_dates = []
            
            for date, status in records:
                if status in ('Absent', 'Unauthorized Departure'):
                    absence_count += 1
                    absence_dates.append(date)
            
            # Calculate attendance percentage
            if total_lectures > 0:
                attendance_percentage = 100.0 * (total_lectures - absence_count) / total_lectures
            else:
                attendance_percentage = 100.0
            
            # Sort absence dates (most recent first)
            absence_dates.sort(reverse=True)
            
            # Determine status category
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
                'max_absence_percentage': self.max_absence_percentage
            })
        
        return {
            'good_count': good_count,
            'warning_count': warning_count,
            'risk_count': risk_count,
            'denied_count': denied_count,
            'student_stats': student_stats,
            'total_lectures': total_lectures
        }
