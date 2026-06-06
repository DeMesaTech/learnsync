"""Class management endpoints"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

from models import CreateClassRequest, ClassResponse, TeacherDashboardResponse
from db import get_db_connection

classes_router = APIRouter(prefix="/api/classes", tags=["classes"])

# 
@classes_router.post("/create", response_model=ClassResponse)
async def create_class(request: CreateClassRequest):
    """
    Create a new class for a teacher
    
    Flow:
    1. Verify teacher exists
    2. Create Sections
    3. Validate grading weights
    4. Insert class record
    5. Return class details
    """
    if round(request.attendance + request.quizzes + request.activities + request.exam, 2) != 100.0:
        raise HTTPException(status_code=400, detail="Grading weights must total 100%.")

    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify teacher exists and get their employee_id and name
        cur.execute(
            '''SELECT t.employee_id, u.name
               FROM teacher t
               JOIN "User" u ON t.user_id = u.user_id
               WHERE u.user_id = %s AND u.role = %s''',
            (request.teacher_id, 'teacher')
        )
        teacher = cur.fetchone()
        
        if not teacher:
            raise HTTPException(status_code=400, detail="Teacher not found")
        
        teacher_name = teacher['name']
        teacher_employee_id = teacher['employee_id']

        # create sections
        letters = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]  # Support up to 10 sections (1-10)
        base = str(request.year)  # e.g. "3"
        section_ids = []
        
        for i in range(request.sections):
            if i >= len(letters):
                raise HTTPException(status_code=400, detail="Maximum supported sections is 10.")

            section_name = f"{base}{letters[i]}"
            cur.execute(
                '''INSERT INTO section (employee_id, section)
                   VALUES (%s, %s)
                   RETURNING section_id''',
                (teacher_employee_id, section_name)
            )
            section_id = cur.fetchone()['section_id']
            section_ids.append(section_id)

        # Insert class records for each section and attach grading policy
        class_id = None
        for section_id in section_ids:
            cur.execute(
                '''INSERT INTO class (employee_id, section_id, subject, subj_code)
                   VALUES (%s, %s, %s, %s)
                   RETURNING class_id''',
                (teacher_employee_id, section_id, request.subject, request.subject_code)
            )
            class_id = cur.fetchone()['class_id']

            cur.execute("""
            INSERT INTO grading_policy (class_id, attendance_weight, recit_weight, quizzes_weight, exam_weight)
            VALUES (%s, %s, %s, %s, %s)
            """, (class_id, request.attendance, request.activities, request.quizzes, request.exam))


        conn.commit()
        
        return ClassResponse(
            class_id=class_id,
            subject=request.subject,
            section_count=request.sections,
            attendance_weight=request.attendance,
            quizzes_weight=request.quizzes,
            activities_weight=request.activities,
            exam_weight=request.exam,
            teacher_id=request.teacher_id,
            teacher_name=teacher_name,
            created_at=datetime.now()
        )
        
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Get all classes for a teacher
@classes_router.get("/teacher/{teacher_id}")
async def get_teacher_classes(teacher_id: int):
    """
    Get all classes for a specific teacher
    
    Returns list of classes ordered by creation date (newest first)
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(
            '''SELECT c.class_id, c.subject, s.section FROM class c
            JOIN section s ON s.section_id = c.section_id
            WHERE c.employee_id = %s'''
            ,(teacher_id,)
        )
        
        classes = cur.fetchall()
        return {"classes": classes or []}
        
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Get details of a specific class
@classes_router.get("/{class_id}")
async def get_class_details(class_id: int):
    """Get details of a specific class"""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(
            '''SELECT c.class_id, c.subject, c.section_count, c.attendance_weight,
                      c.quizzes_weight, c.activities_weight, c.exam_weight,
                      c.employee_id AS teacher_id, u.name as teacher_name,
                      c.created_at
               FROM class c
               JOIN "User" u ON c.employee_id = u.user_id
               WHERE c.class_id = %s''',
            (class_id,)
        )
        
        class_data = cur.fetchone()
        if not class_data:
            raise HTTPException(status_code=404, detail="Class not found")
        
        return ClassResponse(**class_data)
        
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Teacher Dashboard Endpoint
@classes_router.get("/teacher/{teacher_id}/dashboard", response_model=TeacherDashboardResponse)
async def get_teacher_dashboard(teacher_id: int):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # KPIs
        # 1. Count existing classes for this teacher
        cur.execute(
            '''SELECT COUNT(DISTINCT subject) AS classes_count FROM class
            WHERE employee_id = %s'''
            ,(teacher_id,)
        )
        classes_count = cur.fetchone()['classes_count'] or 0
        #2. Count enrolled students in all subjects
        cur.execute(
            '''SELECT COUNT(e.enrollment_id) AS student_count
            FROM class c JOIN enrollment e ON e.class_id = c.class_id
            WHERE c.employee_id = %s''',
            (teacher_id,)
        )
        student_count = cur.fetchone()['student_count'] or 0
        #3. Count Activity Submissions in all subjects
        cur.execute(
            '''SELECT COUNT(a.activity_id) AS submission_count
            FROM class c JOIN activity a ON a.class_id = c.class_id
            WHERE c.employee_id = %s''',
            (teacher_id,)
        )
        submission_count = cur.fetchone()['submission_count'] or 0
        #4. Count Quizzes created
        cur.execute(
            '''SELECT COUNT(q.quiz_id) AS quiz_count
            FROM class c JOIN quiz q ON q.class_id = c.class_id
            WHERE c.employee_id = %s''',
            (teacher_id,)
        )
        quiz_count = cur.fetchone()['quiz_count'] or 0

        return TeacherDashboardResponse(
            teacher_id=teacher_id,
            classes_count=classes_count,
            student_count=student_count,
            submission_count=submission_count,
            quiz_count=quiz_count,
            module_count=143,
            activity_count=69
        )
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()
