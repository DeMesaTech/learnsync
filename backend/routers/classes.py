"""Class management endpoints"""
from fastapi import APIRouter, HTTPException, Body
from httpx import request
import psycopg2
from psycopg2.extras import RealDictCursor

from models import CreateClassRequest, ClassResponse, StudentDashboardResponse, TeacherDashboardResponse
from db import get_db_connection

classes_router = APIRouter(prefix="/api/classes", tags=["classes"])

# ===========================================================
# Create a new class for a teacher
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
               JOIN "user" u ON t.user_id = u.user_id
               WHERE u.user_id = %s AND u.role = %s''',
            (request.teacher_id, 'teacher')
        )
        teacher = cur.fetchone()
        
        if not teacher:
            raise HTTPException(status_code=400, detail="Teacher not found")
        
        teacher_name = teacher['name']
        teacher_employee_id = teacher['employee_id']

        # The frontend already combines year + section before sending JSON, like:
        # { "section_1": "2A", "section_2": "2B", "section_3": "2D" }
        section_values = [value.strip().upper() for value in request.sections.values() if value and value.strip()]
        if not section_values:
            raise HTTPException(status_code=400, detail="At least one section is required.")

        duplicate_sections = {section for section in section_values if section_values.count(section) > 1}
        if duplicate_sections:
            raise HTTPException(status_code=400, detail="Section names must be unique.")

        section_ids = []
        
        for section_value in section_values:
            cur.execute(
                '''INSERT INTO class (class_code, employee_id, subject)
                    VALUES (%s, %s, %s)
                    RETURNING class_code, class_id''',
                (request.class_code, teacher_employee_id, request.subject)
            )
            class_id = cur.fetchone()['class_id']

            cur.execute(
                '''INSERT INTO section (employee_id, section, class_id)
                   VALUES (%s, %s, %s)
                   RETURNING section_id''',
                (teacher_employee_id, section_value, class_id)
            )
            section_id = cur.fetchone()['section_id']
            section_ids.append(section_id)

#

            cur.execute("""
            INSERT INTO grading_policy (class_id, attendance_weight, recit_weight, quizzes_weight, exam_weight)
            VALUES (%s, %s, %s, %s, %s)
            """, (class_id, request.attendance, request.activities, request.quizzes, request.exam))

        conn.commit()
        
        return ClassResponse(
            class_id=class_id,
            class_code=request.class_code,
            subject=request.subject,
            section_count=len(section_ids),
            attendance_weight=request.attendance,
            quizzes_weight=request.quizzes,
            activities_weight=request.activities,
            exam_weight=request.exam,
            teacher_id=request.teacher_id,
            teacher_name=teacher_name
        )
        
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# ===========================================================

# Get details of a specific class
@classes_router.get("/{class_id}")
async def get_class_details(class_id: str):
    """Get details of a specific class"""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            '''SELECT c.class_id,
                      c.class_code,
                      c.subject,
                      s.section,
                      gp.attendance_weight,
                      gp.quizzes_weight,
                      gp.recit_weight AS activities_weight,
                      gp.exam_weight,
                      t.employee_id AS teacher_id,
                      u.name as teacher_name
               FROM class c
               JOIN section s ON s.class_id = c.class_id
               JOIN teacher t ON c.employee_id = t.employee_id
               JOIN "user" u ON t.user_id = u.user_id
               LEFT JOIN grading_policy gp ON gp.class_id = c.class_id
               WHERE c.class_id = %s''',
            (class_id,)
        )

        class_data = cur.fetchone()
        if not class_data:
            raise HTTPException(status_code=404, detail="Class not found")

        return class_data
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# ===========================================================

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
            '''SELECT c.class_id,
                      c.class_code,
                      c.subject,
                      s.section,
                      COALESCE((SELECT COUNT(*) FROM enrollment e WHERE e.class_id = c.class_id), 0) AS student_count,
                      COALESCE((SELECT COUNT(*) FROM module m WHERE m.employee_id = c.employee_id), 0) AS module_count,
                      COALESCE((SELECT COUNT(*) FROM activity a WHERE a.class_id = c.class_id), 0) AS activity_count,
                      COALESCE((SELECT COUNT(*) FROM quiz q WHERE q.class_id = c.class_id), 0) AS quiz_count
               FROM class c
               JOIN section s ON s.class_id = c.class_id
               WHERE c.employee_id = %s
               ORDER BY c.subject, s.section''',
            (teacher_id,)
        )
        
        classes = cur.fetchall()

        return {"classes": classes or []}
        
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# ===========================================================
# Teacher Dashboard Endpoint
@classes_router.get("/teacher/{teacher_id}/dashboard")
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
        #4. Count modules created
        cur.execute(
            '''SELECT COUNT(m.module_id) AS module_count
            FROM class c JOIN module m ON m.employee_id = c.employee_id
            WHERE c.employee_id = %s''',
            (teacher_id,)
        )
        module_count = cur.fetchone()['module_count'] or 0

        return TeacherDashboardResponse(
            teacher_id=teacher_id,
            classes_count=classes_count,
            student_count=student_count,
            submission_count=submission_count,
            quiz_count=quiz_count,
            module_count=module_count,
            activity_count=submission_count
        )
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# ===========================================================
# Student Dashboard Endpoint
@classes_router.get("/student/{student_id}/dashboard")
async def get_student_dashboard(student_id: int):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # KPIs
        #1. Verify student exists
        cur.execute(
            '''SELECT s.student_id, u.name
               FROM student s
               JOIN "user" u ON s.user_id = u.user_id
               WHERE s.student_id = %s AND u.role = %s''',
            (student_id, 'student')
        )
        student = cur.fetchone()
        if not student:
            raise HTTPException(status_code=400, detail="Student not found")
        
        #2. Count existing classes for this student
        cur.execute(
            '''SELECT COUNT(*) AS Enrolled_classes
                FROM enrollment
                WHERE student_id =  %s''',
            (student_id,)
        )
        enrolled_classes = cur.fetchone()['Enrolled_classes'] or 0
        
        #3. Count modules in all subjects
        cur.execute(
            '''SELECT COUNT(m.module_id) AS total_modules
                FROM enrollment e
                JOIN module m
                ON e.class_id = m.class_id
                WHERE e.student_id = %s''',
            (student_id,)
        )
        module_count = cur.fetchone()['total_modules'] or 0
        #4. Pending works (activities and quizzes not yet submitted)
        cur.execute(
            '''SELECT
                (
                    -- Pending Activities
                    SELECT COUNT(*)
                    FROM enrollment e
                    JOIN activity a
                        ON e.class_id = a.class_id
                    LEFT JOIN act_submission s
                        ON s.activity_id = a.activity_id
                    AND s.student_id = e.student_id
                    WHERE e.student_id = %s
                    AND s.act_submission_id IS NULL
                )
                +
                (
                    -- Pending Quizzes
                    SELECT COUNT(*)
                    FROM enrollment e
                    JOIN quiz q
                        ON e.class_id = q.class_id
                    LEFT JOIN quiz_score qs
                        ON qs.quiz_id = q.quiz_id
                    AND qs.student_id = e.student_id
                    WHERE e.student_id = %s
                    AND qs.quiz_score_id IS NULL
                ) AS pending_works''',
            (student_id, student_id)
        )
        pending_works = cur.fetchone()['pending_works'] or 0
    #4. Count completed works (activities and quizzes submitted)    
        cur.execute(
            '''SELECT
                (
                    SELECT COUNT(*)
                    FROM act_submission
                    WHERE student_id = %s
                )
                +
                (
                    SELECT COUNT(*)
                    FROM quiz_score
                    WHERE student_id = %s
                ) AS completed_works''',
            (student_id, student_id)
        )
        completed_works = cur.fetchone()['completed_works'] or 0

        print(f"Student Dashboard: {student_id}, \nEnrolled Classes: {enrolled_classes}, \nModules: {module_count}, \nPending Works: {pending_works}, \nSubmitted Work: {completed_works}")
        return StudentDashboardResponse(
            student_id=student_id,
            enrolled_classes=enrolled_classes,
            module_count=module_count, 
            pending_works=pending_works,
            submitted_work=completed_works
        )
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

