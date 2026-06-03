"""Class management endpoints"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

from models import CreateClassRequest, ClassResponse, TeacherDashboardResponse
from db import get_db_connection

classes_router = APIRouter(prefix="/api/classes", tags=["classes"])


@classes_router.post("/create", response_model=ClassResponse)
async def create_class(request: CreateClassRequest):
    """
    Create a new class for a teacher
    
    Flow:
    1. Verify teacher exists
    2. Insert class record
    3. Return class details
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Verify teacher exists and get their name
        cur.execute(
            'SELECT user_id, name FROM "User" WHERE user_id = %s AND role = %s',
            (request.teacher_id, 'teacher')
        )
        teacher = cur.fetchone()
        
        if not teacher:
            raise HTTPException(status_code=400, detail="Teacher not found")
        
        teacher_name = teacher['name']

        # Insert class (store teacher id in employee_id column)
        cur.execute(
            '''INSERT INTO class (employee_id, class_name, subject_code, schedule, room_number, semester, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING class_id''',
            (request.teacher_id, request.class_name, request.subject_code,
             request.schedule, request.room_number, request.semester, datetime.now())
        )
        class_id = cur.fetchone()['class_id']
        conn.commit()
        
        return ClassResponse(
            class_id=class_id,
            class_name=request.class_name,
            subject_code=request.subject_code,
            teacher_id=request.teacher_id,
            teacher_name=teacher_name,
            schedule=request.schedule,
            room_number=request.room_number,
            semester=request.semester,
            created_at=datetime.now()
        )
        
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()


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
            '''SELECT class_id, class_name, subject_code, schedule, room_number, semester, created_at,
                      employee_id AS teacher_id
               FROM class
               WHERE employee_id = %s
               ORDER BY created_at DESC''',
            (teacher_id,)
        )
        
        classes = cur.fetchall()
        return {"classes": classes or []}
        
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()


@classes_router.get("/{class_id}")
async def get_class_details(class_id: int):
    """Get details of a specific class"""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        cur.execute(
            '''SELECT c.class_id, c.class_name, c.subject_code, c.employee_id AS teacher_id, u.name as teacher_name,
                      c.schedule, c.room_number, c.semester, c.created_at
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

@classes_router.get("/teacher/{teacher_id}/dashboard", response_model=TeacherDashboardResponse)
async def get_teacher_dashboard(teacher_id: int):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # KPIs
        # 1. Count existing classes for this teacher
        cur.execute(
            'SELECT COUNT(*) AS classes_count FROM class WHERE employee_id = %s',
            (teacher_id,)
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
            classes_count=classes_count,
            student_count=student_count,
            submission_count=submission_count,
            quiz_count=quiz_count
        )
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()