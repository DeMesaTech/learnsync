"""Program-owned academic setup, curriculum import, and masterlist enrollment."""
import csv
import io
import re
import uuid
from pathlib import Path
from typing import Literal

from docx import Document
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from psycopg2.extras import Json, RealDictCursor

from db import get_db_connection

academic_router = APIRouter(prefix="/api/academic", tags=["academic"])


class TermInput(BaseModel):
    school_year: str = Field(pattern=r"^[0-9]{4}-[0-9]{4}$")
    semester: Literal["First", "Second", "Summer"]
    is_active: bool = False


class SubjectInput(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=150)
    description: str = ""
    units: float | None = Field(default=None, ge=0)
    active: bool = True


class SectionInput(BaseModel):
    term_id: int
    year_level: int = Field(ge=1, le=8)
    name: str = Field(min_length=1, max_length=10)
    adviser_id: int | None = None
    join_code: str = Field(min_length=4, max_length=24)
    program_id: int | None = None
    curriculum_version_id: int | None = None


class RosterInput(BaseModel):
    student_ids: list[int]


class OfferingInput(BaseModel):
    term_id: int
    subject_id: int
    teacher_id: int
    # An offering is exactly one subject + one section + one assigned teacher.
    section_ids: list[int] = Field(min_length=1, max_length=1)


class RequestDecision(BaseModel):
    admin_user_id: int
    decision: Literal["approved", "rejected"]


class LegacyActivation(BaseModel):
    term_id: int
    subject_id: int
    section_map: dict[int, int]


class SubjectEnrollmentDecision(BaseModel):
    admin_user_id: int
    action: Literal["include", "exclude", "reset"]
    section_id: int | None = None
    reason: str = ""


class ProspectusCommit(BaseModel):
    program_code: str = Field(min_length=2, max_length=30)
    program_name: str = Field(min_length=2, max_length=150)
    version_label: str = Field(min_length=2, max_length=100)
    effective_school_year: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{4}$")
    rows: list[dict] = Field(min_length=1)


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _prospectus_rows(file_bytes: bytes) -> list[dict]:
    """Extract course rows from the editable prospectus table layout."""
    document = Document(io.BytesIO(file_bytes))
    rows = []
    for table in document.tables:
        headers = [_normalize_header(cell.text.strip()) for cell in table.rows[0].cells] if table.rows else []
        code_index = next((i for i, value in enumerate(headers) if value in {"subjectcode", "coursecode"}), None)
        title_index = next((i for i, value in enumerate(headers) if value in {"descriptivetitle", "coursetitle", "title"}), None)
        units_index = next((i for i, value in enumerate(headers) if value == "units"), None)
        prereq_index = next((i for i, value in enumerate(headers) if value in {"prerequisite", "prerequisites"}), None)
        if code_index is None or title_index is None:
            continue
        semester_text = " ".join(cell.text for cell in table.rows[0].cells).casefold()
        semester = "Second" if "second" in semester_text else "First"
        for raw in table.rows[1:]:
            cells = [cell.text.strip() for cell in raw.cells]
            if len(cells) <= max(code_index, title_index):
                continue
            code, title = cells[code_index].upper(), cells[title_index]
            if not code or not title or code.casefold().startswith(("total", "grand total")):
                continue
            units = None
            if units_index is not None and units_index < len(cells):
                try:
                    units = float(cells[units_index])
                except ValueError:
                    pass
            rows.append({"code": code, "title": title, "units": units,
                         "prerequisites": cells[prereq_index] if prereq_index is not None and prereq_index < len(cells) else "",
                         "semester": semester, "year_level": 1})
    return rows


def _masterlist_student_ids(file_bytes: bytes) -> list[int]:
    try:
        decoded = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="Masterlist must be a UTF-8 CSV file.") from exc
    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="Masterlist needs a Student ID column.")
    columns = {_normalize_header(name): name for name in reader.fieldnames}
    column = next((columns[name] for name in ("studentid", "studentnumber", "idnumber") if name in columns), None)
    if not column:
        raise HTTPException(status_code=422, detail="Masterlist needs a Student ID, Student Number, or ID Number column.")
    ids, invalid = [], []
    for number, row in enumerate(reader, start=2):
        value = (row.get(column) or "").strip()
        try:
            ids.append(int(value))
        except ValueError:
            invalid.append(number)
    if invalid:
        raise HTTPException(status_code=422, detail=f"Invalid student ID on CSV row(s): {', '.join(map(str, invalid[:10]))}.")
    if not ids:
        raise HTTPException(status_code=422, detail="Masterlist has no student IDs.")
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="Masterlist contains duplicate student IDs.")
    return ids


def _transaction_result(conn, cur, sql, params):
    cur.execute(sql, params)
    row = cur.fetchone()
    conn.commit()
    return row


def _admin(cur, user_id: int):
    cur.execute("SELECT 1 FROM account WHERE user_id = %s AND role = 'admin'", (user_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=403, detail="Admin account required.")


def _program_account(cur, user_id: int, program_id: int):
    """A shared Program Head/Secretary account may manage only its program."""
    cur.execute("SELECT 1 FROM program_account WHERE program_id=%s AND account_id=%s", (program_id, user_id))
    if not cur.fetchone():
        raise HTTPException(status_code=403, detail="Program Head/Secretary account for this program required.")


def _teacher(cur, employee_id: int):
    cur.execute("SELECT 1 FROM teacher WHERE employee_id = %s", (employee_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Faculty account not found.")


def _term(cur, term_id: int):
    cur.execute("SELECT 1 FROM academic_term WHERE term_id = %s", (term_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Academic term not found.")


def _sync_enrollment(cur, section_id: int, student_id: int, class_id: int | None = None):
    cur.execute("""SELECT cs.class_id FROM class_section cs JOIN class c ON c.class_id=cs.class_id
                   WHERE cs.section_id=%s AND c.workflow_status='active'
                     AND (%s IS NULL OR cs.class_id=%s)""", (section_id, class_id, class_id))
    for row in cur.fetchall():
        class_id = row["class_id"]
        cur.execute("SELECT action,teaching_section_id FROM subject_enrollment_exception WHERE student_id=%s AND class_id=%s",
                    (student_id, class_id))
        exception = cur.fetchone()
        if exception and exception["action"] == "exclude":
            continue
        teaching_section_id = (exception["teaching_section_id"] if exception else section_id)
        cur.execute("""INSERT INTO enrollment(student_id,class_id,section_id) VALUES (%s,%s,%s)
                       ON CONFLICT(student_id,class_id) DO UPDATE SET section_id=EXCLUDED.section_id""",
                    (student_id, class_id, teaching_section_id))
        cur.execute("DELETE FROM grade_publication WHERE class_id=%s", (class_id,))


def _add_member(cur, section_id: int, student_id: int):
    cur.execute("SELECT term_id FROM section WHERE section_id = %s AND workflow_status = 'active'", (section_id,))
    section = cur.fetchone()
    if not section:
        raise HTTPException(status_code=404, detail="Active section not found.")
    cur.execute("SELECT 1 FROM student WHERE student_id = %s", (student_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail=f"Student {student_id} not found.")
    cur.execute(
        """SELECT 1 FROM section_member sm JOIN section s ON s.section_id = sm.section_id
           WHERE sm.student_id = %s AND s.term_id = %s AND sm.section_id <> %s""",
        (student_id, section["term_id"], section_id),
    )
    if cur.fetchone():
        raise HTTPException(status_code=409, detail="Student already belongs to another section this term.")
    cur.execute(
        "INSERT INTO section_member(section_id, student_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (section_id, student_id),
    )
    # Home-section membership is not subject enrollment. A reviewed masterlist
    # controls the roster for each subject offering.


@academic_router.get("/setup")
def setup(admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        queries = {
            "terms": "SELECT * FROM academic_term ORDER BY school_year DESC, semester",
            "programs": "SELECT p.*,cv.curriculum_version_id,cv.version_label,cv.effective_school_year FROM program p LEFT JOIN curriculum_version cv ON cv.program_id=p.program_id AND cv.status='active' ORDER BY p.name,cv.created_at DESC",
            "subjects": "SELECT * FROM subject_catalog ORDER BY code",
            "faculty": "SELECT t.employee_id, a.name FROM teacher t JOIN account a ON a.user_id=t.user_id ORDER BY a.name",
            "students": "SELECT s.student_id, a.name FROM student s JOIN account a ON a.user_id=s.user_id ORDER BY a.name",
            "student_memberships": """SELECT sm.student_id, s.term_id FROM section_member sm
                                      JOIN section s ON s.section_id=sm.section_id""",
            "sections": """SELECT s.section_id, s.section, s.term_id, s.year_level, s.adviser_id, s.join_code, s.program_id, s.curriculum_version_id,
                                  COUNT(sm.student_id) AS student_count
                           FROM section s LEFT JOIN section_member sm ON sm.section_id=s.section_id
                           WHERE s.workflow_status='active'
                           GROUP BY s.section_id ORDER BY s.section""",
            "offerings": """SELECT c.class_id, c.subject, c.subject_id, c.term_id, c.employee_id AS teacher_id, c.teaching_section_id,
                                   ARRAY_REMOVE(ARRAY_AGG(cs.section_id), NULL) AS section_ids
                            FROM class c LEFT JOIN class_section cs ON cs.class_id=c.class_id
                            WHERE c.workflow_status='active' GROUP BY c.class_id ORDER BY c.subject""",
            "requests": """SELECT r.request_id, r.status, r.requested_at, r.section_id, r.student_id,
                                  a.name AS student_name, s.section
                           FROM enrollment_request r JOIN student st ON st.student_id=r.student_id
                           JOIN account a ON a.user_id=st.user_id JOIN section s ON s.section_id=r.section_id
                           WHERE r.status='pending' ORDER BY r.requested_at""",
            "legacy": """SELECT c.class_id, c.class_code, c.subject, lr.reason,
                                ARRAY_AGG(DISTINCT s.section_id) FILTER (WHERE s.section_id IS NOT NULL) AS old_section_ids
                         FROM legacy_review lr JOIN class c ON c.class_id=lr.class_id
                         LEFT JOIN section s ON s.class_id=c.class_id
                         WHERE lr.resolved_at IS NULL GROUP BY c.class_id, lr.reason ORDER BY c.class_id""",
        }
        result = {}
        for key, sql in queries.items():
            cur.execute(sql)
            result[key] = [dict(row) for row in cur.fetchall()]
        return result
    finally:
        conn.close()


@academic_router.post("/terms", status_code=201)
def create_term(payload: TermInput, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        if payload.is_active:
            cur.execute("UPDATE academic_term SET is_active=false WHERE is_active=true")
        cur.execute(
            """INSERT INTO academic_term(school_year, semester, is_active) VALUES (%s,%s,%s)
               ON CONFLICT (school_year, semester) DO UPDATE SET is_active=EXCLUDED.is_active
               RETURNING *""",
            (payload.school_year, payload.semester, payload.is_active),
        )
        row = cur.fetchone()
        conn.commit()
        return row
    finally:
        conn.close()


@academic_router.post("/subjects", status_code=201)
def save_subject(payload: SubjectInput, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        cur.execute(
            """INSERT INTO subject_catalog(code,title,description,units,active) VALUES (%s,%s,%s,%s,%s)
               ON CONFLICT (code) DO UPDATE SET title=EXCLUDED.title, description=EXCLUDED.description,
                   units=EXCLUDED.units, active=EXCLUDED.active RETURNING *""",
            (payload.code.strip().upper(), payload.title.strip(), payload.description, payload.units, payload.active),
        )
        row = cur.fetchone()
        conn.commit()
        return row
    finally:
        conn.close()


@academic_router.post("/prospectus/preview")
async def preview_prospectus(admin_user_id: int = Form(...), file: UploadFile = File(...)):
    """Parse an editable DOCX prospectus; the caller must review before committing it."""
    if Path(file.filename or "").suffix.lower() != ".docx":
        raise HTTPException(status_code=415, detail="Prospectus must be an editable DOCX file.")
    data = await file.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Prospectus must be 20 MB or smaller.")
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        rows = _prospectus_rows(data)
        if not rows:
            raise HTTPException(status_code=422, detail="No subject rows were found in the prospectus tables.")
        seen, warnings = {}, []
        for row in rows:
            key = row["code"].casefold()
            if key in seen and seen[key] != row["title"]:
                warnings.append(f"{row['code']} appears with multiple titles; correct it before approval.")
            seen[key] = row["title"]
        directory = Path(__file__).resolve().parents[1] / "uploads" / "prospectus"
        directory.mkdir(parents=True, exist_ok=True)
        stored = directory / f"{uuid.uuid4().hex}.docx"
        stored.write_bytes(data)
        return {"source_name": Path(file.filename).name[:255], "source_path": f"uploads/prospectus/{stored.name}",
                "rows": rows, "warnings": sorted(set(warnings))}
    finally:
        conn.close()


@academic_router.post("/prospectus/commit", status_code=201)
def commit_prospectus(payload: ProspectusCommit, admin_user_id: int = Query(...)):
    """Approve reviewed rows into a versioned curriculum; never overwrite a prior version."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        cur.execute("SELECT program_id FROM program WHERE code=%s", (payload.program_code.strip().upper(),))
        program = cur.fetchone()
        if program:
            _program_account(cur, admin_user_id, program["program_id"])
            program_id = program["program_id"]
        else:
            cur.execute("INSERT INTO program(code,name) VALUES (%s,%s) RETURNING program_id",
                        (payload.program_code.strip().upper(), payload.program_name.strip()))
            program_id = cur.fetchone()["program_id"]
            cur.execute("INSERT INTO program_account(program_id,account_id) VALUES (%s,%s)", (program_id, admin_user_id))
        cur.execute("""INSERT INTO curriculum_version(program_id,version_label,effective_school_year,status)
                       VALUES (%s,%s,%s,'active') RETURNING curriculum_version_id""",
                    (program_id, payload.version_label.strip(), payload.effective_school_year))
        version_id = cur.fetchone()["curriculum_version_id"]
        for row in payload.rows:
            code, title = str(row.get("code", "")).strip().upper(), str(row.get("title", "")).strip()
            if not code or not title:
                raise HTTPException(status_code=422, detail="Every approved prospectus row needs a code and title.")
            # Codes are deliberately not unique; the numeric subject ID is the LMS identity.
            cur.execute("INSERT INTO subject_catalog(code,title,description,units,active) VALUES (%s,%s,'',%s,true) RETURNING subject_id",
                        (code, title, row.get("units")))
            subject_id = cur.fetchone()["subject_id"]
            cur.execute("""INSERT INTO curriculum_subject(curriculum_version_id,subject_id,year_level,semester,prerequisites)
                           VALUES (%s,%s,%s,%s,%s)""",
                        (version_id, subject_id, int(row.get("year_level", 1)), row.get("semester", "First"),
                         str(row.get("prerequisites", ""))))
        cur.execute("UPDATE curriculum_version SET status='archived' WHERE program_id=%s AND curriculum_version_id<>%s AND status='active'",
                    (program_id, version_id))
        cur.execute("""INSERT INTO prospectus_import(program_id,curriculum_version_id,source_name,source_path,parsed_rows,status,submitted_by,approved_by,approved_at)
                       VALUES (%s,%s,%s,%s,%s,'approved',%s,%s,CURRENT_TIMESTAMP)""",
                    (program_id, version_id, "Reviewed prospectus", "", Json(payload.rows), admin_user_id, admin_user_id))
        conn.commit()
        return {"program_id": program_id, "curriculum_version_id": version_id, "subjects_created": len(payload.rows)}
    finally:
        conn.close()


@academic_router.put("/terms/{term_id}")
def update_term(term_id: int, payload: TermInput, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        _term(cur, term_id)
        if payload.is_active:
            cur.execute("UPDATE academic_term SET is_active=false WHERE is_active=true")
        return _transaction_result(conn, cur, """UPDATE academic_term SET school_year=%s,semester=%s,is_active=%s
               WHERE term_id=%s RETURNING *""",
               (payload.school_year, payload.semester, payload.is_active, term_id))
    finally:
        conn.close()


@academic_router.delete("/terms/{term_id}")
def delete_term(term_id: int, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        cur.execute("SELECT 1 FROM section WHERE term_id=%s UNION SELECT 1 FROM class WHERE term_id=%s", (term_id, term_id))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Term has sections or subject offerings.")
        cur.execute("DELETE FROM academic_term WHERE term_id=%s RETURNING term_id", (term_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Term not found.")
        conn.commit()
        return {"deleted": True}
    finally:
        conn.close()


@academic_router.put("/subjects/{subject_id}")
def update_subject(subject_id: int, payload: SubjectInput, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        cur.execute("""UPDATE subject_catalog SET code=%s,title=%s,description=%s,units=%s,active=%s
                       WHERE subject_id=%s RETURNING *""",
                    (payload.code.strip().upper(), payload.title.strip(), payload.description,
                     payload.units, payload.active, subject_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Subject not found.")
        cur.execute("UPDATE class SET subject=%s WHERE subject_id=%s", (row["title"], subject_id))
        conn.commit()
        return row
    finally:
        conn.close()


@academic_router.delete("/subjects/{subject_id}")
def deactivate_subject(subject_id: int, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        cur.execute("UPDATE subject_catalog SET active=false WHERE subject_id=%s RETURNING subject_id", (subject_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Subject not found.")
        conn.commit()
        return {"deactivated": True}
    finally:
        conn.close()


@academic_router.post("/sections", status_code=201)
def create_section(payload: SectionInput, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        _term(cur, payload.term_id)
        if payload.program_id is not None:
            _program_account(cur, admin_user_id, payload.program_id)
            cur.execute("SELECT 1 FROM curriculum_version WHERE curriculum_version_id=%s AND program_id=%s AND status='active'",
                        (payload.curriculum_version_id, payload.program_id))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Choose an active curriculum version for this program.")
        elif payload.curriculum_version_id is not None:
            raise HTTPException(status_code=400, detail="Choose the program for this curriculum version.")
        if payload.adviser_id is not None:
            _teacher(cur, payload.adviser_id)
        cur.execute(
            """INSERT INTO section(section,term_id,year_level,adviser_id,join_code,program_id,curriculum_version_id,workflow_status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'active') RETURNING section_id,section,term_id,year_level,join_code,program_id,curriculum_version_id""",
            (payload.name.strip().upper(), payload.term_id, payload.year_level,
             payload.adviser_id, payload.join_code.strip().upper(), payload.program_id, payload.curriculum_version_id),
        )
        row = cur.fetchone()
        conn.commit()
        return row
    finally:
        conn.close()


@academic_router.get("/sections/{section_id}/roster")
def section_roster(section_id: int, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        cur.execute("""SELECT st.student_id,a.name FROM section_member sm
                       JOIN student st ON st.student_id=sm.student_id
                       JOIN account a ON a.user_id=st.user_id
                       WHERE sm.section_id=%s ORDER BY a.name""", (section_id,))
        return {"students": cur.fetchall()}
    finally:
        conn.close()


@academic_router.put("/sections/{section_id}/roster")
def add_roster(section_id: int, payload: RosterInput, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        for student_id in set(payload.student_ids):
            _add_member(cur, section_id, student_id)
        conn.commit()
        return {"added": len(set(payload.student_ids))}
    finally:
        conn.close()


@academic_router.put("/sections/{section_id}")
def update_section(section_id: int, payload: SectionInput, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        cur.execute("SELECT term_id,section FROM section WHERE section_id=%s AND workflow_status='active'", (section_id,))
        old = cur.fetchone()
        if not old:
            raise HTTPException(status_code=404, detail="Active section not found.")
        if old["term_id"] != payload.term_id:
            cur.execute("SELECT 1 FROM class_section WHERE section_id=%s UNION SELECT 1 FROM section_member WHERE section_id=%s",
                        (section_id, section_id))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Move assignments and roster before changing term.")
        if old["section"] != payload.name.strip().upper():
            cur.execute("UPDATE grading_column SET section=%s WHERE section=%s AND class_id IN (SELECT class_id FROM class_section WHERE section_id=%s)",
                        (payload.name.strip().upper(), old["section"], section_id))
            cur.execute("UPDATE grade_visibility SET section=%s WHERE section=%s AND class_id IN (SELECT class_id FROM class_section WHERE section_id=%s)",
                        (payload.name.strip().upper(), old["section"], section_id))
        cur.execute("""UPDATE section SET term_id=%s,year_level=%s,section=%s,adviser_id=%s,join_code=%s
                       WHERE section_id=%s RETURNING section_id,section,term_id,year_level,adviser_id,join_code""",
                    (payload.term_id, payload.year_level, payload.name.strip().upper(), payload.adviser_id,
                     payload.join_code.strip().upper(), section_id))
        row = cur.fetchone()
        conn.commit()
        return row
    finally:
        conn.close()


@academic_router.delete("/sections/{section_id}")
def archive_section(section_id: int, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        cur.execute("SELECT 1 FROM class_section WHERE section_id=%s", (section_id,))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Remove subject assignments before archiving this section.")
        cur.execute("UPDATE section SET workflow_status='archived',join_code=NULL WHERE section_id=%s RETURNING section_id",
                    (section_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Section not found.")
        conn.commit()
        return {"archived": True}
    finally:
        conn.close()


@academic_router.delete("/sections/{section_id}/roster/{student_id}")
def remove_roster(section_id: int, student_id: int, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        cur.execute("""SELECT 1 FROM subject_enrollment_exception x
                       JOIN class c ON c.class_id=x.class_id
                       JOIN section s ON s.term_id=c.term_id
                       WHERE x.student_id=%s AND x.action='include' AND s.section_id=%s LIMIT 1""",
                    (student_id, section_id))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Reset this student's subject exceptions before removing their home section.")
        cur.execute("DELETE FROM section_member WHERE section_id=%s AND student_id=%s", (section_id, student_id))
        cur.execute("SELECT class_id FROM class_section WHERE section_id=%s", (section_id,))
        for offering in cur.fetchall():
            class_id = offering["class_id"]
            cur.execute("""SELECT teaching_section_id FROM subject_enrollment_exception
                           WHERE student_id=%s AND class_id=%s AND action='include'""",
                        (student_id, class_id))
            if cur.fetchone():
                continue
            cur.execute("""INSERT INTO subject_enrollment_history(student_id,class_id,section_id,action,changed_by)
                           SELECT student_id,class_id,section_id,'roster_removed',%s FROM enrollment
                           WHERE student_id=%s AND class_id=%s""", (admin_user_id, student_id, class_id))
            cur.execute("DELETE FROM enrollment WHERE student_id=%s AND class_id=%s", (student_id, class_id))
            cur.execute("DELETE FROM grade_publication WHERE class_id=%s", (class_id,))
        conn.commit()
        return {"removed": True}
    finally:
        conn.close()


@academic_router.get("/subject-enrollments")
def subject_enrollments(admin_user_id: int, term_id: int):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        _term(cur, term_id)
        cur.execute("""SELECT sm.student_id, sm.section_id AS home_section_id, a.name,
                              s.section AS home_section
                       FROM section_member sm JOIN section s ON s.section_id=sm.section_id
                       JOIN student st ON st.student_id=sm.student_id
                       JOIN account a ON a.user_id=st.user_id
                       WHERE s.term_id=%s ORDER BY a.name""", (term_id,))
        students = cur.fetchall()
        cur.execute("""SELECT c.class_id,c.subject,c.employee_id,cs.section_id,s.section
                       FROM class c JOIN class_section cs ON cs.class_id=c.class_id
                       JOIN section s ON s.section_id=cs.section_id
                       WHERE c.term_id=%s AND c.workflow_status='active'
                       ORDER BY c.subject,s.section""", (term_id,))
        offerings = cur.fetchall()
        cur.execute("""SELECT x.student_id,x.class_id,x.action,x.teaching_section_id,x.reason
                       FROM subject_enrollment_exception x JOIN class c ON c.class_id=x.class_id
                       WHERE c.term_id=%s""", (term_id,))
        exceptions = cur.fetchall()
        cur.execute("""SELECT e.student_id,e.class_id,e.section_id FROM enrollment e
                       JOIN class c ON c.class_id=e.class_id WHERE c.term_id=%s""", (term_id,))
        enrollments = cur.fetchall()
        return {"students": students, "offerings": offerings, "exceptions": exceptions,
                "enrollments": enrollments}
    finally:
        conn.close()


@academic_router.put("/students/{student_id}/subjects/{class_id}")
def set_subject_enrollment(student_id: int, class_id: int, payload: SubjectEnrollmentDecision):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, payload.admin_user_id)
        cur.execute("""SELECT c.term_id FROM class c WHERE c.class_id=%s AND c.workflow_status='active' FOR UPDATE""",
                    (class_id,))
        offering = cur.fetchone()
        if not offering:
            raise HTTPException(status_code=404, detail="Active subject offering not found.")
        cur.execute("""SELECT sm.section_id FROM section_member sm JOIN section s ON s.section_id=sm.section_id
                       WHERE sm.student_id=%s AND s.term_id=%s""", (student_id, offering["term_id"]))
        homes = [row["section_id"] for row in cur.fetchall()]
        if len(homes) != 1:
            raise HTTPException(status_code=409, detail="Student needs exactly one home section for this term.")
        home = homes[0]
        cur.execute("SELECT 1 FROM class_section WHERE class_id=%s AND section_id=%s", (class_id, home))
        home_subject = bool(cur.fetchone())
        if payload.action == "exclude" and not home_subject:
            raise HTTPException(status_code=400, detail="The home section is not assigned this subject.")
        if payload.action == "include":
            cur.execute("SELECT 1 FROM class_section WHERE class_id=%s AND section_id=%s",
                        (class_id, payload.section_id))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Choose a teaching section assigned to this subject.")
        cur.execute("SELECT section_id FROM enrollment WHERE student_id=%s AND class_id=%s", (student_id, class_id))
        previous = cur.fetchone()
        if payload.action == "reset":
            cur.execute("DELETE FROM subject_enrollment_exception WHERE student_id=%s AND class_id=%s",
                        (student_id, class_id))
            target = home if home_subject else None
        else:
            target = payload.section_id if payload.action == "include" else None
            cur.execute("""INSERT INTO subject_enrollment_exception
                           (student_id,class_id,action,teaching_section_id,reason,updated_by)
                           VALUES (%s,%s,%s,%s,%s,%s)
                           ON CONFLICT(student_id,class_id) DO UPDATE SET action=EXCLUDED.action,
                           teaching_section_id=EXCLUDED.teaching_section_id,reason=EXCLUDED.reason,
                           updated_by=EXCLUDED.updated_by,updated_at=CURRENT_TIMESTAMP""",
                        (student_id, class_id, payload.action, target, payload.reason, payload.admin_user_id))
        cur.execute("""INSERT INTO subject_enrollment_history
                       (student_id,class_id,section_id,new_section_id,action,reason,changed_by)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                    (student_id, class_id, previous["section_id"] if previous else None,
                     target, payload.action, payload.reason, payload.admin_user_id))
        if target is None:
            cur.execute("DELETE FROM enrollment WHERE student_id=%s AND class_id=%s", (student_id, class_id))
        else:
            cur.execute("""INSERT INTO enrollment(student_id,class_id,section_id) VALUES (%s,%s,%s)
                           ON CONFLICT(student_id,class_id) DO UPDATE SET section_id=EXCLUDED.section_id""",
                        (student_id, class_id, target))
        cur.execute("DELETE FROM grade_publication WHERE class_id=%s", (class_id,))
        conn.commit()
        return {"student_id": student_id, "class_id": class_id, "action": payload.action,
                "teaching_section_id": target}
    finally:
        conn.close()


@academic_router.post("/offerings", status_code=201)
def create_offering(payload: OfferingInput, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        _term(cur, payload.term_id)
        _teacher(cur, payload.teacher_id)
        cur.execute("SELECT title FROM subject_catalog WHERE subject_id=%s AND active=true", (payload.subject_id,))
        subject = cur.fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="Active subject not found.")
        section_ids = set(payload.section_ids)
        cur.execute(
            "SELECT section_id FROM section WHERE section_id=ANY(%s) AND term_id=%s AND workflow_status='active'",
            (list(section_ids), payload.term_id),
        )
        if {row["section_id"] for row in cur.fetchall()} != section_ids:
            raise HTTPException(status_code=400, detail="All sections must belong to the selected term.")
        cur.execute(
            """INSERT INTO class(employee_id,subject,subject_id,term_id,workflow_status)
               VALUES (%s,%s,%s,%s,'active') RETURNING class_id""",
            (payload.teacher_id, subject["title"], payload.subject_id, payload.term_id),
        )
        class_id = cur.fetchone()["class_id"]
        cur.execute("UPDATE class SET class_code=%s WHERE class_id=%s", (f"LS{class_id}", class_id))
        for section_id in section_ids:
            cur.execute("INSERT INTO class_section(class_id,section_id) VALUES (%s,%s)", (class_id, section_id))
            cur.execute("SELECT student_id FROM section_member WHERE section_id=%s", (section_id,))
            for row in cur.fetchall():
                _sync_enrollment(cur, section_id, row["student_id"], class_id)
        conn.commit()
        return {"class_id": class_id, "subject": subject["title"], "section_ids": sorted(section_ids)}
    finally:
        conn.close()


@academic_router.get("/faculty/{teacher_id}/offerings")
def faculty_offerings(teacher_id: int):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """SELECT c.class_id, c.class_code, c.subject, sc.code AS subject_code,
                      t.school_year, t.semester,
                      ARRAY_REMOVE(ARRAY_AGG(DISTINCT s.section),NULL) AS sections,
                      COUNT(DISTINCT e.student_id) AS students
               FROM class c JOIN subject_catalog sc ON sc.subject_id=c.subject_id
               JOIN academic_term t ON t.term_id=c.term_id
               JOIN class_section cs ON cs.class_id=c.class_id JOIN section s ON s.section_id=cs.section_id
               LEFT JOIN enrollment e ON e.class_id=c.class_id
               WHERE c.employee_id=%s AND c.workflow_status='active'
               GROUP BY c.class_id,sc.code,t.school_year,t.semester ORDER BY t.school_year DESC,c.subject""",
            (teacher_id,),
        )
        return {"offerings": cur.fetchall()}
    finally:
        conn.close()


@academic_router.put("/offerings/{class_id}")
def update_offering(class_id: int, payload: OfferingInput, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        _term(cur, payload.term_id)
        _teacher(cur, payload.teacher_id)
        cur.execute("SELECT title FROM subject_catalog WHERE subject_id=%s AND active=true", (payload.subject_id,))
        subject = cur.fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="Active subject not found.")
        cur.execute("SELECT 1 FROM class WHERE class_id=%s AND workflow_status='active' FOR UPDATE", (class_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Active offering not found.")
        new_sections = set(payload.section_ids)
        cur.execute("SELECT section_id FROM section WHERE section_id=ANY(%s) AND term_id=%s AND workflow_status='active'",
                    (list(new_sections), payload.term_id))
        if {row["section_id"] for row in cur.fetchall()} != new_sections:
            raise HTTPException(status_code=400, detail="Sections must belong to the selected term.")
        cur.execute("SELECT section_id FROM class_section WHERE class_id=%s", (class_id,))
        old_sections = {row["section_id"] for row in cur.fetchall()}
        if old_sections - new_sections:
            raise HTTPException(status_code=409, detail="Section removal requires archival review to preserve student records.")
        cur.execute("UPDATE class SET employee_id=%s,subject_id=%s,subject=%s,term_id=%s WHERE class_id=%s",
                    (payload.teacher_id, payload.subject_id, subject["title"], payload.term_id, class_id))
        for section_id in new_sections - old_sections:
            cur.execute("INSERT INTO class_section(class_id,section_id) VALUES (%s,%s)", (class_id, section_id))
            cur.execute("SELECT student_id FROM section_member WHERE section_id=%s", (section_id,))
            for row in cur.fetchall():
                _sync_enrollment(cur, section_id, row["student_id"], class_id)
        cur.execute("UPDATE grading_column SET teacher_id=%s WHERE class_id=%s", (payload.teacher_id, class_id))
        conn.commit()
        return {"updated": True, "class_id": class_id}
    finally:
        conn.close()


@academic_router.delete("/offerings/{class_id}")
def archive_offering(class_id: int, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        cur.execute("UPDATE class SET workflow_status='archived' WHERE class_id=%s RETURNING class_id", (class_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Offering not found.")
        conn.commit()
        return {"archived": True}
    finally:
        conn.close()


@academic_router.post("/join-requests", status_code=201)
def request_join(student_id: int, join_code: str):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT section_id FROM section WHERE join_code=%s AND workflow_status='active'", (join_code.strip().upper(),))
        section = cur.fetchone()
        if not section:
            raise HTTPException(status_code=404, detail="Section code not found.")
        cur.execute("SELECT 1 FROM student WHERE student_id=%s", (student_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Student not found.")
        cur.execute("SELECT 1 FROM section_member WHERE section_id=%s AND student_id=%s", (section["section_id"], student_id))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Already in this section.")
        cur.execute(
            """INSERT INTO enrollment_request(section_id,student_id) VALUES (%s,%s)
               RETURNING request_id,status""",
            (section["section_id"], student_id),
        )
        row = cur.fetchone()
        conn.commit()
        return row
    finally:
        conn.close()


@academic_router.post("/join-requests/{request_id}/decision")
def decide_join(request_id: int, payload: RequestDecision):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, payload.admin_user_id)
        cur.execute("SELECT * FROM enrollment_request WHERE request_id=%s FOR UPDATE", (request_id,))
        row = cur.fetchone()
        if not row or row["status"] != "pending":
            raise HTTPException(status_code=404, detail="Pending request not found.")
        if payload.decision == "approved":
            _add_member(cur, row["section_id"], row["student_id"])
        cur.execute(
            "UPDATE enrollment_request SET status=%s,decided_at=CURRENT_TIMESTAMP,decided_by=%s WHERE request_id=%s",
            (payload.decision, payload.admin_user_id, request_id),
        )
        conn.commit()
        return {"status": payload.decision}
    finally:
        conn.close()


@academic_router.post("/legacy/{class_id}/activate")
def activate_legacy(class_id: int, payload: LegacyActivation, admin_user_id: int = Query(...)):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _admin(cur, admin_user_id)
        _term(cur, payload.term_id)
        cur.execute("SELECT 1 FROM class WHERE class_id=%s AND workflow_status='legacy_review' FOR UPDATE", (class_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Legacy class not found.")
        cur.execute("SELECT section_id FROM section WHERE class_id=%s", (class_id,))
        old_ids = {row["section_id"] for row in cur.fetchall()}
        if old_ids != set(payload.section_map):
            raise HTTPException(status_code=400, detail="Map every legacy section explicitly.")
        for new_id in set(payload.section_map.values()):
            cur.execute("SELECT 1 FROM section WHERE section_id=%s AND term_id=%s AND workflow_status='active'", (new_id, payload.term_id))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Mapped section is not active in this term.")
        for old_id, new_id in payload.section_map.items():
            cur.execute("SELECT student_id FROM enrollment WHERE class_id=%s AND section_id=%s", (class_id, old_id))
            for row in cur.fetchall():
                _add_member(cur, new_id, row["student_id"])
            cur.execute("UPDATE enrollment SET section_id=%s WHERE class_id=%s AND section_id=%s", (new_id, class_id, old_id))
            cur.execute("INSERT INTO class_section(class_id,section_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", (class_id, new_id))
        cur.execute("SELECT title FROM subject_catalog WHERE subject_id=%s", (payload.subject_id,))
        subject = cur.fetchone()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found.")
        cur.execute(
            "UPDATE class SET term_id=%s,subject_id=%s,subject=%s,workflow_status='active' WHERE class_id=%s",
            (payload.term_id, payload.subject_id, subject["title"], class_id),
        )
        cur.execute("UPDATE legacy_review SET resolved_at=CURRENT_TIMESTAMP WHERE class_id=%s", (class_id,))
        conn.commit()
        return {"class_id": class_id, "status": "active"}
    finally:
        conn.close()
