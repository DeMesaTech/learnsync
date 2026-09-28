"""Daily attendance and score-only face-to-face quizzes for assigned offerings."""
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from psycopg2.extras import RealDictCursor

from db import get_db_connection

work_router = APIRouter(prefix="/api/faculty", tags=["faculty work"])


class AttendanceMarkInput(BaseModel):
    student_id: int
    status: Literal["Present", "Absent", "Late", "Excused"]


class AttendanceSessionInput(BaseModel):
    teacher_id: int
    section_id: int
    session_date: date
    grading_period: Literal["Midterm", "Finals"]
    marks: list[AttendanceMarkInput]


class AttendanceUpdateInput(BaseModel):
    teacher_id: int
    marks: list[AttendanceMarkInput]


class OfflineQuizInput(BaseModel):
    teacher_id: int
    title: str = Field(min_length=1, max_length=255)
    quiz_date: date
    total_points: float = Field(gt=0)
    grading_period: Literal["Midterm", "Finals"]
    section_ids: list[int] = Field(min_length=1)
    content_level: Literal["course", "chapter", "subsection", "topic"] = "course"
    content_key: str | None = None


class OfflineScoreInput(BaseModel):
    student_id: int
    score: float | None = Field(default=None, ge=0)


class OfflineScoreBatch(BaseModel):
    teacher_id: int
    scores: list[OfflineScoreInput]


def _owns(cur, class_id: int, teacher_id: int):
    cur.execute("""SELECT 1 FROM class WHERE class_id=%s AND employee_id=%s
                   AND workflow_status='active'""", (class_id, teacher_id))
    if not cur.fetchone():
        raise HTTPException(status_code=403, detail="Assigned faculty member required.")


def _section(cur, class_id: int, section_id: int):
    cur.execute("SELECT 1 FROM class_section WHERE class_id=%s AND section_id=%s",
                (class_id, section_id))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Section is not assigned to this subject.")


def _roster(cur, class_id: int, section_id: int):
    cur.execute("""SELECT e.student_id,a.name FROM enrollment e
                   JOIN student st ON st.student_id=e.student_id
                   JOIN account a ON a.user_id=st.user_id
                   WHERE e.class_id=%s AND e.section_id=%s ORDER BY a.name""",
                (class_id, section_id))
    return cur.fetchall()


def _save_marks(cur, session_id: int, roster, marks):
    roster_ids = {row["student_id"] for row in roster}
    entries = {item.student_id: item.status for item in marks}
    if set(entries) != roster_ids or len(marks) != len(roster_ids):
        raise HTTPException(status_code=422, detail="Mark each currently enrolled student exactly once.")
    for student_id, status in entries.items():
        cur.execute("""INSERT INTO attendance_mark(session_id,student_id,status)
                       VALUES (%s,%s,%s) ON CONFLICT(session_id,student_id)
                       DO UPDATE SET status=EXCLUDED.status,updated_at=CURRENT_TIMESTAMP""",
                    (session_id, student_id, status))


@work_router.get("/{class_id}/attendance")
def attendance_week(class_id: int, teacher_id: int, section_id: int, week: date):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _owns(cur, class_id, teacher_id)
        _section(cur, class_id, section_id)
        monday = week - timedelta(days=week.weekday())
        roster = _roster(cur, class_id, section_id)
        cur.execute("""SELECT session_id,session_date,grading_period FROM attendance_session
                       WHERE class_id=%s AND section_id=%s AND session_date BETWEEN %s AND %s
                       ORDER BY session_date""", (class_id, section_id, monday, monday + timedelta(days=6)))
        sessions = [dict(row) for row in cur.fetchall()]
        for session in sessions:
            cur.execute("SELECT student_id,status FROM attendance_mark WHERE session_id=%s",
                        (session["session_id"],))
            session["marks"] = {row["student_id"]: row["status"] for row in cur.fetchall()}
        return {"week_start": monday, "students": roster, "sessions": sessions}
    finally:
        conn.close()


@work_router.post("/{class_id}/attendance/sessions", status_code=201)
def create_attendance_session(class_id: int, payload: AttendanceSessionInput):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _owns(cur, class_id, payload.teacher_id)
        _section(cur, class_id, payload.section_id)
        roster = _roster(cur, class_id, payload.section_id)
        if not roster:
            raise HTTPException(status_code=409, detail="The teaching section has no enrolled students.")
        cur.execute("""INSERT INTO attendance_session
                       (class_id,section_id,session_date,grading_period,created_by)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT(class_id,section_id,session_date) DO NOTHING
                       RETURNING session_id""",
                    (class_id, payload.section_id, payload.session_date,
                     payload.grading_period, payload.teacher_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=409, detail="Attendance already exists for this date.")
        _save_marks(cur, row["session_id"], roster, payload.marks)
        cur.execute("DELETE FROM grade_publication WHERE class_id=%s AND section_id=%s",
                    (class_id, payload.section_id))
        conn.commit()
        return {"session_id": row["session_id"], "saved": len(roster)}
    finally:
        conn.close()


@work_router.put("/{class_id}/attendance/sessions/{session_id}")
def update_attendance_session(class_id: int, session_id: int, payload: AttendanceUpdateInput):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _owns(cur, class_id, payload.teacher_id)
        cur.execute("SELECT section_id FROM attendance_session WHERE session_id=%s AND class_id=%s",
                    (session_id, class_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Attendance date not found.")
        roster = _roster(cur, class_id, row["section_id"])
        _save_marks(cur, session_id, roster, payload.marks)
        cur.execute("DELETE FROM grade_publication WHERE class_id=%s AND section_id=%s",
                    (class_id, row["section_id"]))
        conn.commit()
        return {"session_id": session_id, "saved": len(roster)}
    finally:
        conn.close()


def _valid_content_placement(cur, class_id: int, level: str, key: str | None):
    if level == "course":
        if key:
            raise HTTPException(status_code=422, detail="Course-wide quizzes have no content key.")
        return
    cur.execute("""SELECT content FROM syllabus_version WHERE class_id=%s AND status='approved'
                   ORDER BY version DESC LIMIT 1""", (class_id,))
    approved = cur.fetchone()
    if not approved:
        raise HTTPException(status_code=409, detail="Approve a syllabus before placing a quiz.")
    content = approved["content"]
    valid = set()
    for chapter in content.get("chapters", []):
        if level == "chapter":
            valid.add(chapter.get("key"))
        for topic in chapter.get("topics", []):
            if level == "topic":
                valid.add(topic.get("key"))
        for subsection in chapter.get("subsections", []):
            if level == "subsection":
                valid.add(subsection.get("key"))
            for topic in subsection.get("topics", []):
                if level == "topic":
                    valid.add(topic.get("key"))
    if not key or key not in valid:
        raise HTTPException(status_code=422, detail="Choose a valid approved chapter, subsection, or topic.")


@work_router.post("/{class_id}/offline-quizzes", status_code=201)
def create_offline_quiz(class_id: int, payload: OfflineQuizInput):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _owns(cur, class_id, payload.teacher_id)
        _valid_content_placement(cur, class_id, payload.content_level, payload.content_key)
        for section_id in set(payload.section_ids):
            _section(cur, class_id, section_id)
        cur.execute("""INSERT INTO quiz(class_id,title,date_created,total_points,status,
                       grading_period,delivery_type,origin,content_level,content_key)
                       VALUES (%s,%s,%s,%s,'Draft',%s,'offline','manual',%s,%s)
                       RETURNING quiz_id""",
                    (class_id, payload.title.strip(), payload.quiz_date, payload.total_points,
                     payload.grading_period, payload.content_level, payload.content_key))
        quiz_id = cur.fetchone()["quiz_id"]
        for section_id in set(payload.section_ids):
            cur.execute("INSERT INTO quiz_sections(quiz_id,section_id) VALUES (%s,%s)",
                        (quiz_id, section_id))
            cur.execute("DELETE FROM grade_publication WHERE class_id=%s AND section_id=%s",
                        (class_id, section_id))
        conn.commit()
        return {"quiz_id": quiz_id, "delivery_type": "offline", "status": "Draft"}
    finally:
        conn.close()


@work_router.get("/{class_id}/offline-quizzes")
def list_offline_quizzes(class_id: int, teacher_id: int, section_id: int):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _owns(cur, class_id, teacher_id)
        _section(cur, class_id, section_id)
        cur.execute("""SELECT q.quiz_id,q.title,q.date_created AS quiz_date,q.total_points,
                              q.grading_period,q.content_level,q.content_key
                       FROM quiz q JOIN quiz_sections qs ON qs.quiz_id=q.quiz_id
                       WHERE q.class_id=%s AND q.delivery_type='offline' AND qs.section_id=%s
                       ORDER BY q.date_created DESC,q.quiz_id DESC""", (class_id, section_id))
        quizzes = [dict(row) for row in cur.fetchall()]
        for quiz in quizzes:
            cur.execute("""SELECT DISTINCT ON(student_id) student_id,total_score
                           FROM quiz_score WHERE quiz_id=%s ORDER BY student_id,
                           submitted_at DESC NULLS LAST,score_id DESC""", (quiz["quiz_id"],))
            quiz["scores"] = {row["student_id"]: row["total_score"] for row in cur.fetchall()}
        return {"students": _roster(cur, class_id, section_id), "quizzes": quizzes}
    finally:
        conn.close()


@work_router.put("/{class_id}/offline-quizzes/{quiz_id}/scores")
def save_offline_scores(class_id: int, quiz_id: int, payload: OfflineScoreBatch):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _owns(cur, class_id, payload.teacher_id)
        cur.execute("""SELECT total_points,grading_period FROM quiz WHERE quiz_id=%s AND class_id=%s
                       AND delivery_type='offline'""", (quiz_id, class_id))
        quiz = cur.fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="Face-to-face quiz not found.")
        cur.execute("""SELECT e.student_id,e.section_id FROM enrollment e
                       JOIN quiz_sections qs ON qs.section_id=e.section_id AND qs.quiz_id=%s
                       WHERE e.class_id=%s""", (quiz_id, class_id))
        allowed = {row["student_id"]: row["section_id"] for row in cur.fetchall()}
        if len({item.student_id for item in payload.scores}) != len(payload.scores):
            raise HTTPException(status_code=422, detail="Each student may appear only once.")
        for item in payload.scores:
            if item.student_id not in allowed or (item.score is not None and item.score > quiz["total_points"]):
                raise HTTPException(status_code=422, detail="Invalid student or score exceeds the maximum.")
            if item.score is None:
                continue
            cur.execute("""INSERT INTO quiz_score(student_id,quiz_id,is_online,total_score,max_score,
                           date_taken,submitted_at,grading_period)
                           VALUES (%s,%s,false,%s,%s,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP,%s)""",
                        (item.student_id, quiz_id, item.score, quiz["total_points"], quiz["grading_period"]))
        cur.execute("DELETE FROM grade_publication WHERE class_id=%s", (class_id,))
        conn.commit()
        return {"saved": len([item for item in payload.scores if item.score is not None])}
    finally:
        conn.close()
