"""Explicit, idempotent local demonstration data. Never run in production."""
import os

from db import DB_CONFIG, get_db_connection
from migrate_academic import migrate
from utils import hash_password


def seed():
    if DB_CONFIG["host"] not in {"localhost", "127.0.0.1"} or os.getenv("ALLOW_DEMO_SEED") != "1":
        raise RuntimeError("Demo seed requires a local database and ALLOW_DEMO_SEED=1.")
    migrate()
    password = os.getenv("DEMO_PASSWORD", "LearnSyncDemo2026!")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            people = [("admin@learnsync.local", "Demo Administrator", "admin"),
                      ("faculty1@learnsync.local", "Maricel Peneo", "teacher"),
                      ("faculty2@learnsync.local", "Edgar Venus", "teacher")]
            people += [(f"student{i}@learnsync.local", f"Demo Student {i}", "student") for i in range(1, 7)]
            users = {}
            for email, name, role in people:
                cur.execute(
                    """INSERT INTO account(name,email,password,role,is_activated)
                       VALUES (%s,%s,%s,%s,true) ON CONFLICT(email) DO NOTHING""",
                    (name, email, hash_password(password), role),
                )
                cur.execute("SELECT user_id FROM account WHERE email=%s", (email,))
                users[email] = cur.fetchone()[0]
            faculty = []
            for i in (1, 2):
                user_id = users[f"faculty{i}@learnsync.local"]
                cur.execute("INSERT INTO teacher(user_id) VALUES (%s) ON CONFLICT(user_id) DO NOTHING", (user_id,))
                cur.execute("SELECT employee_id FROM teacher WHERE user_id=%s", (user_id,))
                faculty.append(cur.fetchone()[0])
            students = []
            for i in range(1, 7):
                student_id = 260000 + i
                user_id = users[f"student{i}@learnsync.local"]
                cur.execute("INSERT INTO student(student_id,user_id) VALUES (%s,%s) ON CONFLICT(student_id) DO NOTHING",
                            (student_id, user_id))
                students.append(student_id)
            cur.execute("UPDATE academic_term SET is_active=false WHERE is_active=true AND (school_year,semester) <> ('2026-2027','First')")
            cur.execute(
                """INSERT INTO academic_term(school_year,semester,is_active) VALUES ('2026-2027','First',true)
                   ON CONFLICT(school_year,semester) DO UPDATE SET is_active=true RETURNING term_id"""
            )
            term_id = cur.fetchone()[0]
            catalog = []
            for code, title in (("ENT101", "Entrepreneurship Fundamentals"), ("ENT102", "Business Planning")):
                cur.execute(
                    """INSERT INTO subject_catalog(code,title,units) VALUES (%s,%s,3)
                       ON CONFLICT(code) DO UPDATE SET title=EXCLUDED.title RETURNING subject_id""",
                    (code, title),
                )
                catalog.append((cur.fetchone()[0], title))
            sections = []
            for code, name, adviser in (("DEMO-ENT-A", "1A", faculty[0]), ("DEMO-ENT-B", "1B", faculty[1])):
                cur.execute("SELECT section_id FROM section WHERE join_code=%s", (code,))
                row = cur.fetchone()
                if row:
                    section_id = row[0]
                else:
                    cur.execute(
                        """INSERT INTO section(section,term_id,year_level,adviser_id,join_code,workflow_status)
                           VALUES (%s,%s,1,%s,%s,'active') RETURNING section_id""",
                        (name, term_id, adviser, code),
                    )
                    section_id = cur.fetchone()[0]
                sections.append(section_id)
            for index, student_id in enumerate(students):
                cur.execute("INSERT INTO section_member(section_id,student_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                            (sections[index // 3], student_id))
            for index, (subject_id, title) in enumerate(catalog):
                code = f"DEMO-E{index + 1}"
                cur.execute("SELECT class_id FROM class WHERE class_code=%s AND workflow_status='active'", (code,))
                row = cur.fetchone()
                if row:
                    class_id = row[0]
                else:
                    cur.execute(
                        """INSERT INTO class(class_code,employee_id,subject,subject_id,term_id,workflow_status)
                           VALUES (%s,%s,%s,%s,%s,'active') RETURNING class_id""",
                        (code, faculty[index], title, subject_id, term_id),
                    )
                    class_id = cur.fetchone()[0]
                for section_id in sections:
                    cur.execute("INSERT INTO class_section(class_id,section_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                                (class_id, section_id))
                    cur.execute(
                        """INSERT INTO enrollment(student_id,class_id,section_id)
                           SELECT student_id,%s,section_id FROM section_member WHERE section_id=%s
                           ON CONFLICT(student_id,class_id) DO UPDATE SET section_id=EXCLUDED.section_id""",
                        (class_id, section_id),
                    )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
    print("Local demo users and academic assignments ready.")
