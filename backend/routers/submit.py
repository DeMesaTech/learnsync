from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
import os
from datetime import datetime, timezone
from psycopg2.extras import RealDictCursor

from db import get_db_connection

submit_router = APIRouter(prefix="/api/submissions", tags=["submissions"])

ALLOWED_SUBMISSION_STATUSES = ["Submitted", "Late", "Returned", "Missing"]


def get_submission_status_for_activity(activity_due_date: object | None = None) -> str:
    """Return the submission status based on the activity deadline."""
    if activity_due_date is None:
        return "Submitted"

    if isinstance(activity_due_date, str):
        activity_due_date = activity_due_date.replace("Z", "+00:00")
        activity_due_date = datetime.fromisoformat(activity_due_date)

    if isinstance(activity_due_date, datetime):
        now = datetime.now(activity_due_date.tzinfo or timezone.utc)
        return "Late" if now > activity_due_date else "Submitted"

    return "Submitted"


def ensure_submission_notes_column(conn):
    """Create the st_notes column when the database schema is missing it."""
    cur = conn.cursor()
    try:
        cur.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'act_submission' AND column_name = 'st_notes'
                ) THEN
                    ALTER TABLE act_submission ADD COLUMN st_notes text;
                END IF;
            END
            $$;
            """
        )
        conn.commit()
    finally:
        cur.close()


@submit_router.get("/student/{student_id}/class/{class_id}/activity/{activity_id}")
async def get_student_activity_submission(student_id: int, class_id: int, activity_id: int):
    """Return student activity and any existing submission details."""
    conn = get_db_connection()
    try:
        ensure_submission_notes_column(conn)
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
                s.attempt_number,
                s.st_notes
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
        ensure_submission_notes_column(conn)
        upload_location = None

        # Save uploaded file if provided
        if file is not None and getattr(file, 'filename', None):
            os.makedirs("uploads/submissions", exist_ok=True)
            upload_location = f"uploads/submissions/{file.filename}"
            with open(upload_location, "wb") as buffer:
                buffer.write(await file.read())

        # prefer explicit file_path param if provided
        path_to_store = file_path or upload_location

        cur.execute(
            "SELECT due_date FROM activity WHERE activity_id = %s AND class_id = %s",
            (activity_id, class_id),
        )
        activity_row = cur.fetchone()
        due_date = activity_row[0] if activity_row else None
        submission_status = get_submission_status_for_activity(due_date)

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
                attempt_number,
                st_notes
            ) VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s)
            RETURNING act_submission_id
            """,
            (
                student_id,
                activity_id,
                path_to_store,
                submission_status,
                None,
                None,
                1,
                notes
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

# Student unsubmit activity
@submit_router.delete("/student/{student_id}/class/{class_id}/activity/{activity_id}/unsubmit")
async def unsubmit_activity(student_id: int, class_id: int, activity_id: int):
    """Allow a student to unsubmit their activity submission."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Check if the submission exists
        cur.execute(
            """
            SELECT act_submission_id FROM act_submission
            WHERE student_id = %s AND activity_id = %s
            """,
            (student_id, activity_id)
        )
        submission = cur.fetchone()

        if not submission:
            raise HTTPException(status_code=404, detail="Submission not found")

        # Delete the submission
        cur.execute(
            """
            DELETE FROM act_submission
            WHERE act_submission_id = %s
            """,
            (submission[0],)
        )

        conn.commit()
        return {"message": "Submission successfully removed."}

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
