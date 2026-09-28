"""Focused grade and local end-to-end checks for the revised faculty flow."""
import os
import unittest
import uuid
from collections import defaultdict
from pathlib import Path

from academic_grading import calculate_student
from syllabus_document import import_syllabus
from routers.faculty_syllabus import _content
from routers.learning_content import sanitize


class CalculationTests(unittest.TestCase):
    def test_outline_accepts_direct_and_subsection_topics(self):
        keys = _content({"title": "Example", "chapters": [{"key": "chapter", "title": "Chapter",
            "topics": [{"key": "direct", "title": "Direct"}],
            "subsections": [{"key": "lesson", "title": "Lesson", "topics": [
                {"key": "nested", "title": "Nested"}]}]}]})
        self.assertEqual(keys, {"chapter", "direct", "lesson", "nested"})

    def test_reviewed_html_removes_scripts_and_unsafe_links(self):
        markup = sanitize('<h3>Title</h3><script>alert(1)</script><a href="javascript:alert(2)">bad</a><a href="https://gmvcc.edu.ph">good</a>')
        self.assertNotIn("<script", markup)
        self.assertNotIn("javascript:", markup)
        self.assertIn('href="https://gmvcc.edu.ph"', markup)

    def test_missing_weighted_score_stays_pending(self):
        rule = {"weights": {"attendance": 0, "quiz": 50, "activity": 0, "exam": 50},
                "period_shares": {"Midterm": 50, "Finals": 50},
                "transmutation": "raw", "passing_threshold": 75}
        records = {"Midterm": {"quiz": [(8, 10)], "exam": [(None, 100)]}}
        computed = calculate_student(records, rule)
        self.assertIsNone(computed["periods"]["Midterm"]["grade"])
        self.assertIn("exam", computed["periods"]["Midterm"]["pending"])

    def test_sample_transmutation_and_period_shares(self):
        rule = {"weights": {"attendance": 0, "quiz": 100, "activity": 0, "exam": 0},
                "period_shares": {"Midterm": 40, "Finals": 60},
                "transmutation": "sample_50_100", "passing_threshold": 75}
        records = {"Midterm": {"quiz": [(8, 10)]}, "Finals": {"quiz": [(10, 10)]}}
        computed = calculate_student(records, rule)
        self.assertEqual(computed["periods"]["Midterm"]["grade"], 90)
        self.assertEqual(computed["course_grade"], 96)

    def test_sample_docx_imports_chapters_and_weights(self):
        sample = Path(__file__).resolve().parents[1] / "EPA-2-1-CBSUA-SIP-SYL-ACD.docx"
        if not sample.exists():
            self.skipTest("Optional user-supplied syllabus is unavailable")
        content, rule, warnings = import_syllabus(sample)
        self.assertGreaterEqual(len(content["chapters"]), 6)
        self.assertEqual(round(sum(rule["weights"].values())), 100)
        self.assertIn("Electronics", content["title"])


@unittest.skipUnless(os.getenv("RUN_DB_TESTS") == "1", "Set RUN_DB_TESTS=1 for local seeded database checks")
class DatabaseFlowTests(unittest.TestCase):
    def test_ai_quiz_draft_is_saved_for_faculty_review(self):
        from fastapi.testclient import TestClient
        from main import app
        from db import get_db_connection
        client = TestClient(app)
        login = client.post("/api/auth/login", json={"email": "faculty1@learnsync.local",
                          "password": os.getenv("DEMO_PASSWORD", "LearnSyncDemo2026!")}).json()
        class_id = client.get(f"/api/academic/faculty/{login['teacher_id']}/offerings").json()["offerings"][0]["class_id"]
        result = client.post("/api/quizzes", json={"class_id": class_id, "title": "Generated draft check",
            "status": "Draft", "origin": "ai", "grading_period": "Midterm", "sections": [],
            "questions": [{"question_text": "Explain this concept", "question_type": "short_answer",
                           "correct_answer": "An explanation", "points": 1}]})
        self.assertEqual(result.status_code, 200, result.text)
        quiz_id = result.json()["quiz_id"]
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT status,origin,delivery_type FROM quiz WHERE quiz_id=%s", (quiz_id,))
                self.assertEqual(cur.fetchone(), ("Draft", "ai", "online"))
                cur.execute("DELETE FROM question WHERE quiz_id=%s", (quiz_id,))
                cur.execute("DELETE FROM quiz_sections WHERE quiz_id=%s", (quiz_id,))
                cur.execute("DELETE FROM quiz WHERE quiz_id=%s", (quiz_id,))
            conn.commit()
        finally:
            conn.close()

    def test_daily_attendance_offline_quiz_and_outline(self):
        from fastapi.testclient import TestClient
        from main import app
        from db import get_db_connection
        client = TestClient(app)
        login = client.post("/api/auth/login", json={"email": "faculty1@learnsync.local",
                          "password": os.getenv("DEMO_PASSWORD", "LearnSyncDemo2026!")}).json()
        teacher_id = login["teacher_id"]
        class_id = client.get(f"/api/academic/faculty/{teacher_id}/offerings").json()["offerings"][0]["class_id"]
        section_id = client.get(f"/api/faculty/{class_id}/syllabus/items",
                                params={"teacher_id": teacher_id}).json()["sections"][0]["section_id"]
        week = client.get(f"/api/faculty/{class_id}/attendance", params={"teacher_id": teacher_id,
                         "section_id": section_id, "week": "2099-01-01"})
        self.assertEqual(week.status_code, 200, week.text)
        students = week.json()["students"]
        self.assertTrue(students)
        saved = client.post(f"/api/faculty/{class_id}/attendance/sessions", json={
            "teacher_id": teacher_id, "section_id": section_id, "session_date": "2099-01-01",
            "grading_period": "Midterm", "marks": [{"student_id": row["student_id"],
            "status": "Late" if index == 0 else "Present"} for index, row in enumerate(students)]})
        self.assertIn(saved.status_code, {201, 409}, saved.text)
        outline = client.get(f"/api/learning/{class_id}/outline", params={"teacher_id": teacher_id})
        self.assertIn(outline.status_code, {200, 409}, outline.text)
        title = "Offline check " + uuid.uuid4().hex[:8]
        quiz = client.post(f"/api/faculty/{class_id}/offline-quizzes", json={
            "teacher_id": teacher_id, "title": title, "quiz_date": "2099-01-01",
            "total_points": 10, "grading_period": "Midterm", "section_ids": [section_id]})
        self.assertEqual(quiz.status_code, 201, quiz.text)
        quiz_id = quiz.json()["quiz_id"]
        scores = client.put(f"/api/faculty/{class_id}/offline-quizzes/{quiz_id}/scores", json={
            "teacher_id": teacher_id, "scores": [{"student_id": students[0]["student_id"], "score": 0}]})
        self.assertEqual(scores.status_code, 200, scores.text)
        visible = client.get(f"/api/subjects/{students[0]['student_id']}/{class_id}/student/quizzes")
        self.assertEqual(visible.status_code, 200, visible.text)
        item = next(item for item in visible.json() if item["quiz_id"] == quiz_id)
        self.assertEqual(item["delivery_type"], "offline")
        self.assertIsNone(item["total_score"])
        attempt = client.post(f"/api/quizzes/{quiz_id}/submit", json={
            "student_id": students[0]["student_id"], "answers": []})
        self.assertEqual(attempt.status_code, 403, attempt.text)
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM quiz_score WHERE quiz_id=%s", (quiz_id,))
                cur.execute("DELETE FROM quiz_sections WHERE quiz_id=%s", (quiz_id,))
                cur.execute("DELETE FROM quiz WHERE quiz_id=%s", (quiz_id,))
                if saved.status_code == 201:
                    cur.execute("DELETE FROM attendance_session WHERE session_id=%s", (saved.json()["session_id"],))
            conn.commit()
        finally:
            conn.close()

    def test_migration_keeps_legacy_class_and_enrollment(self):
        from db import get_db_connection
        from migrate_academic import migrate

        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT employee_id FROM teacher ORDER BY employee_id LIMIT 1")
                faculty_id = cur.fetchone()[0]
                cur.execute("SELECT student_id FROM student ORDER BY student_id LIMIT 1")
                student_id = cur.fetchone()[0]
                code = "O" + uuid.uuid4().hex[:9]
                cur.execute("""INSERT INTO class(class_code,employee_id,subject)
                               VALUES (%s,%s,'Legacy preserved') RETURNING class_id""",
                            (code, faculty_id))
                class_id = cur.fetchone()[0]
                cur.execute("""INSERT INTO section(class_id,employee_id,section)
                               VALUES (%s,%s,'OLD') RETURNING section_id""",
                            (class_id, faculty_id))
                section_id = cur.fetchone()[0]
                cur.execute("INSERT INTO enrollment(student_id,class_id,section_id) VALUES (%s,%s,%s)",
                            (student_id, class_id, section_id))
            conn.commit()
        finally:
            conn.close()

        migrate()
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""SELECT c.workflow_status,e.section_id,lr.resolved_at
                               FROM class c JOIN enrollment e ON e.class_id=c.class_id
                               JOIN legacy_review lr ON lr.class_id=c.class_id
                               WHERE c.class_id=%s AND e.student_id=%s""", (class_id, student_id))
                row = cur.fetchone()
                self.assertEqual(row[0], "legacy_review")
                self.assertEqual(row[1], section_id)
                self.assertIsNone(row[2])
                cur.execute("DELETE FROM enrollment WHERE class_id=%s", (class_id,))
                cur.execute("DELETE FROM section WHERE section_id=%s", (section_id,))
                cur.execute("DELETE FROM legacy_review WHERE class_id=%s", (class_id,))
                cur.execute("DELETE FROM class WHERE class_id=%s", (class_id,))
            conn.commit()
        finally:
            conn.close()

    def test_admin_setup_join_approval_and_shared_roster(self):
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        login = client.post("/api/auth/login", json={"email": "admin@learnsync.local",
                                                    "password": os.getenv("DEMO_PASSWORD", "LearnSyncDemo2026!")})
        self.assertEqual(login.status_code, 200, login.text)
        admin_id = login.json()["user_id"]
        setup = client.get("/api/academic/setup", params={"admin_user_id": admin_id})
        self.assertEqual(setup.status_code, 200, setup.text)
        faculty_id = setup.json()["faculty"][0]["employee_id"]
        student_id = setup.json()["students"][0]["student_id"]
        marker = uuid.uuid4().hex[:8].upper()
        test_year = 3000 + int(marker, 16) % 5000
        term = client.post("/api/academic/terms", params={"admin_user_id": admin_id},
                           json={"school_year": f"{test_year}-{test_year + 1}", "semester": "Summer"})
        self.assertEqual(term.status_code, 201, term.text)
        subject = client.post("/api/academic/subjects", params={"admin_user_id": admin_id},
                              json={"code": marker, "title": "Faculty Flow Check", "units": 3})
        self.assertEqual(subject.status_code, 201, subject.text)
        section = client.post("/api/academic/sections", params={"admin_user_id": admin_id},
                              json={"term_id": term.json()["term_id"], "year_level": 1,
                                    "name": marker[:7], "adviser_id": faculty_id,
                                    "join_code": marker + "JOIN"})
        self.assertEqual(section.status_code, 201, section.text)
        section_id = section.json()["section_id"]
        offering = client.post("/api/academic/offerings", params={"admin_user_id": admin_id},
                               json={"term_id": term.json()["term_id"],
                                     "subject_id": subject.json()["subject_id"], "teacher_id": faculty_id,
                                     "section_ids": [section_id]})
        self.assertEqual(offering.status_code, 201, offering.text)
        request = client.post("/api/academic/join-requests", params={"student_id": student_id,
                                                                      "join_code": marker + "JOIN"})
        self.assertEqual(request.status_code, 201, request.text)
        decision = client.post(f"/api/academic/join-requests/{request.json()['request_id']}/decision",
                               json={"admin_user_id": admin_id, "decision": "approved"})
        self.assertEqual(decision.status_code, 200, decision.text)
        class_id = offering.json()["class_id"]
        decision_path = f"/api/academic/students/{student_id}/subjects/{class_id}"
        excluded = client.put(decision_path, json={"admin_user_id": admin_id, "action": "exclude",
                                                   "reason": "Irregular timetable"})
        self.assertEqual(excluded.status_code, 200, excluded.text)
        self.assertIsNone(excluded.json()["teaching_section_id"])
        included = client.put(decision_path, json={"admin_user_id": admin_id, "action": "include",
                                                   "section_id": section_id, "reason": "Attend this subject"})
        self.assertEqual(included.status_code, 200, included.text)
        reset = client.put(decision_path, json={"admin_user_id": admin_id, "action": "reset"})
        self.assertEqual(reset.status_code, 200, reset.text)
        from db import get_db_connection
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM section_member WHERE section_id=%s AND student_id=%s",
                            (section_id, student_id))
                self.assertIsNotNone(cur.fetchone())
                cur.execute("SELECT 1 FROM enrollment WHERE class_id=%s AND section_id=%s AND student_id=%s",
                            (offering.json()["class_id"], section_id, student_id))
                self.assertIsNotNone(cur.fetchone())
                cur.execute("DELETE FROM enrollment_request WHERE request_id=%s", (request.json()["request_id"],))
                cur.execute("DELETE FROM subject_enrollment_history WHERE class_id=%s", (offering.json()["class_id"],))
                cur.execute("DELETE FROM enrollment WHERE class_id=%s", (offering.json()["class_id"],))
                cur.execute("DELETE FROM class_section WHERE class_id=%s", (offering.json()["class_id"],))
                cur.execute("DELETE FROM class WHERE class_id=%s", (offering.json()["class_id"],))
                cur.execute("DELETE FROM section_member WHERE section_id=%s", (section_id,))
                cur.execute("DELETE FROM section WHERE section_id=%s", (section_id,))
                cur.execute("DELETE FROM subject_catalog WHERE subject_id=%s", (subject.json()["subject_id"],))
                cur.execute("DELETE FROM academic_term WHERE term_id=%s", (term.json()["term_id"],))
            conn.commit()
        finally:
            conn.close()

    def test_import_review_score_and_publish(self):
        from fastapi.testclient import TestClient
        from main import app

        client = TestClient(app)
        login = client.post("/api/auth/login", json={"email": "faculty1@learnsync.local",
                                                      "password": os.getenv("DEMO_PASSWORD", "LearnSyncDemo2026!")})
        self.assertEqual(login.status_code, 200, login.text)
        teacher_id = login.json()["teacher_id"]
        offerings = client.get(f"/api/academic/faculty/{teacher_id}/offerings").json()["offerings"]
        self.assertTrue(offerings)
        class_id = offerings[0]["class_id"]
        sample = Path(__file__).resolve().parents[1] / "EPA-2-1-CBSUA-SIP-SYL-ACD.docx"
        with sample.open("rb") as stream:
            response = client.post(f"/api/faculty/{class_id}/syllabus/import", data={"teacher_id": teacher_id},
                                   files={"file": (sample.name, stream)})
        self.assertEqual(response.status_code, 200, response.text)
        draft = response.json()
        saved = client.put(f"/api/faculty/{class_id}/syllabus/draft", json={
            "teacher_id": teacher_id, "content": draft["content"],
            "grading_rule": draft["grading_rule"], "acknowledge_warnings": True})
        self.assertEqual(saved.status_code, 200, saved.text)
        approved = client.post(f"/api/faculty/{class_id}/syllabus/approve", params={"teacher_id": teacher_id})
        self.assertEqual(approved.status_code, 200, approved.text)
        topic_key = draft["content"]["chapters"][0]["topics"][0]["key"]
        marker_content = "Reviewed topic " + uuid.uuid4().hex[:8]
        content = client.post(f"/api/learning/{class_id}/contents", json={
            "teacher_id": teacher_id, "topic_key": topic_key, "title": marker_content,
            "edited_html": "<h3>Reviewed text</h3><p>Faculty notes</p>", "publish": False})
        self.assertEqual(content.status_code, 200, content.text)
        content_id = content.json()["content_id"]
        published_content = client.put(f"/api/learning/{class_id}/contents/{content_id}", json={
            "teacher_id": teacher_id, "topic_key": topic_key, "title": marker_content,
            "edited_html": "<h3>Reviewed text</h3><p>Faculty notes</p>", "publish": True})
        self.assertEqual(published_content.status_code, 200, published_content.text)
        items = client.get(f"/api/faculty/{class_id}/syllabus/items", params={"teacher_id": teacher_id}).json()
        section = items["sections"][0]
        preview_url = f"/api/faculty/{class_id}/grades/preview"
        preview = client.get(preview_url, params={"teacher_id": teacher_id,
                                                   "section_id": section["section_id"]}).json()
        self.assertTrue(preview["students"])
        # A rerun may already have complete demo scores; publishing is checked after the new columns.
        marker = uuid.uuid4().hex[:8]
        for period, value in (("Midterm", 80), ("Finals", 90)):
            for category in ("quiz", "activity", "exam"):
                response = client.post("/api/grades/columns", json={
                    "class_id": class_id, "section": section["section"], "grading_period": period,
                    "teacher_id": teacher_id, "category": category, "label": f"{marker}-{period}-{category}",
                    "total_items": 100, "scores": [
                        {"student_id": student["student_id"], "score": value}
                        for student in preview["students"]]})
                self.assertEqual(response.status_code, 200, response.text)
        preview = client.get(preview_url, params={"teacher_id": teacher_id,
                                                   "section_id": section["section_id"]}).json()
        self.assertAlmostEqual(preview["students"][0]["course_grade"], 85, delta=1)
        published = client.post(f"/api/faculty/{class_id}/grades/publish", json={
            "teacher_id": teacher_id, "section_id": section["section_id"], "grading_period": "Course"})
        self.assertEqual(published.status_code, 200, published.text)
        student_id = preview["students"][0]["student_id"]
        student_grades = client.get(f"/api/grades/student/{student_id}").json()["courses"]
        matching = next(course for course in student_grades if course["id"] == class_id)
        self.assertEqual(matching["grade"], 90)
        self.assertEqual(matching["course_grade"], preview["students"][0]["course_grade"])
        student_outline = client.get(f"/api/learning/{class_id}/outline", params={"student_id": student_id})
        self.assertEqual(student_outline.status_code, 200, student_outline.text)
        self.assertTrue(any(item["content_id"] == content_id for item in student_outline.json()["materials"]))
        from db import get_db_connection
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM learning_content WHERE content_id=%s", (content_id,))
            conn.commit()
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
