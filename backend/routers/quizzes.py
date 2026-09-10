"""Quiz creation, delivery, and submission endpoints."""

from datetime import datetime
from collections import Counter
import json
import os
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
    question_settings: dict[str, dict[str, float]] = Field(default_factory=dict)


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


SUPPORTED_QUESTION_TYPES = {
    "multiple_choice", "true_false", "modified_true_false", "fill_in_the_blank",
    "matching", "short_answer", "essay", "problem_solving", "enumeration",
}
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"


def _question_plan(request: QuizDraftRequest) -> list[dict]:
    """Validate the requested mix and retain the teacher's per-type settings."""
    plan = []
    for raw_type in request.question_types:
        question_type = raw_type.lower().strip().replace(" ", "_")
        if question_type not in SUPPORTED_QUESTION_TYPES:
            raise HTTPException(status_code=422, detail=f"Unsupported question type: {raw_type}.")
        settings = request.question_settings.get(question_type, {})
        count = int(settings.get("count", request.questions_per_type))
        points = float(settings.get("points", request.points_per_question))
        if not 1 <= count <= 50 or points <= 0:
            raise HTTPException(status_code=422, detail="Each question type needs 1–50 questions and positive points.")
        plan.append({"type": question_type, "count": count, "points": points})
    if not plan:
        raise HTTPException(status_code=422, detail="Choose at least one question type.")
    if sum(item["count"] for item in plan) > 50:
        raise HTTPException(status_code=422, detail="A quiz draft cannot contain more than 50 questions.")
    return plan


def _generate_questions_with_ai(request: QuizDraftRequest, lesson_title: str, context: str, plan: list[dict]) -> list[dict]:
    """Create a structured, lesson-grounded draft through the existing Groq provider."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="GROQ_API_KEY is not configured on the backend.")

    prompt = {
        "lesson_title": lesson_title,
        "learning_outcomes": request.learning_outcomes,
        "exclusions": request.exclusions,
        "difficulty": request.difficulty,
        "question_plan": plan,
        "instructions": (
            "Create exactly the requested number of questions for every type. Use only the lesson context. "
            "Return JSON only: an array of objects with question_text, question_type, choices, correct_answer, explanation. "
            "multiple_choice must have exactly four choices and correct_answer must exactly match one choice. "
            "true_false must use choices [\"True\", \"False\"] and correct_answer must be one of them. "
            "All other types use choices [] and may use an empty correct_answer when teacher grading is required. "
            "Do not include markdown or claims not supported by the lesson."
        ),
        "lesson_context": context[:12000],
    }
    payload = json.dumps({
        "model": os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL,
        "temperature": 0.25,
        "max_tokens": 5000,
        "messages": [
            {"role": "system", "content": "You produce reliable, teacher-reviewable assessment drafts."},
            {"role": "user", "content": json.dumps(prompt)},
        ],
    }).encode("utf-8")
    groq_request = Request(
        "https://api.groq.com/openai/v1/chat/completions", data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": "LearnSync/1.0"}, method="POST",
    )
    try:
        with urlopen(groq_request, timeout=60) as response:
            content = json.loads(response.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()
    except HTTPError as error:
        raise HTTPException(status_code=502, detail="Quiz generation provider rejected the request.") from error
    except (URLError, KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=502, detail="Quiz generation provider returned an invalid response.") from error

    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        generated = json.loads(content)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=502, detail="Quiz generation provider did not return valid JSON.") from error
    if not isinstance(generated, list) or len(generated) != sum(item["count"] for item in plan):
        raise HTTPException(status_code=502, detail="Quiz generation provider returned an incomplete draft. Please generate again.")

    points_by_type = {item["type"]: item["points"] for item in plan}
    expected_counts = Counter({item["type"]: item["count"] for item in plan})
    questions = []
    for order, item in enumerate(generated, start=1):
        if not isinstance(item, dict):
            raise HTTPException(status_code=502, detail="Quiz generation provider returned an invalid question.")
        question_type = str(item.get("question_type", "")).lower().strip()
        choices = [str(choice).strip() for choice in (item.get("choices") or [])]
        correct_answer = str(item.get("correct_answer") or "").strip()
        if question_type not in points_by_type or not str(item.get("question_text") or "").strip():
            raise HTTPException(status_code=502, detail="Quiz generation provider returned an invalid question type.")
        if question_type == "multiple_choice" and (len(choices) != 4 or correct_answer not in choices):
            raise HTTPException(status_code=502, detail="Quiz generation provider returned an invalid multiple-choice question.")
        if question_type == "true_false" and (choices != ["True", "False"] or correct_answer not in choices):
            raise HTTPException(status_code=502, detail="Quiz generation provider returned an invalid true/false question.")
        questions.append({
            "question_text": str(item["question_text"]).strip(), "question_type": question_type,
            "choices": choices, "correct_answer": correct_answer,
            "points": points_by_type[question_type], "display_order": order,
            "explanation": str(item.get("explanation") or "").strip(),
        })
    if Counter(question["question_type"] for question in questions) != expected_counts:
        raise HTTPException(status_code=502, detail="Quiz generation provider did not follow the requested question mix. Please generate again.")
    return questions


@quiz_router.post("/generate-draft")
def generate_draft(request: QuizDraftRequest):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        _class_exists(cur, request.class_id)
        if not request.module_id:
            raise HTTPException(status_code=422, detail="Select a source module before generating a quiz.")
        cur.execute("SELECT title FROM module WHERE module_id = %s AND class_id = %s", (request.module_id, request.class_id))
        module = cur.fetchone()
        if not module:
            raise HTTPException(status_code=404, detail="The selected module does not belong to this class.")
        cur.execute("SELECT text FROM module_content WHERE module_id = %s ORDER BY chunk_index LIMIT 12", (request.module_id,))
        context = "\n".join(row["text"] for row in cur.fetchall()).strip()
        if not context:
            raise HTTPException(status_code=422, detail="The selected module has no extracted lesson content yet.")
        plan = _question_plan(request)
        return {
            "title": request.title,
            "description": request.learning_outcomes or f"{request.difficulty.title()} quiz based on {module['title']}.",
            "context_used": True,
            "questions": _generate_questions_with_ai(request, module["title"], context, plan),
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
        if request.module_id:
            cur.execute("SELECT 1 FROM module WHERE module_id = %s AND class_id = %s", (request.module_id, request.class_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="The selected module does not belong to this class.")
        for question in request.questions:
            if question.question_type not in SUPPORTED_QUESTION_TYPES or not question.question_text.strip() or question.points <= 0:
                raise HTTPException(status_code=422, detail="Each question needs supported type, text, and positive points.")
            if question.question_type == "multiple_choice" and (len(question.choices) != 4 or question.correct_answer not in question.choices):
                raise HTTPException(status_code=422, detail="Multiple-choice questions need four choices and a matching correct answer.")
            if question.question_type == "true_false" and (question.choices != ["True", "False"] or question.correct_answer not in question.choices):
                raise HTTPException(status_code=422, detail="True/false questions need True and False choices and a matching correct answer.")
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


@quiz_router.delete("/{quiz_id}")
def delete_quiz(quiz_id: int):
    """Delete a quiz and its dependent delivery data as one transaction."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT quiz_id FROM quiz WHERE quiz_id = %s", (quiz_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Quiz not found.")

        # Some existing databases predate cascading foreign keys, so remove known
        # dependent records explicitly before removing the quiz itself.
        cur.execute("DELETE FROM student_answer WHERE quiz_id = %s", (quiz_id,))
        cur.execute("DELETE FROM quiz_score WHERE quiz_id = %s", (quiz_id,))
        cur.execute("DELETE FROM quiz_sections WHERE quiz_id = %s", (quiz_id,))
        cur.execute("DELETE FROM question WHERE quiz_id = %s", (quiz_id,))
        cur.execute("DELETE FROM quiz WHERE quiz_id = %s", (quiz_id,))
        conn.commit()
        return {"deleted": True, "quiz_id": quiz_id}
    except psycopg2.Error as error:
        conn.rollback()
        raise HTTPException(status_code=500, detail="Unable to delete quiz.") from error
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
