"""Quiz creation, delivery, and submission endpoints."""

from datetime import datetime
from typing import Any, Optional

import psycopg2
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from psycopg2.extras import RealDictCursor

from db import get_db_connection

quiz_router = APIRouter(prefix="/api/quizzes", tags=["Quizzes"])


class QuizQuestionDraft(BaseModel):
    question_text: str
    question_type: str = "short_answer"
    choices: list[str] = Field(default_factory=list)
    correct_answer: str = ""
    points: float = 1
    display_order: int = 0
    explanation: str = ""


class QuizDraftRequest(BaseModel):
    class_id: int
    module_id: Optional[int] = None
    title: str
    description: str = ""
    question_types: list[str] = Field(default_factory=lambda: ["multiple_choice"])
    questions_per_type: int = Field(default=3, ge=1, le=50)
    points_per_question: float = Field(default=1, gt=0)
    difficulty: str = "balanced"
    learning_outcomes: str = ""
    exclusions: str = ""


class QuizCreateRequest(BaseModel):
    class_id: int
    module_id: Optional[int] = None
    title: str
    description: str = ""
    deadline: Optional[datetime] = None
    time_limit_minutes: Optional[int] = Field(default=None, ge=1)
    status: str = "Published"
    total_points: Optional[float] = None
    sections: list[str] = Field(default_factory=list)
    questions: list[QuizQuestionDraft] = Field(min_length=1)


class QuizAnswer(BaseModel):
    question_id: int
    answer: Any = None


class QuizSubmitRequest(BaseModel):
    student_id: int
    answers: list[QuizAnswer] = Field(default_factory=list)


def _class_exists(cur, class_id: int) -> None:
    cur.execute("SELECT class_id FROM class WHERE class_id = %s", (class_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Class not found.")


def _quiz_payload(cur, quiz_id: int, include_answers: bool = True) -> dict:
    cur.execute(
        """
        SELECT q.quiz_id, q.class_id, c.subject AS class_name, q.title, q.description,
               q.module_id, q.deadline, q.time_limit_minutes, q.total_points, q.status,
               q.date_created
        FROM quiz q JOIN class c ON c.class_id = q.class_id
        WHERE q.quiz_id = %s
        """,
        (quiz_id,),
    )
    quiz = cur.fetchone()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found.")

    fields = "question_id, question_text, question_type, choices, points, display_order, explanation"
    if include_answers:
        fields = "question_id, question_text, question_type, choices, correct_answer, points, display_order, explanation"
    cur.execute(
        f"SELECT {fields} FROM question WHERE quiz_id = %s ORDER BY display_order, question_id",
        (quiz_id,),
    )
    result = dict(quiz)
    result["questions"] = [dict(row) for row in cur.fetchall()]
    return result


def _draft_questions(request: QuizDraftRequest, context: str) -> list[dict]:
    questions = []
    order = 0
    for question_type in request.question_types:
        normalized = question_type.lower().replace(" ", "_")
        for index in range(request.questions_per_type):
            order += 1
            if normalized in {"multiple_choice", "choice"}:
                questions.append({
                    "question_text": f"Which statement best reflects this lesson? (Question {index + 1})",
                    "question_type": "multiple_choice",
                    "choices": ["It applies the lesson concept", "It is unrelated to the lesson", "It contradicts the lesson", "It cannot be determined"],
                    "correct_answer": "It applies the lesson concept",
                    "points": request.points_per_question,
                    "display_order": order,
                    "explanation": "Review the selected module content for the supporting concept.",
                })
            elif normalized in {"true_false", "truefalse"}:
                questions.append({
                    "question_text": f"The selected lesson content supports its main learning objective. (Question {index + 1})",
                    "question_type": "true_false",
                    "choices": ["True", "False"],
                    "correct_answer": "True",
                    "points": request.points_per_question,
                    "display_order": order,
                    "explanation": "Use the module objective and lesson context to verify the answer.",
                })
            else:
                questions.append({
                    "question_text": f"Explain one important idea from the selected lesson. (Question {index + 1})",
                    "question_type": "short_answer",
                    "choices": [],
                    "correct_answer": "",
                    "points": request.points_per_question,
                    "display_order": order,
                    "explanation": "Award points for an accurate explanation grounded in the lesson.",
                })
    return questions


@quiz_router.post("/generate-draft")
def generate_draft(request: QuizDraftRequest):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _class_exists(cur, request.class_id)
        context = ""
        if request.module_id:
            cur.execute("SELECT text FROM module_content WHERE module_id = %s ORDER BY chunk_index LIMIT 6", (request.module_id,))
            context = "\n".join(row["text"] for row in cur.fetchall())
        return {
            "title": request.title,
            "description": request.learning_outcomes or f"Generated {request.difficulty} quiz based on the selected lesson.",
            "context_used": bool(context),
            "questions": _draft_questions(request, context),
        }
    except psycopg2.Error as error:
        raise HTTPException(status_code=500, detail="Unable to generate quiz draft.") from error
    finally:
        conn.close()


@quiz_router.post("")
def create_quiz(request: QuizCreateRequest):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _class_exists(cur, request.class_id)
        total_points = request.total_points or sum(question.points for question in request.questions)
        cur.execute(
            """
            INSERT INTO quiz (class_id, title, date_created, description, module_id, deadline,
                              time_limit_minutes, total_points, status)
            VALUES (%s, %s, CURRENT_TIMESTAMP, %s, %s, %s, %s, %s, %s)
            RETURNING quiz_id
            """,
            (request.class_id, request.title, request.description, request.module_id, request.deadline,
             request.time_limit_minutes, total_points, request.status),
        )
        quiz_id = cur.fetchone()["quiz_id"]
        for question in request.questions:
            cur.execute(
                """
                INSERT INTO question (quiz_id, question_text, correct_answer, question_type,
                                      choices, points, display_order, explanation)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                """,
                (quiz_id, question.question_text, question.correct_answer, question.question_type,
                 __import__("json").dumps(question.choices), question.points,
                 question.display_order, question.explanation),
            )
        cur.execute(
            """
            INSERT INTO quiz_sections (quiz_id, section_id)
            SELECT %s, section_id FROM section
            WHERE class_id = %s AND (%s = '{}' OR section = ANY(%s))
            ON CONFLICT DO NOTHING
            """,
            (quiz_id, request.class_id, request.sections, request.sections),
        )
        conn.commit()
        return _quiz_payload(cur, quiz_id)
    except psycopg2.Error as error:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Unable to save quiz.") from error
    finally:
        conn.close()


@quiz_router.get("/class/{class_id}")
def list_class_quizzes(class_id: int):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT q.quiz_id, q.class_id, q.title, q.description, q.date_created, q.deadline,
                   q.time_limit_minutes, q.total_points, q.status,
                   COUNT(question.question_id) AS question_count
            FROM quiz q LEFT JOIN question ON question.quiz_id = q.quiz_id
            WHERE q.class_id = %s
            GROUP BY q.quiz_id ORDER BY q.date_created DESC, q.quiz_id DESC
            """,
            (class_id,),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


@quiz_router.get("/{quiz_id}")
def get_quiz(quiz_id: int):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        return _quiz_payload(cur, quiz_id, include_answers=False)
    finally:
        conn.close()


@quiz_router.get("/teacher/{quiz_id}")
def get_teacher_quiz(quiz_id: int):
    """Return the full quiz, including answer keys, for teacher review."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        return _quiz_payload(cur, quiz_id, include_answers=True)
    finally:
        conn.close()


@quiz_router.post("/{quiz_id}/submit")
def submit_quiz(quiz_id: int, request: QuizSubmitRequest):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        quiz = _quiz_payload(cur, quiz_id, include_answers=True)
        cur.execute("SELECT question_id, correct_answer, points FROM question WHERE quiz_id = %s", (quiz_id,))
        questions = {row["question_id"]: row for row in cur.fetchall()}
        score = 0.0
        max_score = sum(float(row["points"] or 0) for row in questions.values())
        for answer in request.answers:
            question = questions.get(answer.question_id)
            if not question:
                continue
            expected = str(question["correct_answer"] or "").strip().lower()
            actual = str(answer.answer or "").strip().lower()
            is_correct = bool(expected and actual == expected)
            score += float(question["points"] or 0) if is_correct else 0
        cur.execute(
            """
            INSERT INTO quiz_score (student_id, quiz_id, is_online, total_score, max_score, date_taken, submitted_at)
            VALUES (%s, %s, TRUE, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING score_id
            """,
            (request.student_id, quiz_id, score, max_score),
        )
        score_id = cur.fetchone()["score_id"]
        for answer in request.answers:
            question = questions.get(answer.question_id)
            if not question:
                continue
            expected = str(question["correct_answer"] or "").strip().lower()
            actual = str(answer.answer or "").strip().lower()
            cur.execute(
                """
                INSERT INTO student_answer (student_id, quiz_id, score_id, question_id, answer_text, answer_json, is_correct)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                """,
                (request.student_id, quiz_id, score_id, answer.question_id, str(answer.answer or ""),
                 __import__("json").dumps(answer.answer), bool(expected and actual == expected)),
            )
        conn.commit()
        return {"score_id": score_id, "score": score, "max_score": max_score, "percentage": round(score * 100 / max_score, 2) if max_score else 0}
    except psycopg2.Error as error:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Unable to submit quiz.") from error
    finally:
        conn.close()
