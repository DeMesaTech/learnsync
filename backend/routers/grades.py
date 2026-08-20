"""Class grading records used by the teacher grading sheet."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from psycopg2.extras import RealDictCursor

from db import get_db_connection


grades_router = APIRouter(prefix="/api/grades", tags=["grades"])


@grades_router.get("/class/{class_id}")
async def get_class_grading_sheet(
    class_id: int,
    grading_period: str = Query("Midterm", pattern="^(Midterm|Finals)$"),
    section: Optional[str] = Query(None),
):
    """Return the records needed by the grading sheet for one class."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            SELECT c.class_id, c.class_code, c.subject,
                   COALESCE(gp.attendance_weight, 0) AS attendance_weight,
                   COALESCE(gp.quizzes_weight, 0) AS quizzes_weight,
                   COALESCE(gp.recit_weight, 0) AS activities_weight,
                   COALESCE(gp.exam_weight, 0) AS exam_weight,
                   COALESCE(
                       (SELECT ARRAY_AGG(s.section ORDER BY s.section)
                        FROM section s WHERE s.class_id = c.class_id),
                       ARRAY[]::varchar[]
                   ) AS sections
            FROM class c
            LEFT JOIN grading_policy gp ON gp.class_id = c.class_id
            WHERE c.class_id = %s
            """,
            (class_id,),
        )
        class_row = cur.fetchone()
        if not class_row:
            raise HTTPException(status_code=404, detail="Class not found")

        cur.execute(
            """
            SELECT st.student_id, COALESCE(acc.name, st.student_id::text) AS name
            FROM enrollment e
            JOIN student st ON st.student_id = e.student_id
                        JOIN section sec ON sec.section_id = e.section_id
            LEFT JOIN account acc ON acc.user_id = st.user_id
                        WHERE e.class_id = %s
                            AND (%s IS NULL OR sec.section = %s)
            ORDER BY name
            """,
                        (class_id, section, section),
        )
        students = cur.fetchall()

        cur.execute(
            """
            SELECT attendance_id, student_id, is_present, score,
                   date_created::date AS record_date
            FROM attendance
              WHERE class_id = %s AND grading_period = %s
            ORDER BY record_date, attendance_id
            """,
              (class_id, grading_period),
        )
        attendance = cur.fetchall()

        cur.execute(
            """
            SELECT q.quiz_id, q.title, qs.student_id, qs.total_score,
                   qs.date_taken
            FROM quiz q
              JOIN quiz_score qs ON qs.quiz_id = q.quiz_id
                            AND qs.grading_period = %s
            WHERE q.class_id = %s
            ORDER BY q.date_created NULLS LAST, q.quiz_id, qs.student_id
            """,
              (grading_period, class_id),
        )
        quizzes = cur.fetchall()

        cur.execute(
            """
                 SELECT a.activity_id, a.title, a.points, s.student_id,
                   s.score, s.submission_date
            FROM activity a
            LEFT JOIN (
                SELECT DISTINCT ON (activity_id, student_id)
                       activity_id, student_id, score, submission_date
                FROM act_submission
                WHERE grading_period = %s
                ORDER BY activity_id, student_id, submission_date DESC NULLS LAST,
                         act_submission_id DESC
            ) s ON s.activity_id = a.activity_id
            WHERE a.class_id = %s
                            AND a.grading_period = %s
            ORDER BY a.due_date NULLS LAST, a.activity_id, s.student_id
            """,
                        (grading_period, class_id, grading_period),
        )
        activities = cur.fetchall()

        return {
            "class": dict(class_row),
            "students": [dict(row) for row in students],
            "attendance": [dict(row) for row in attendance],
            "quizzes": [dict(row) for row in quizzes],
            "activities": [dict(row) for row in activities],
        }
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        cur.close()
        conn.close()
