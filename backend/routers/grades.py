"""Class grading records used by the teacher grading sheet."""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Body
from psycopg2.extras import RealDictCursor

from db import get_db_connection


grades_router = APIRouter(prefix="/api/grades", tags=["grades"])


def ensure_visibility_table(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS grade_visibility (
                class_id bigint NOT NULL,
                section varchar(50) NOT NULL,
                grading_period varchar(20) NOT NULL,
                visible boolean NOT NULL DEFAULT false,
                PRIMARY KEY (class_id, section, grading_period)
            )
            """
        )
        conn.commit()
    finally:
        cur.close()


@grades_router.get("/visibility")
async def get_grade_visibility(
    class_id: int,
    section: str = Query(...),
    grading_period: str = Query("Midterm", pattern="^(Midterm|Finals)$"),
):
    conn = get_db_connection()
    try:
        ensure_visibility_table(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """SELECT visible FROM grade_visibility
               WHERE class_id = %s AND section = %s AND grading_period = %s""",
            (class_id, section, grading_period),
        )
        row = cur.fetchone()
        return {"visible": bool(row["visible"]) if row else False}
    finally:
        cur.close()
        conn.close()


@grades_router.put("/visibility")
async def set_grade_visibility(payload: dict = Body(...)):
    class_id = payload.get("class_id")
    section = payload.get("section")
    grading_period = payload.get("grading_period", "Midterm")
    visible = payload.get("visible")
    if not isinstance(class_id, int) or not section or grading_period not in ("Midterm", "Finals") or not isinstance(visible, bool):
        raise HTTPException(status_code=400, detail="class_id, section, grading_period, and boolean visible are required")

    conn = get_db_connection()
    try:
        ensure_visibility_table(conn)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO grade_visibility (class_id, section, grading_period, visible)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (class_id, section, grading_period)
            DO UPDATE SET visible = EXCLUDED.visible
            """,
            (class_id, section, grading_period, visible),
        )
        conn.commit()
        return {"visible": visible}
    finally:
        cur.close()
        conn.close()


@grades_router.get("/class/{class_id}/summary")
async def get_class_grade_summary(
    class_id: int,
    section: str = Query(...),
    grading_period: str = Query("Midterm", pattern="^(Midterm|Finals)$"),
):
    """Return calculated component and course grades for one class section."""
    section = section.removeprefix("Section ").strip()
    conn = get_db_connection()
    try:
        ensure_visibility_table(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT c.subject, c.class_id, sec.section,
                   COALESCE(gp.attendance_weight, 0) AS attendance_weight,
                   COALESCE(gp.quizzes_weight, 0) AS quizzes_weight,
                   COALESCE(gp.recit_weight, 0) AS activities_weight,
                   COALESCE(gp.exam_weight, 0) AS exam_weight,
                   st.student_id, COALESCE(acc.name, st.student_id::text) AS student_name,
                   att.percentage AS attendance_percentage,
                   quiz.percentage AS quiz_percentage,
                   activity.percentage AS activity_percentage
            FROM enrollment e
            JOIN class c ON c.class_id = e.class_id
            JOIN student st ON st.student_id = e.student_id
            JOIN section sec ON sec.section_id = e.section_id AND sec.section = %s
            LEFT JOIN account acc ON acc.user_id = st.user_id
            LEFT JOIN grading_policy gp ON gp.class_id = c.class_id
            LEFT JOIN LATERAL (
                SELECT AVG(COALESCE(a.score, CASE WHEN a.is_present THEN 1 ELSE 0 END)) * 100 AS percentage
                FROM attendance a WHERE a.class_id = c.class_id AND a.student_id = st.student_id AND a.grading_period = %s
            ) att ON TRUE
            LEFT JOIN LATERAL (
                SELECT SUM(qs.total_score) * 100 / NULLIF(SUM(qt.total), 0) AS percentage
                FROM quiz q JOIN quiz_score qs ON qs.quiz_id = q.quiz_id AND qs.student_id = st.student_id AND qs.grading_period = %s
                LEFT JOIN LATERAL (SELECT COUNT(*) AS total FROM question WHERE question.quiz_id = q.quiz_id) qt ON TRUE
                WHERE q.class_id = c.class_id
            ) quiz ON TRUE
            LEFT JOIN LATERAL (
                SELECT SUM(latest.score) * 100 / NULLIF(SUM(a.points), 0) AS percentage
                FROM activity a
                JOIN LATERAL (
                    SELECT score FROM act_submission s
                    WHERE s.activity_id = a.activity_id AND s.student_id = st.student_id AND s.grading_period = %s
                    ORDER BY s.submission_date DESC NULLS LAST, s.act_submission_id DESC LIMIT 1
                ) latest ON TRUE
                WHERE a.class_id = c.class_id AND a.grading_period = %s
            ) activity ON TRUE
            WHERE c.class_id = %s
            ORDER BY student_name
            """,
            (section, grading_period, grading_period, grading_period, grading_period, class_id),
        )
        rows = cur.fetchall()
        cur.execute(
            """SELECT visible FROM grade_visibility WHERE class_id = %s AND section = %s AND grading_period = %s""",
            (class_id, section, grading_period),
        )
        visibility = cur.fetchone()
        visible = bool(visibility["visible"]) if visibility else False

        students = []
        for row in rows:
            weights = {
                "attendance": float(row["attendance_weight"] or 0),
                "quiz": float(row["quizzes_weight"] or 0),
                "activity": float(row["activities_weight"] or 0),
            }
            percentages = {
                "attendance": row["attendance_percentage"],
                "quiz": row["quiz_percentage"],
                "activity": row["activity_percentage"],
            }
            missing = [key for key, weight in weights.items() if weight > 0 and percentages[key] is None]
            weight_total = sum(weights.values())
            period_grade = None if missing or not weight_total else round(sum(float(percentages[key]) * weight for key, weight in weights.items()) / weight_total, 2)
            students.append({
                "student_id": row["student_id"],
                "name": row["student_name"],
                "attendance": round(float(percentages["attendance"]), 2) if percentages["attendance"] is not None else None,
                "quiz": round(float(percentages["quiz"]), 2) if percentages["quiz"] is not None else None,
                "activities": round(float(percentages["activity"]), 2) if percentages["activity"] is not None else None,
                "period_grade": period_grade,
                "course_grade": period_grade,
            })
        return {
            "class": {"class_id": class_id, "subject": rows[0]["subject"] if rows else "", "section": section},
            "weights": {"attendance": rows[0]["attendance_weight"] if rows else 0, "quizzes": rows[0]["quizzes_weight"] if rows else 0, "activities": rows[0]["activities_weight"] if rows else 0},
            "grading_period": grading_period,
            "visible": visible,
            "students": students,
        }
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        cur.close()
        conn.close()


@grades_router.get("/student/{student_id}")
async def get_student_final_grades(
    student_id: int,
    grading_period: str = Query("Finals", pattern="^(Midterm|Finals)$"),
):
    """Calculate weighted grades for every class enrolled by a student."""
    conn = get_db_connection()
    try:
        ensure_visibility_table(conn)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            WITH enrolled AS (
                SELECT e.class_id, sec.section, c.subject, acc.name AS teacher
                FROM enrollment e
                JOIN class c ON c.class_id = e.class_id
                LEFT JOIN section sec ON sec.section_id = e.section_id
                LEFT JOIN teacher t ON t.employee_id = c.employee_id
                LEFT JOIN account acc ON acc.user_id = t.user_id
                WHERE e.student_id = %s
            ),
            attendance_scores AS (
                SELECT class_id,
                       AVG(COALESCE(score, CASE WHEN is_present THEN 1 ELSE 0 END)) * 100 AS percentage
                FROM attendance
                WHERE student_id = %s AND grading_period = %s
                GROUP BY class_id
            ),
            quiz_scores AS (
                SELECT q.class_id,
                       SUM(qs.total_score) * 100 / NULLIF(SUM(question_totals.total), 0) AS percentage
                FROM quiz q
                JOIN quiz_score qs ON qs.quiz_id = q.quiz_id
                LEFT JOIN LATERAL (
                    SELECT COUNT(*) AS total
                    FROM question question_row
                    WHERE question_row.quiz_id = q.quiz_id
                ) question_totals ON TRUE
                WHERE qs.student_id = %s AND qs.grading_period = %s
                GROUP BY q.class_id
            ),
            activity_scores AS (
                SELECT a.class_id,
                       SUM(s.score) * 100 / NULLIF(SUM(a.points), 0) AS percentage
                FROM activity a
                JOIN LATERAL (
                    SELECT DISTINCT ON (student_id, activity_id) score
                    FROM act_submission
                    WHERE student_id = %s AND activity_id = a.activity_id
                      AND grading_period = %s
                    ORDER BY student_id, activity_id, submission_date DESC NULLS LAST,
                             act_submission_id DESC
                ) s ON TRUE
                WHERE a.grading_period = %s
                GROUP BY a.class_id
            ),
            exam_scores AS (
                SELECT class_id, score * 100 / NULLIF(total, 0) AS percentage
                FROM grade
                WHERE student_id = %s
                  AND LOWER(type) IN ('exam', 'final exam')
            )
            SELECT e.class_id, e.subject AS name, e.section,
                   COALESCE(e.teacher, 'Not assigned') AS teacher,
                   gp.attendance_weight, gp.quizzes_weight,
                   gp.recit_weight AS activities_weight, gp.exam_weight,
                   ats.percentage AS attendance_percentage,
                   qzs.percentage AS quiz_percentage,
                   acs.percentage AS activity_percentage,
                   exs.percentage AS exam_percentage
            FROM enrolled e
            LEFT JOIN grading_policy gp ON gp.class_id = e.class_id
            LEFT JOIN attendance_scores ats ON ats.class_id = e.class_id
            LEFT JOIN quiz_scores qzs ON qzs.class_id = e.class_id
            LEFT JOIN activity_scores acs ON acs.class_id = e.class_id
            LEFT JOIN exam_scores exs ON exs.class_id = e.class_id
            ORDER BY e.subject
            """,
            (
                student_id,
                student_id, grading_period,
                student_id, grading_period,
                student_id, grading_period, grading_period,
                student_id,
            ),
        )

        rows = cur.fetchall()
        published = set()
        if grading_period == "Finals":
            cur.execute(
                """SELECT class_id, section FROM grade_visibility
                   WHERE grading_period = %s AND visible = TRUE""",
                (grading_period,),
            )
            published = {(row["class_id"], row["section"]) for row in cur.fetchall()}

        courses = []
        for row in rows:
            weights = {
                "attendance": float(row["attendance_weight"] or 0),
                "quiz": float(row["quizzes_weight"] or 0),
                "activity": float(row["activities_weight"] or 0),
                "exam": float(row["exam_weight"] or 0),
            }
            percentages = {
                "attendance": row["attendance_percentage"],
                "quiz": row["quiz_percentage"],
                "activity": row["activity_percentage"],
                "exam": row["exam_percentage"],
            }
            missing = [
                category for category, weight in weights.items()
                if weight > 0 and percentages[category] is None
            ]
            total_weight = sum(weights.values())
            grade = None
            if total_weight and not missing:
                grade = round(sum(
                    float(percentages[category]) * weight
                    for category, weight in weights.items()
                ) / total_weight, 2)
            if grading_period == "Finals" and (row["class_id"], row["section"]) not in published:
                grade = None

            courses.append({
                "id": row["class_id"],
                "name": row["name"],
                "section": row["section"] or "-",
                "teacher": row["teacher"],
                "grade": grade,
                "remark": "Passed" if grade is not None and grade >= 75 else "Failed" if grade is not None else "Grade not available yet",
            })

        return {"courses": courses, "grading_period": grading_period}
    except HTTPException:
        raise
    except Exception as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        cur.close()
        conn.close()


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
