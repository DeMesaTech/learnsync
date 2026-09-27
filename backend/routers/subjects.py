from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from models import AnnouncementCreate, AnnouncementResponse, SubjectKPIsResponse, StudentDashboardResponse
import psycopg2
import json 
import os
import uuid
from pathlib import Path
from psycopg2.extras import RealDictCursor
from module_extractor import SUPPORTED_EXTENSIONS, extract_module_text, extract_syllabus_topics

#from models import 
from db import get_db_connection

subject_router = APIRouter(prefix="/api/subjects", tags=["subjects"])


def ensure_syllabus_progress_tables(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS syllabus_topic (
                topic_id bigserial PRIMARY KEY,
                class_id bigint NOT NULL REFERENCES class(class_id) ON DELETE CASCADE,
                title varchar(255) NOT NULL,
                display_order integer NOT NULL DEFAULT 0,
                created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS student_topic_progress (
                topic_id bigint NOT NULL REFERENCES syllabus_topic(topic_id) ON DELETE CASCADE,
                student_id integer NOT NULL REFERENCES student(student_id) ON DELETE CASCADE,
                completed boolean NOT NULL DEFAULT false,
                completed_at timestamp without time zone,
                updated_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (topic_id, student_id)
            );
            CREATE TABLE IF NOT EXISTS class_syllabus (
                class_id bigint PRIMARY KEY REFERENCES class(class_id) ON DELETE CASCADE,
                file_name varchar(255) NOT NULL,
                file_path varchar(255) NOT NULL,
                uploaded_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS syllabus_topic_class_order_idx
                ON syllabus_topic (class_id, display_order, topic_id);
            """
        )
        conn.commit()
    finally:
        cur.close()


def assert_student_enrolled(cur, student_id: int, class_id: int):
    cur.execute(
        "SELECT 1 FROM enrollment WHERE student_id = %s AND class_id = %s",
        (student_id, class_id),
    )
    if not cur.fetchone():
        raise HTTPException(status_code=403, detail="Student is not enrolled in this class.")


def assert_teacher_owns_class(cur, class_id: int, teacher_id: int):
    cur.execute(
        "SELECT 1 FROM class WHERE class_id = %s AND employee_id = %s",
        (class_id, teacher_id),
    )
    if not cur.fetchone():
        raise HTTPException(status_code=403, detail="You do not own this class.")


@subject_router.get("/{class_id}/teacher/syllabus-progress")
async def get_teacher_syllabus_progress(class_id: int):
    conn = get_db_connection()
    try:
        ensure_syllabus_progress_tables(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT COUNT(*) AS total FROM enrollment WHERE class_id = %s", (class_id,))
        total_students = cur.fetchone()["total"] or 0
        cur.execute(
            """
            SELECT topic.topic_id, topic.title, topic.display_order,
                   COUNT(progress.student_id) FILTER (WHERE progress.completed) AS completed_students
            FROM syllabus_topic topic
            LEFT JOIN student_topic_progress progress ON progress.topic_id = topic.topic_id
            WHERE topic.class_id = %s
            GROUP BY topic.topic_id
            ORDER BY topic.display_order, topic.topic_id
            """,
            (class_id,),
        )
        topics = [dict(row) for row in cur.fetchall()]
        for topic in topics:
            topic["total_students"] = total_students
            topic["completion_percent"] = round(topic["completed_students"] * 100 / total_students) if total_students else 0
        cur.execute(
            "SELECT file_name, file_path, uploaded_at FROM class_syllabus WHERE class_id = %s",
            (class_id,),
        )
        syllabus = cur.fetchone()
        total_possible = len(topics) * total_students
        completed_total = sum(topic["completed_students"] for topic in topics)
        return {
            "topics": topics,
            "syllabus": dict(syllabus) if syllabus else None,
            "total_students": total_students,
            "overall_completion_percent": round(completed_total * 100 / total_possible) if total_possible else 0,
        }
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()


@subject_router.post("/{class_id}/teacher/syllabus")
async def upload_class_syllabus(
    class_id: int,
    teacher_id: int = Form(...),
    file: UploadFile = File(...),
):
    original_name = Path(file.filename or "syllabus").name
    extension = Path(original_name).suffix.lower()
    if extension not in {".docx", ".pdf"}:
        raise HTTPException(status_code=415, detail="Syllabus must be a DOCX or PDF file.")

    max_file_size = 20 * 1024 * 1024
    file_data = await file.read(max_file_size + 1)
    if len(file_data) > max_file_size:
        raise HTTPException(status_code=413, detail="Syllabus file must be 20 MB or smaller.")

    conn = get_db_connection()
    cur = None
    new_path = None
    try:
        ensure_syllabus_progress_tables(conn)
        cur = conn.cursor()
        assert_teacher_owns_class(cur, class_id, teacher_id)
        cur.execute("SELECT file_path FROM class_syllabus WHERE class_id = %s", (class_id,))
        previous = cur.fetchone()

        upload_dir = Path(__file__).resolve().parents[1] / "uploads" / "syllabus"
        upload_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}{extension}"
        stored_path = upload_dir / stored_name
        new_path = f"uploads/syllabus/{stored_name}"
        stored_path.write_bytes(file_data)
        try:
            syllabus_topics = extract_syllabus_topics(stored_path)
        except Exception as error:
            raise HTTPException(status_code=422, detail="Unable to read syllabus topics from this file.") from error

        cur.execute(
            """
            INSERT INTO class_syllabus (class_id, file_name, file_path, uploaded_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (class_id) DO UPDATE
            SET file_name = EXCLUDED.file_name,
                file_path = EXCLUDED.file_path,
                uploaded_at = CURRENT_TIMESTAMP
            """,
            (class_id, original_name[:255], new_path),
        )
        if syllabus_topics:
            cur.execute(
                "SELECT topic_id, title FROM syllabus_topic WHERE class_id = %s",
                (class_id,),
            )
            existing_topics = cur.fetchall()
            existing_by_title = {}
            for topic_id, title in existing_topics:
                existing_by_title.setdefault(title.casefold(), topic_id)

            retained_topic_ids = set()
            for display_order, title in enumerate(syllabus_topics, start=1):
                existing_id = existing_by_title.get(title.casefold())
                if existing_id:
                    retained_topic_ids.add(existing_id)
                    cur.execute(
                        "UPDATE syllabus_topic SET display_order = %s WHERE topic_id = %s",
                        (display_order, existing_id),
                    )
                else:
                    cur.execute(
                        "INSERT INTO syllabus_topic (class_id, title, display_order) VALUES (%s, %s, %s) RETURNING topic_id",
                        (class_id, title, display_order),
                    )
                    retained_topic_ids.add(cur.fetchone()[0])
            for topic_id, _ in existing_topics:
                if topic_id not in retained_topic_ids:
                    cur.execute("DELETE FROM syllabus_topic WHERE topic_id = %s", (topic_id,))
        conn.commit()

        if previous and previous[0] != new_path:
            old_file = Path(__file__).resolve().parents[1] / previous[0]
            old_file.unlink(missing_ok=True)

        return {
            "file_name": original_name[:255],
            "file_path": new_path,
            "topics_imported": len(syllabus_topics),
            "topic_warning": None if syllabus_topics else "No course outline topics were detected; existing tracked topics were kept. Use a DOCX or PDF with a course-outline table or numbered topics.",
        }
    except HTTPException:
        conn.rollback()
        if new_path:
            (Path(__file__).resolve().parents[1] / new_path).unlink(missing_ok=True)
        raise
    except Exception as e:
        conn.rollback()
        if new_path:
            (Path(__file__).resolve().parents[1] / new_path).unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Unable to upload syllabus.") from e
    finally:
        if cur:
            cur.close()
        conn.close()


@subject_router.delete("/teacher/syllabus-topics/{topic_id}")
async def delete_syllabus_topic(topic_id: int, teacher_id: int):
    conn = get_db_connection()
    try:
        ensure_syllabus_progress_tables(conn)
        cur = conn.cursor()
        cur.execute("SELECT class_id FROM syllabus_topic WHERE topic_id = %s", (topic_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Syllabus topic not found.")
        assert_teacher_owns_class(cur, row[0], teacher_id)
        cur.execute("DELETE FROM syllabus_topic WHERE topic_id = %s", (topic_id,))
        conn.commit()
        return {"deleted": True}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()


@subject_router.get("/{student_id}/{class_id}/student/syllabus-progress")
async def get_student_syllabus_progress(student_id: int, class_id: int):
    conn = get_db_connection()
    try:
        ensure_syllabus_progress_tables(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        assert_student_enrolled(cur, student_id, class_id)
        cur.execute(
            """
            SELECT topic.topic_id, topic.title, topic.display_order,
                   COALESCE(progress.completed, false) AS completed,
                   progress.completed_at
            FROM syllabus_topic topic
            LEFT JOIN student_topic_progress progress
              ON progress.topic_id = topic.topic_id AND progress.student_id = %s
            WHERE topic.class_id = %s
            ORDER BY topic.display_order, topic.topic_id
            """,
            (student_id, class_id),
        )
        topics = [dict(row) for row in cur.fetchall()]
        completed = sum(topic["completed"] for topic in topics)
        return {
            "topics": topics,
            "completed_topics": completed,
            "total_topics": len(topics),
            "completion_percent": round(completed * 100 / len(topics)) if topics else 0,
        }
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()


@subject_router.put("/{student_id}/{class_id}/student/syllabus-topics/{topic_id}")
async def set_student_topic_completion(student_id: int, class_id: int, topic_id: int, payload: dict = Body(...)):
    completed = payload.get("completed")
    if not isinstance(completed, bool):
        raise HTTPException(status_code=400, detail="completed must be a boolean.")

    conn = get_db_connection()
    try:
        ensure_syllabus_progress_tables(conn)
        cur = conn.cursor()
        assert_student_enrolled(cur, student_id, class_id)
        cur.execute(
            "SELECT 1 FROM syllabus_topic WHERE topic_id = %s AND class_id = %s",
            (topic_id, class_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Syllabus topic not found.")
        cur.execute(
            """
            INSERT INTO student_topic_progress (topic_id, student_id, completed, completed_at, updated_at)
            VALUES (%s, %s, %s, CASE WHEN %s THEN CURRENT_TIMESTAMP ELSE NULL END, CURRENT_TIMESTAMP)
            ON CONFLICT (topic_id, student_id) DO UPDATE
            SET completed = EXCLUDED.completed,
                completed_at = EXCLUDED.completed_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            (topic_id, student_id, completed, completed),
        )
        conn.commit()
        return {"topic_id": topic_id, "completed": completed}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()


@subject_router.get("/todo/student/{student_id}")
async def get_student_todo(student_id: int):
    """Return the student's enrolled activities, quizzes, and modules with progress."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            SELECT a.activity_id, a.class_id, c.subject AS class_name,
                   a.title, a.description, a.due_date AS date, a.status,
                   latest.submission_status,
                   latest.submission_date,
                   latest.score,
                   (latest.act_submission_id IS NOT NULL) AS submitted
            FROM activity a
            JOIN class c ON c.class_id = a.class_id
            JOIN enrollment e ON e.class_id = a.class_id AND e.student_id = %s
            LEFT JOIN LATERAL (
                SELECT s.act_submission_id, s.submission_status,
                       s.submission_date, s.score
                FROM act_submission s
                WHERE s.activity_id = a.activity_id AND s.student_id = e.student_id
                ORDER BY s.submission_date DESC NULLS LAST, s.act_submission_id DESC
                LIMIT 1
            ) latest ON TRUE
            WHERE NOT EXISTS (
                SELECT 1 FROM activity_sections visible
                WHERE visible.activity_id = a.activity_id
            ) OR EXISTS (
                SELECT 1 FROM activity_sections visible
                WHERE visible.activity_id = a.activity_id AND visible.section_id = e.section_id
            )
            ORDER BY a.due_date DESC NULLS LAST, a.activity_id DESC
            """,
            (student_id,)
        )
        activities = cur.fetchall()

        cur.execute(
            """
            SELECT q.quiz_id, q.class_id, c.subject AS class_name,
                   q.title, q.description, q.deadline AS date, q.status,
                   latest.total_score,
                   (latest.score_id IS NOT NULL) AS submitted
            FROM quiz q
            JOIN class c ON c.class_id = q.class_id
            JOIN enrollment e ON e.class_id = q.class_id AND e.student_id = %s
            LEFT JOIN LATERAL (
                SELECT qs.score_id, qs.total_score, qs.date_taken
                FROM quiz_score qs
                WHERE qs.quiz_id = q.quiz_id AND qs.student_id = e.student_id
                ORDER BY qs.date_taken DESC NULLS LAST, qs.score_id DESC
                LIMIT 1
            ) latest ON TRUE
            WHERE q.status = 'Published' AND (NOT EXISTS (
                SELECT 1 FROM quiz_sections visible
                WHERE visible.quiz_id = q.quiz_id
            ) OR EXISTS (
                SELECT 1 FROM quiz_sections visible
                WHERE visible.quiz_id = q.quiz_id AND visible.section_id = e.section_id
            ))
            ORDER BY q.date_created DESC NULLS LAST, q.quiz_id DESC
            """,
            (student_id,)
        )
        quizzes = cur.fetchall()

        cur.execute(
            """
            SELECT m.module_id, m.class_id, c.subject AS class_name,
                   m.title, m.summary AS description, m.upload_date AS date,
                   m.file_path
            FROM module m
            JOIN class c ON c.class_id = m.class_id
            JOIN enrollment e ON e.class_id = m.class_id AND e.student_id = %s
            WHERE NOT EXISTS (
                SELECT 1 FROM module_sections visible
                WHERE visible.module_id = m.module_id
            ) OR EXISTS (
                SELECT 1 FROM module_sections visible
                WHERE visible.module_id = m.module_id AND visible.section_id = e.section_id
            )
            ORDER BY m.upload_date DESC NULLS LAST, m.module_id DESC
            """,
            (student_id,)
        )
        modules = cur.fetchall()

        return {"activities": activities, "quizzes": quizzes, "modules": modules}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# ===========================================================
# Teacher Dashboard Endpoint
@subject_router.get("/subject/{class_id}/kpis", response_model=SubjectKPIsResponse)
async def get_teacher_dashboard(class_id: int):
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

        # get section_id for the given section code
        section_code = payload.get('section')
        cur.execute(
            'SELECT section_id FROM section WHERE class_id = %s AND section = %s',
            (class_id, section_code),
        )
        section_id = cur.fetchone()
        if not section_id:
            raise HTTPException(status_code=400, detail="Invalid section")
        section_id = section_id[0]

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
            existing = cur.fetchone()

            # Skip duplicates
            if existing:
                continue

            if not cur.fetchone():
                cur.execute('INSERT INTO enrollment (student_id, class_id, section_id) VALUES (%s, %s, %s)', (sid_int, class_id, section_id))
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

    max_file_size = 20 * 1024 * 1024
    original_name = file.filename or ""
    extension = Path(original_name).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported module format. Use PDF, DOCX, XLSX, or PPTX."
        )

    try:
        sections_list = json.loads(sections)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="sections must be valid JSON")

    if not isinstance(sections_list, list):
        raise HTTPException(status_code=400, detail="sections must be a JSON list")

    file_data = await file.read(max_file_size + 1)
    if len(file_data) > max_file_size:
        raise HTTPException(status_code=413, detail="Module file must be 20 MB or smaller")

    conn = get_db_connection()
    cursor = conn.cursor()
    file_location = None

    try:
        upload_dir = Path(__file__).resolve().parents[1] / "uploads" / "modules"
        upload_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}{extension}"
        stored_path = upload_dir / stored_name
        file_location = f"uploads/modules/{stored_name}"

        print(
            f"Received title: {title}, "
            f"path: {file_location}, "
            f"summary: {summary}, "
            f"class_id: {class_id}"
        )
        print(f"Received sections: {sections_list}")

        stored_path.write_bytes(file_data)
        extraction = extract_module_text(stored_path)

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
                class_id,
                upload_date
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING module_id
            """,
            (
                employee_id,
                title,
                file_location,
                summary,
                class_id,
                datetime.now()
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
                WHERE section = %s AND class_id = %s
                """,
                (section_code, class_id)
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

        for chunk_index, chunk in enumerate(extraction["chunks"]):
            cursor.execute(
                """
                INSERT INTO module_content (module_id, text, chunk_index)
                VALUES (%s, %s, %s)
                """,
                (module_id, chunk, chunk_index)
            )

        conn.commit()

        return {
            "message": "Module uploaded successfully",
            "module_id": module_id,
            "employee_id": employee_id,
            "class_id": class_id,
            "file_path": file_location,
            "summary": summary,
            "sections": sections_list,
            "content_extracted": extraction["content_extracted"],
            "content_chunks": len(extraction["chunks"]),
            "extraction_warning": extraction["warning"]
        }

    except HTTPException:
        conn.rollback()
        if file_location:
            Path(__file__).resolve().parents[1].joinpath(file_location).unlink(missing_ok=True)
        raise
    except Exception as e:
        conn.rollback()
        if file_location:
            Path(__file__).resolve().parents[1].joinpath(file_location).unlink(missing_ok=True)
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
                WHERE section = %s AND class_id = %s
                """,
                (section_code, class_id)
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
                class_id, employee_id, title, message, status
                )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING announcement_id
            """,
            (class_id, employee_id, request.title, request.message, request.status)
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
#DELETE Announcement
@subject_router.delete("/announcement/{announcement_id}")
async def delete_announcement(announcement_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM announcement_section WHERE announcement_id = %s", (announcement_id,))
        cursor.execute("DELETE FROM announcement WHERE announcement_id = %s RETURNING announcement_id", (announcement_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Announcement not found")
        conn.commit()
        return {
            "message": "Announcement deleted",
            "announcement_id": announcement_id
        }
    except HTTPException:
        conn.rollback()
        raise
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
# Management endpoints used by the teacher subject modal
@subject_router.put("/announcement/{announcement_id}")
async def update_announcement(announcement_id: int, request: AnnouncementCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE announcement SET title = %s, message = %s, status = %s WHERE announcement_id = %s RETURNING class_id", (request.title, request.message, request.status, announcement_id))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Announcement not found")
        cursor.execute("DELETE FROM announcement_section WHERE announcement_id = %s", (announcement_id,))
        for section_code in request.sections:
            cursor.execute("SELECT section_id FROM section WHERE section = %s AND class_id = %s", (section_code, row[0]))
            section = cursor.fetchone()
            if not section:
                raise HTTPException(status_code=404, detail=f"Section {section_code} not found")
            cursor.execute("INSERT INTO announcement_section (announcement_id, section_id) VALUES (%s, %s)", (announcement_id, section[0]))
        conn.commit()
        return {"announcement_id": announcement_id}
    except HTTPException:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

@subject_router.put("/module/{module_id}")
async def update_module(module_id: int, payload: dict = Body(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE module SET title = %s, summary = %s WHERE module_id = %s RETURNING module_id", (payload.get("title"), payload.get("summary", ""), module_id))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Module not found")
        conn.commit()
        return {"module_id": module_id}
    finally:
        cursor.close()
        conn.close()

@subject_router.delete("/module/{module_id}")
async def delete_module(module_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM module_sections WHERE module_id = %s", (module_id,))
        cursor.execute("DELETE FROM module_content WHERE module_id = %s", (module_id,))
        cursor.execute("DELETE FROM module WHERE module_id = %s RETURNING module_id", (module_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Module not found")
        conn.commit()
        return {"module_id": module_id}
    finally:
        cursor.close()
        conn.close()

@subject_router.put("/activity/{activity_id}")
async def update_activity(activity_id: int, payload: dict = Body(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE activity SET title = %s, description = %s, due_date = %s, points = %s WHERE activity_id = %s RETURNING activity_id", (payload.get("title"), payload.get("description", ""), payload.get("due_date") or None, payload.get("points", 0), activity_id))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Activity not found")
        conn.commit()
        return {"activity_id": activity_id}
    finally:
        cursor.close()
        conn.close()

@subject_router.delete("/activity/{activity_id}")
async def delete_activity(activity_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM activity_sections WHERE activity_id = %s", (activity_id,))
        cursor.execute("DELETE FROM activity WHERE activity_id = %s RETURNING activity_id", (activity_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Activity not found")
        conn.commit()
        return {"activity_id": activity_id}
    finally:
        cursor.close()
        conn.close()

# LOAD TEACHER Announcements
@subject_router.get("/{class_id}/teacher/announcement")
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
@subject_router.get("/{class_id}/teacher/load_modules")
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

# ===========================================================
# LOAD modules
@subject_router.get("/{class_id}/teacher/load_act")
async def load_Activities(class_id: int):
    """Load activities for a specific class."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            '''SELECT
                a.activity_id,
                a.title,
                a.file_path,
                a.status,
                a.due_date,
                ARRAY_REMOVE(ARRAY_AGG(DISTINCT s.section), NULL) AS sections
            FROM activity a
            JOIN teacher t
                ON a.employee_id = t.employee_id
            LEFT JOIN activity_sections acts
                ON a.activity_id = acts.activity_id
            LEFT JOIN section s
                ON acts.section_id = s.section_id
            WHERE a.class_id = %s
            GROUP BY
                a.activity_id
            ORDER BY a.publish_date DESC;''',
            (class_id,)
        )

        activity_data = cur.fetchall()
        print(f"activities:\n{activity_data}")

        return activity_data
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

"""
Overall logic

Think of each activity as moving through states.

Draft
   ↓
Published
   ↓
Accepting submissions
   ↓
Deadline reached
   ↓
Teacher grades
   ↓
Scored

Depending on the state, the summary changes.

State	What the card displays
Draft	Not published yet
Published	Due date, submitted, pending
Deadline passed	Submitted count, late submissions
Grading	"Grading in progress"
Scored	Average score, highest score, etc.
Backend logic

When the frontend requests activities, the backend can determine what summary to return.

Pseudo-logic:

for activity in activities:

    if activity.is_scored:
        show_average_score()

    elif activity.has_due_date:
        show_submission_counts()

    else:
        show_basic_information()

or even better, have the backend compute a summary object:

{
    "title": "Chapter 1 Draft",
    "status": "active",
    "summary": {
        "submitted": 18,
        "pending": 14
    }
}

Another activity might return

{
    "title": "Problem Statement Worksheet",
    "status": "scored",
    "summary": {
        "average": 91
    }
}

The frontend then simply checks the status and renders the appropriate information.
"""

# ===========================================================
# Student Dashboard Endpoint
@subject_router.get("/{class_id}/kpis", response_model=StudentDashboardResponse)
async def get_student_dashboard(class_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # KPIs
        # 1. Count enrolled students in the subject
        cur.execute(
            '''SELECT COUNT(e.enrollment_id) AS student_count
            FROM class c JOIN enrollment e ON e.class_id = c.class_id
            WHERE c.class_id = %s''',
            (class_id,)
        )
        student_count = cur.fetchone()['student_count'] or 0

        # 2. Count Activity Submissions in the subject
        cur.execute(
            '''SELECT COUNT(s.submission_id) AS submission_count
            FROM class c JOIN activity a ON a.class_id = c.class_id
            JOIN submission s ON s.activity_id = a.activity_id
            WHERE c.class_id = %s''',
            (class_id,)
        )
        submission_count = cur.fetchone()['submission_count'] or 0

        # 3. Count Quizzes taken in the subject
        cur.execute(
            '''SELECT COUNT(q.quiz_id) AS quiz_count
            FROM class c JOIN quiz q ON q.class_id = c.class_id
            WHERE c.class_id = %s''',
            (class_id,)
        )
        quiz_count = cur.fetchone()['quiz_count'] or 0
        # 4. Count modules created in the subject
        cur.execute(
            '''SELECT COUNT(m.module_id) AS module_count
            FROM class c JOIN module m ON m.class_id = c.class_id
            WHERE c.class_id = %s''',
            (class_id,)
        )
        module_count = cur.fetchone()['module_count'] or 0
        # 5. Count activities created in the subject
        cur.execute(
            '''SELECT COUNT(a.activity_id) AS activity_count
            FROM class c JOIN activity a ON a.class_id = c.class_id
            WHERE c.class_id = %s''',
            (class_id,)
        )
        activity_count = cur.fetchone()['activity_count'] or 0

        print(f"KPIs for class_id={class_id}: \nstudents={student_count}, \nsubmissions={submission_count}, \nquizzes={quiz_count}, \nmodules={module_count}, \nactivities={activity_count}")
        return StudentDashboardResponse(
            student_id=None,  # Use the provided class_id
            classes_count=1,  # Assuming this is for a single class
            submission_count=submission_count,
            quiz_count=quiz_count,
            module_count=module_count,
            activity_count=activity_count
        )
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    finally:
        cur.close()
        conn.close()

# ===========================================================
# Student Class Title Endpoint
@subject_router.get("/{class_id}/{student_id}/student")
async def get_student_announcements(class_id: str, student_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch title and section for the class
        cur.execute(
            '''SELECT
                s.section,
                c.subject
                FROM enrollment e
                JOIN section s ON e.section_id = s.section_id
                JOIN class c ON e.class_id = c.class_id
                WHERE e.student_id = %s AND e.class_id = %s''',
            (student_id, class_id)
        )
        class_data = cur.fetchone()
        print(f"Class Data:\n{class_data}")

        return class_data

    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    finally:
        cur.close()
        conn.close()

# ===========================================================
# Student Class Announcements Endpoint
@subject_router.get("/{student_id}/{class_id}/student/announcements")
async def get_student_announcements(student_id: str, class_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch announcements for the class
        cur.execute(
            '''SELECT
                a.announcement_id,
                a.title,
                a.message,
                a.status,
                a.publish_date
            FROM announcement a
            JOIN enrollment e ON e.class_id = a.class_id
            JOIN student st ON st.student_id = e.student_id
            LEFT JOIN announcement_section ans ON a.announcement_id = ans.announcement_id
            LEFT JOIN section s ON ans.section_id = s.section_id
            WHERE e.student_id = %s AND a.class_id = %s
            GROUP BY a.announcement_id, e.section_id
            ORDER BY a.publish_date DESC;''',
            (student_id, class_id)
        )

        announcements = cur.fetchall()
        print("Student Announcements:\n")
        for announcement in announcements:
            print(f"title: {announcement['title']}, \n message: {announcement['message']}, \n status: {announcement['status']}, \n publish_date: {announcement['publish_date']}")

        return announcements

    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    finally:
        cur.close()
        conn.close()

# ===========================================================
# Student Class MODULES Endpoint
@subject_router.get("/{student_id}/{class_id}/student/modules")
async def get_student_modules(student_id: str, class_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch modules for the class
        cur.execute(
            '''SELECT
                m.module_id,
                m.title,
                m.file_path,
                m.upload_date,
                m.summary
            FROM module m
            JOIN enrollment e ON e.class_id = m.class_id
            JOIN student st ON st.student_id = e.student_id
            LEFT JOIN module_sections ans ON m.module_id = ans.module_id
            LEFT JOIN section s ON ans.section_id = s.section_id
            WHERE e.student_id = %s AND m.class_id = %s
            GROUP BY m.module_id, e.section_id
            ORDER BY m.upload_date DESC;''',
            (student_id, class_id)
        )

        modules = cur.fetchall()
        print("Student Modules:\n")
        for module in modules:
            print(f"title: {module['title']}, \n file_path: {module['file_path']}, \n upload_date: {module['upload_date']}, \n summary: {module['summary']}")

        return modules

    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    finally:
        cur.close()
        conn.close()

# ===========================================================
# Student Class QUIZZES Endpoint
@subject_router.get("/{student_id}/{class_id}/student/quizzes")
async def get_student_quizzes(student_id: str, class_id: str):
    conn = get_db_connection()
    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT q.quiz_id, q.title, q.description, q.deadline, q.total_points,
                   COUNT(question.question_id) AS question_count,
                   latest.total_score,
                   (latest.score_id IS NOT NULL) AS submitted
            FROM quiz q
            JOIN enrollment e ON e.class_id = q.class_id AND e.student_id = %s
            LEFT JOIN question ON question.quiz_id = q.quiz_id
            LEFT JOIN LATERAL (
                SELECT qs.score_id, qs.total_score
                FROM quiz_score qs
                WHERE qs.quiz_id = q.quiz_id AND qs.student_id = e.student_id
                ORDER BY qs.date_taken DESC NULLS LAST, qs.score_id DESC
                LIMIT 1
            ) latest ON TRUE
            WHERE q.class_id = %s
              AND q.status = 'Published'
              AND (
                  NOT EXISTS (SELECT 1 FROM quiz_sections visible WHERE visible.quiz_id = q.quiz_id)
                  OR EXISTS (
                      SELECT 1 FROM quiz_sections visible
                      WHERE visible.quiz_id = q.quiz_id AND visible.section_id = e.section_id
                  )
              )
            GROUP BY q.quiz_id, latest.score_id, latest.total_score
            ORDER BY q.date_created DESC NULLS LAST, q.quiz_id DESC
            """,
            (student_id, class_id),
        )
        return [dict(quiz) for quiz in cur.fetchall()]
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        if cur:
            cur.close()
        conn.close()

# ===========================================================
# Student Class ACTIVITY Endpoint
@subject_router.get("/{student_id}/{class_id}/student/activities")
async def get_student_activities(student_id: str, class_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Fetch activities for the class
        cur.execute(
            '''SELECT
                a.activity_id,
                a.title,
                a.description,
                a.file_path,
                a.due_date
            FROM activity a
            JOIN enrollment e ON e.class_id = a.class_id
            JOIN student st ON st.student_id = e.student_id
            WHERE e.student_id = %s AND a.class_id = %s
            ORDER BY a.due_date DESC;''',
            # Use parameterized SQL to avoid SQL injection and properly substitute runtime values
            (student_id, class_id)
        )

        activities = cur.fetchall()

        print("Student Activities:\n")
        for activity in activities:
            print(f"title: {activity['title']}, \n description: {activity['description']}, \n file_path: {activity['file_path']}, \n due_date: {activity['due_date']}")

        return activities

    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    finally:
        cur.close()
        conn.close()
