from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
import os
from psycopg2.extras import RealDictCursor

from db import get_db_connection

submit_router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@submit_router.get("/student/{student_id}/class/{class_id}/activity/{activity_id}")
async def get_student_activity_submission(student_id: int, class_id: int, activity_id: int):
    """Return student activity and any existing submission details."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # SQL query uses parameterized values for safety and clarity.
        # It joins activity, enrollment, and student to make sure the student is enrolled
        # in the class, and then left joins act_submission to include submission details.
        cur.execute(
            '''SELECT
                a.activity_id,
                a.title,
                a.description,
                a.due_date,
                a.file_path AS attachment,
                a.points,
                a.status,
                s.act_submission_id,
                s.file_path AS submission_file_path,
                s.submission_date,
                s.score,
                s.submission_status,
                s.feedback,
                s.attempt_number
            FROM activity a
            JOIN enrollment e ON e.class_id = a.class_id
            JOIN student st ON st.student_id = e.student_id
            LEFT JOIN act_submission s
                ON s.activity_id = a.activity_id
                AND s.student_id = st.student_id
            WHERE st.student_id = %s
                AND a.class_id = %s
                AND a.activity_id = %s
            ORDER BY s.submission_date DESC
            LIMIT 1;''',
            (student_id, class_id, activity_id)
        )

        result = cur.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Activity submission not found")

        return result

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    finally:
        cur.close()
        conn.close()


# Student submission upload
@submit_router.post("/student/{student_id}/class/{class_id}/activity/{activity_id}/submit")
async def submit_activity(student_id: int, class_id: int, activity_id: int, file: UploadFile = File(None), file_path: str = Form(None), notes: str = Form(None)):
    """Receive a student submission: file or file_path (link)."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        upload_location = None

        # Save uploaded file if provided
        if file is not None and getattr(file, 'filename', None):
            os.makedirs("uploads/submissions", exist_ok=True)
            upload_location = f"uploads/submissions/{file.filename}"
            with open(upload_location, "wb") as buffer:
                buffer.write(await file.read())

        # prefer explicit file_path param if provided
        path_to_store = file_path or upload_location

        # Insert submission record
        cur.execute(
            """
            INSERT INTO act_submission (
                student_id,
                activity_id,
                file_path,
                submission_date,
                submission_status,
                feedback,
                score,
                attempt_number
            ) VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s)
            RETURNING act_submission_id
            """,
            (
                student_id,
                activity_id,
                path_to_store,
                'Submitted',
                None,
                None,
                1
            )
        )

        submission_id = cur.fetchone()[0]
        conn.commit()

        return {"act_submission_id": submission_id, "file_path": path_to_store}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


# Teacher: list enrolled students for an activity with optional section filter
@submit_router.get("/class/{class_id}/activity/{activity_id}")
async def list_activity_submissions(class_id: int, activity_id: int, section: str = None):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        query = '''
            SELECT
                e.student_id,
                acc.name AS student_name,
                sec.section,
                latest.act_submission_id,
                latest.file_path AS submission_file_path,
                latest.submission_date,
                latest.score,
                latest.submission_status,
                latest.feedback,
                latest.attempt_number,
                CASE WHEN latest.act_submission_id IS NULL THEN FALSE ELSE TRUE END AS has_submission
            FROM enrollment e
            JOIN activity a ON a.class_id = e.class_id
            JOIN student st ON st.student_id = e.student_id
            LEFT JOIN account acc ON acc.user_id = st.user_id
            LEFT JOIN section sec ON sec.section_id = e.section_id
            LEFT JOIN (
                SELECT DISTINCT ON (student_id)
                    student_id,
                    act_submission_id,
                    file_path,
                    submission_date,
                    score,
                    submission_status,
                    feedback,
                    attempt_number
                FROM act_submission
                WHERE activity_id = %s
                ORDER BY student_id, submission_date DESC NULLS LAST, act_submission_id DESC
            ) latest ON latest.student_id = st.student_id
            WHERE a.class_id = %s
              AND a.activity_id = %s
        '''

        params = [activity_id, class_id, activity_id]
        if section:
            query += ' AND sec.section = %s'
            params.append(section)

        query += ' ORDER BY sec.section, acc.name'

        cur.execute(query, tuple(params))
        rows = cur.fetchall()

        return rows

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()


# Teacher: grade a submission
@submit_router.put("/{submission_id}/grade")
async def grade_submission(submission_id: int, payload: dict = Body(...)):
    score = payload.get('score')
    feedback = payload.get('feedback')
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            UPDATE act_submission
            SET score = %s,
                feedback = %s,
                graded_at= NOW()
            WHERE act_submission_id = %s
            RETURNING act_submission_id, student_id, activity_id, score, feedback
            """,
            (score, feedback, submission_id)
        )

        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail='Submission not found')

        conn.commit()
        return {
            'act_submission_id': row[0],
            'student_id': row[1],
            'activity_id': row[2],
            'score': row[3],
            'feedback': row[4]
    }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cur.close()
        conn.close()
