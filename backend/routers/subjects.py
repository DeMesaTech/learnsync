from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from models import AnnouncementCreate, AnnouncementResponse, SubjectKPIsResponse
import psycopg2
import json 
import os
from psycopg2.extras import RealDictCursor

#from models import 
from db import get_db_connection

subject_router = APIRouter(prefix="/api/subjects", tags=["subjects"])

# ===========================================================
# Teacher Dashboard Endpoint
@subject_router.get("/subject/{class_id}/kpis", response_model=SubjectKPIsResponse)
async def get_teacher_dashboard(class_id: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # KPIs
        #2. Count enrolled students in in a subjects
        cur.execute(
            '''SELECT COUNT(e.enrollment_id) AS student_count
            FROM class c JOIN enrollment e ON e.class_id = c.class_id
            WHERE c.class_id = %s''',
            (class_id,)
        )
        student_count = cur.fetchone()['student_count'] or 0
        #3. Count Activity Submissions in all subjects
        cur.execute(
            '''SELECT COUNT(a.activity_id) AS activity_count
            FROM class c JOIN activity a ON a.class_id = c.class_id
            WHERE c.class_id = %s''',
            (class_id,)
        )
        activity_count = cur.fetchone()['activity_count'] or 0
        #4. Count Quizzes created
        cur.execute(
            '''SELECT COUNT(q.quiz_id) AS quiz_count
            FROM class c JOIN quiz q ON q.class_id = c.class_id
            WHERE c.class_id = %s''',
            (class_id,)
        )
        quiz_count = cur.fetchone()['quiz_count'] or 0
        #4. Count modules created
        cur.execute(
            '''SELECT COUNT(m.module_id) AS module_count
            FROM class c JOIN module m ON m.class_id = c.class_id
            WHERE c.class_id = %s''',
            (class_id,)
        )
        module_count = cur.fetchone()['module_count'] or 0

        print(f"KPIs for class_id={class_id}: \nstudents={student_count}, \nmodules={module_count}, \nquizzes={quiz_count}, \nactivities={activity_count}")   
        return SubjectKPIsResponse(
            class_id=class_id,  # Use the provided class_id
            total_students=student_count,
            total_modules=module_count,
            total_quizzes=quiz_count,
            total_activities=activity_count
        )
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# ===========================================================
# Enroll students into a specific class
@subject_router.post("/{class_id}/enroll")
async def enroll_students(class_id: str, payload: dict = Body(...)):
    """Enroll a list of student IDs into the given class_id.

    Expects JSON: { "student_ids": [123, 456, ...] }
    """
    student_ids = payload.get('student_ids')
    if not isinstance(student_ids, list):
        raise HTTPException(status_code=400, detail="student_ids must be a list of integers")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        enrolled = 0
        for sid in student_ids:
            try:
                sid_int = int(sid)
            except Exception:
                continue

            # ensure student record exists (insert if missing)
            cur.execute('''INSERT INTO student (student_id) VALUES (%s) ON CONFLICT (student_id) DO NOTHING''', (sid_int,))

            # check existing enrollment
            cur.execute('SELECT 1 FROM enrollment WHERE student_id = %s AND class_id = %s', (sid_int, class_id))
            if not cur.fetchone():
                cur.execute('INSERT INTO enrollment (student_id, class_id) VALUES (%s, %s)', (sid_int, class_id))
                enrolled += 1

        conn.commit()
        return {"enrolled": enrolled}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# ===========================================================
# Upload Module into a specific class
@subject_router.post("/{class_id}/up_module")
async def upload_module(
    class_id: str,
    title: str = Form(...),
    summary: str = Form(""),
    sections: str = Form(...),  # JSON string from frontend
    file: UploadFile = File(...)
):
    """
    Upload Module for the class
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Convert sections JSON string back to Python list
        sections_list = json.loads(sections)

        # Save file
        upload_dir = "uploads/modules"
        os.makedirs(upload_dir, exist_ok=True)

        file_location = f"{upload_dir}/{file.filename}"

        print(
            f"Received title: {title}, "
            f"path: {file_location}, "
            f"summary: {summary}, "
            f"class_id: {class_id}"
        )
        print(f"Received sections: {sections_list}")

        with open(file_location, "wb") as buffer:
            buffer.write(await file.read())

        # Get teacher assigned to this class
        cursor.execute(
            """
            SELECT employee_id
            FROM class
            WHERE class_id = %s
            """,
            (class_id,)
        )

        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Class not found"
            )

        employee_id = row[0]

        print(
            f"Found employee_id={employee_id} "
            f"for class_id={class_id}"
        )

        # Insert module and immediately get its module_id
        cursor.execute(
            """
            INSERT INTO module (
                employee_id,
                title,
                file_path,
                summary,
                class_id
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING module_id
            """,
            (
                employee_id,
                title,
                file_location,
                summary,
                class_id
            )
        )

        module_id = cursor.fetchone()[0]

        print(f"Created module_id={module_id}")

        # Insert module-section mappings
        for section_code in sections_list:

            cursor.execute(
                """
                SELECT section_id
                FROM section
                WHERE section = %s
                """,
                (section_code,)
            )

            row = cursor.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Section {section_code} not found"
                )

            section_id = row[0]

            cursor.execute(
                """
                INSERT INTO module_sections (
                    module_id,
                    section_id
                )
                VALUES (%s, %s)
                """,
                (module_id, section_id)
            )

            print(
                f"Linked module_id={module_id} "
                f"to section_id={section_id}"
            )
        conn.commit()

        return {
            "message": "Module uploaded successfully",
            "module_id": module_id,
            "employee_id": employee_id,
            "class_id": class_id,
            "file_path": file_location,
            "summary": summary,
            "sections": sections_list
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        cursor.close()
        conn.close()

# ===========================================================
# Upload Activity        
@subject_router.post("/{class_id}/up_activity")
async def upload_activity(
    class_id: str,
    sections: str = Form(...),  # JSON string from frontend
    title: str = Form(...),
    instruction: str = Form(""),
    deadline: str = Form(""),
    points: int = Form(0),
    file: Optional[UploadFile] = File(None)
):
    """
    Upload Activity for the class
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Convert sections JSON string back to Python list
        sections_list = json.loads(sections)

        file_location = None

        if file and file.filename:
            upload_dir = "uploads/activities"
            os.makedirs(upload_dir, exist_ok=True)

            file_location = f"{upload_dir}/{file.filename}"

            with open(file_location, "wb") as buffer:
                buffer.write(await file.read())

        print(
            f"Received title: {title}, "
            f"path: {file_location}, "
            f"instruction: {instruction}, "
            f"deadline: {deadline}, "
            f"points: {points}, "
            f"class_id: {class_id}"
            f"sections: {sections_list}"
        )

        # Get teacher assigned to this class
        cursor.execute(
            """
            SELECT employee_id
            FROM class
            WHERE class_id = %s
            """,
            (class_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Class not found"
            )
        employee_id = row[0]

        print(
            f"Found employee_id={employee_id} "
            f"for class_id={class_id}"
            f"Created ={employee_id, title, file_location, instruction, deadline, points}"

        )
        # Insert activity and immediately get its activity_id
        cursor.execute(
            """
            INSERT INTO activity (
                class_id,
                title,
                description,
                due_date,
                employee_id,
                file_path,
                points
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING activity_id
            """,
            (
                class_id,
                title,
                instruction,
                deadline,
                employee_id,
                file_location,
                points
            )
        )
        activity_id = cursor.fetchone()[0]
        print(f"Created activity_id={activity_id}")
        # Insert module-section mappings
        for section_code in sections_list:

            cursor.execute(
                """
                SELECT section_id
                FROM section
                WHERE section = %s
                """,
                (section_code,)
            )

            row = cursor.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Section {section_code} not found"
                )

            section_id = row[0]
            print(f"sections for activity={section_id}")

            cursor.execute(
                """
                INSERT INTO activity_sections (
                    activity_id,
                    section_id
                )
                VALUES (%s, %s)
                """,
                (activity_id, section_id)
            )

            print(
                f"Linked module_id={activity_id} "
                f"to section_id={section_id}"
            )
        conn.commit()
        return {
            "message": "Activity uploaded successfully",
            "activity_id": activity_id,
            "employee_id": employee_id,
            "class_id": class_id,
            "file_path": file_location,
            "instruction": instruction,
            "deadline": deadline,
            "points": points,
            "sections": sections_list
        }
    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    finally:
        cursor.close()
        conn.close()

# ===========================================================
# Post Announcement
@subject_router.post("/{class_id}/announcement", response_model=AnnouncementResponse)
async def post_Announcement(class_id: int, request: AnnouncementCreate):
    """
    Post Announcements
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Convert sections JSON string back to Python list
        sections_list = request.sections

        # Get teacher assigned to this class
        cursor.execute(
            """
            SELECT employee_id
            FROM class
            WHERE class_id = %s
            """,
            (class_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail="Class not found"
            )
        employee_id = row[0]
        # Verify
        print(f"Employee ID= {employee_id}")

        cursor.execute(
            """
            INSERT INTO announcement (
                class_id, employee_id, title, message
                )
            VALUES (%s, %s, %s, %s)
            RETURNING announcement_id
            """,
            (class_id, employee_id, request.title, request.message)
        )
        announcement_id = cursor.fetchone()[0]
        print(f"announcement id: {announcement_id}")

        # Insert module-section mappings
        for section_code in sections_list:

            cursor.execute(
                """
                SELECT section_id
                FROM section
                WHERE section = %s
                """,
                (section_code,)
            )

            row = cursor.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Section {section_code} not found"
                )

            section_id = row[0]
            print(f"sections for activity={section_id}")

            cursor.execute(
                """
                INSERT INTO announcement_section (
                    announcement_id,
                    section_id
                )
                VALUES (%s, %s)
                """,
                (announcement_id, section_id)
            )

        conn.commit()
        
        return {
            "announcement_id": announcement_id,
            "title": request.title,
            "message": request.message,
            "status": "Published",
            "sections": request.sections 
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    finally:
        cursor.close()
        conn.close()

# ===========================================================
# LOAD Announcements
@subject_router.get("/{class_id}/announcement")
async def load_Announcements(class_id: int):
    """Load announcements for a specific class."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            '''SELECT
                a.announcement_id,
                a.title,
                a.message,
                a.status,
                a.publish_date,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT s.section), NULL) AS sections
            FROM announcement a
            JOIN teacher t
                ON a.employee_id = t.employee_id
            LEFT JOIN announcement_section ans
                ON a.announcement_id = ans.announcement_id
            LEFT JOIN section s
                ON ans.section_id = s.section_id
            WHERE a.class_id = %s
            GROUP BY
                a.announcement_id
            ORDER BY a.publish_date DESC;''',
            (class_id,)
        )

        announcement_data = cur.fetchall()
        print(f"announcements:\n{announcement_data}")

        return announcement_data
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# ===========================================================
# LOAD modules
@subject_router.get("/{class_id}/load_modules")
async def load_Modules(class_id: int):
    """Load modules for a specific class."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            '''SELECT
                m.module_id,
                m.title,
                m.file_path,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT s.section), NULL) AS sections
            FROM module m
            JOIN teacher t
                ON m.employee_id = t.employee_id
            LEFT JOIN module_sections ms
                ON m.module_id = ms.module_id
            LEFT JOIN section s
                ON ms.section_id = s.section_id
            WHERE m.class_id = %s
            GROUP BY
                m.module_id
            ORDER BY m.upload_date DESC;''',
            (class_id,)
        )

        module_data = cur.fetchall()
        print(f"Modules:\n{module_data}")

        return module_data
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()
