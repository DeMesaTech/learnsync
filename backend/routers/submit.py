from fastapi import APIRouter, HTTPException
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
