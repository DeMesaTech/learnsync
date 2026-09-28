"""Grade calculation from recorded assessments and an approved syllabus rule."""
from collections import defaultdict


PERIODS = ("Midterm", "Finals")
CATEGORIES = ("attendance", "quiz", "activity", "exam")


def calculate_student(records, rule):
    """Pure calculation. A missing score never becomes zero silently."""
    periods = {}
    for period in PERIODS:
        categories = {}
        pending = []
        weighted = 0.0
        for category in CATEGORIES:
            weight = float(rule["weights"][category])
            items = records.get(period, {}).get(category, [])
            if weight == 0:
                categories[category] = None
                continue
            if not items or any(score is None or total is None or float(total) <= 0 for score, total in items):
                categories[category] = None
                pending.append(category)
                continue
            raw = sum(float(score) for score, _ in items) / sum(float(total) for _, total in items) * 100
            raw = max(0.0, min(100.0, raw))
            transformed = 50 + raw / 2 if rule["transmutation"] == "sample_50_100" else raw
            categories[category] = round(transformed, 2)
            weighted += transformed * weight / 100
        periods[period] = {"categories": categories, "grade": round(weighted, 2) if not pending else None,
                           "pending": pending}
    if all(periods[period]["grade"] is not None for period in PERIODS):
        course = round(sum(periods[period]["grade"] * float(rule["period_shares"][period]) / 100
                           for period in PERIODS), 2)
    else:
        course = None
    return {"periods": periods, "course_grade": course,
            "remark": "Pending" if course is None else
                      ("Passed" if course >= float(rule["passing_threshold"]) else "Failed")}


def _append(records, period, category, score, total):
    if period in PERIODS and category in CATEGORIES:
        records[period][category].append((score, total))


def load_class_preview(cur, class_id: int, section_id: int, syllabus):
    cur.execute(
        """SELECT s.section, e.student_id, COALESCE(a.name,e.student_id::text) AS name
           FROM enrollment e JOIN section s ON s.section_id=e.section_id
           LEFT JOIN student st ON st.student_id=e.student_id
           LEFT JOIN account a ON a.user_id=st.user_id
           WHERE e.class_id=%s AND e.section_id=%s ORDER BY name""",
        (class_id, section_id),
    )
    students = cur.fetchall()
    result = []
    for student in students:
        student_id = student["student_id"]
        records = defaultdict(lambda: defaultdict(list))
        cur.execute("""SELECT DISTINCT grading_period FROM attendance_session
                       WHERE class_id=%s AND section_id=%s""", (class_id, section_id))
        daily_periods = {row["grading_period"] for row in cur.fetchall()}
        cur.execute(
            """SELECT gc.grading_period,gc.category,gs.score,gc.total_items
               FROM grading_column gc LEFT JOIN grading_score gs
                    ON gs.column_id=gc.column_id AND gs.student_id=%s
               WHERE gc.class_id=%s AND gc.section=%s""",
            (student_id, class_id, student["section"]),
        )
        for row in cur.fetchall():
            if row["category"] == "attendance" and row["grading_period"] in daily_periods:
                continue
            _append(records, row["grading_period"], row["category"], row["score"], row["total_items"])
        if daily_periods:
            cur.execute("""SELECT a.grading_period,m.status FROM attendance_session a
                           JOIN attendance_mark m ON m.session_id=a.session_id
                           WHERE a.class_id=%s AND a.section_id=%s AND m.student_id=%s""",
                        (class_id, section_id, student_id))
            late_credit = float(syllabus["grading_rule"].get("attendance_late_percent", 50)) / 100
            for row in cur.fetchall():
                credit = {"Present": 1, "Absent": 0, "Late": late_credit,
                          "Excused": None}[row["status"]]
                if credit is not None:
                    _append(records, row["grading_period"], "attendance", credit, 1)
        cur.execute(
            """SELECT grading_period, score, is_present FROM attendance
               WHERE class_id=%s AND student_id=%s""",
            (class_id, student_id),
        )
        for row in cur.fetchall():
            if row["grading_period"] in daily_periods:
                continue
            score = row["score"]
            if score is None:
                score = 1 if row["is_present"] else 0 if row["is_present"] is not None else None
            elif score > 1:
                score = float(score) / 100
            _append(records, row["grading_period"], "attendance", score, 1)
        cur.execute(
            """SELECT q.quiz_id,q.grading_period,q.total_points,
                      (SELECT qs.total_score FROM quiz_score qs WHERE qs.quiz_id=q.quiz_id
                       AND qs.student_id=%s ORDER BY qs.submitted_at DESC NULLS LAST,qs.score_id DESC LIMIT 1) AS score,
                      (SELECT qs.max_score FROM quiz_score qs WHERE qs.quiz_id=q.quiz_id
                       AND qs.student_id=%s ORDER BY qs.submitted_at DESC NULLS LAST,qs.score_id DESC LIMIT 1) AS max_score
               FROM quiz q LEFT JOIN syllabus_section_override o ON o.class_id=q.class_id
                    AND o.section_id=%s AND o.item_type='quiz' AND o.item_id=q.quiz_id
               WHERE q.class_id=%s AND q.status='Published' AND COALESCE(o.visible,true)
                 AND (NOT EXISTS (SELECT 1 FROM quiz_sections qs WHERE qs.quiz_id=q.quiz_id)
                      OR EXISTS (SELECT 1 FROM quiz_sections qs WHERE qs.quiz_id=q.quiz_id AND qs.section_id=%s))""",
            (student_id, student_id, section_id, class_id, section_id),
        )
        for row in cur.fetchall():
            _append(records, row["grading_period"], "quiz", row["score"],
                    row["max_score"] or row["total_points"])
        cur.execute(
            """SELECT a.grading_period,a.points,
                      (SELECT s.score FROM act_submission s WHERE s.activity_id=a.activity_id
                       AND s.student_id=%s ORDER BY s.submission_date DESC NULLS LAST,
                       s.act_submission_id DESC LIMIT 1) AS score
               FROM activity a LEFT JOIN syllabus_section_override o ON o.class_id=a.class_id
                    AND o.section_id=%s AND o.item_type='activity' AND o.item_id=a.activity_id
               WHERE a.class_id=%s AND a.status='Published' AND COALESCE(o.visible,true)
                 AND (NOT EXISTS (SELECT 1 FROM activity_sections ac WHERE ac.activity_id=a.activity_id)
                      OR EXISTS (SELECT 1 FROM activity_sections ac WHERE ac.activity_id=a.activity_id AND ac.section_id=%s))""",
            (student_id, section_id, class_id, section_id),
        )
        for row in cur.fetchall():
            _append(records, row["grading_period"], "activity", row["score"], row["points"])
        cur.execute(
            """SELECT grading_period,score,total FROM grade WHERE class_id=%s AND student_id=%s
               AND lower(type) IN ('exam','midterm exam','final exam')""",
            (class_id, student_id),
        )
        for row in cur.fetchall():
            _append(records, row["grading_period"], "exam", row["score"], row["total"])
        computed = calculate_student(records, syllabus["grading_rule"])
        result.append({"student_id": student_id, "name": student["name"], **computed})
    return {"class_id": class_id, "section_id": section_id,
            "syllabus_id": syllabus["syllabus_id"], "syllabus_version": syllabus["version"],
            "passing_threshold": syllabus["grading_rule"]["passing_threshold"],
            "students": result}
