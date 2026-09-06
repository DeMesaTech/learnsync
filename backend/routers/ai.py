"""AI assistant endpoint backed by Groq and module-content retrieval."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException
import psycopg2
from psycopg2.extras import RealDictCursor

from db import get_db_connection
from models import ChatRequest, ChatResponse

ai_router = APIRouter(prefix="/api/ai", tags=["AI"])

MAX_CONTEXT_CHARS = 6000
MAX_HISTORY_MESSAGES = 6
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"


def retrieve_module_context(student_id: int, module_id: int, question: str) -> tuple[str, str]:
    """Authorize the student and retrieve only the most relevant lesson chunks."""
    conn = get_db_connection()
    cur = None
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT m.title
            FROM module m
            JOIN enrollment e ON e.class_id = m.class_id
            WHERE m.module_id = %s AND e.student_id = %s
            """,
            (module_id, student_id),
        )
        module = cur.fetchone()
        if not module:
            raise HTTPException(status_code=403, detail="You are not enrolled in this lesson.")

        cur.execute(
            """
            SELECT mc.chunk_index, mc.text
            FROM module_content mc
            WHERE mc.module_id = %s
              AND to_tsvector('simple', mc.text) @@ plainto_tsquery('simple', %s)
            ORDER BY ts_rank_cd(
                to_tsvector('simple', mc.text),
                plainto_tsquery('simple', %s)
            ) DESC, mc.chunk_index
            LIMIT 4
            """,
            (module_id, question, question),
        )
        chunks = cur.fetchall()

        if not chunks:
            cur.execute(
                """
                SELECT chunk_index, text
                FROM module_content
                WHERE module_id = %s
                ORDER BY chunk_index
                LIMIT 2
                """,
                (module_id,),
            )
            chunks = cur.fetchall()

        context_parts = []
        remaining_chars = MAX_CONTEXT_CHARS
        for chunk in chunks:
            text = chunk["text"].strip()[:remaining_chars]
            if not text:
                continue
            context_parts.append(f"[Lesson chunk {chunk['chunk_index']}]\n{text}")
            remaining_chars -= len(text)
            if remaining_chars <= 0:
                break

        return module["title"], "\n\n".join(context_parts)
    except psycopg2.Error as error:
        raise HTTPException(status_code=500, detail="Unable to retrieve lesson content.") from error
    finally:
        if cur is not None:
            cur.close()
        conn.close()

@ai_router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured on the backend.",
        )

    clean_messages = [
        {
            "role": message["role"],
            "content": message["content"].strip(),
        }
        for message in request.messages
        if message.get("role") in {"user", "assistant"}
        and message.get("content", "").strip()
    ]
    question = next(
        (message["content"] for message in reversed(clean_messages) if message["role"] == "user"),
        "",
    )
    lesson_title, context = retrieve_module_context(
        request.student_id,
        request.module_id,
        question,
    )
    if not context:
        raise HTTPException(status_code=404, detail="This lesson has no searchable content yet.")

    prompt_messages = [
        {
            "role": "system",
            "content": (
                "You are LearnSync AI, a patient study assistant. "
                "Answer using only the supplied lesson context. "
                "If the context does not contain the answer, say so clearly. "
                "Keep answers concise and useful for a student.\n\n"
                f"Lesson: {lesson_title}\n"
                f"Lesson context:\n{context}"
            ),
        },
        *clean_messages[-MAX_HISTORY_MESSAGES:],
    ]

    requested_model = os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL
    models_to_try = [requested_model]
    if requested_model != DEFAULT_GROQ_MODEL:
        models_to_try.append(DEFAULT_GROQ_MODEL)

    result = None
    for model in models_to_try:
        payload = json.dumps(
            {
                "model": model,
                "messages": prompt_messages,
                "temperature": 0.3,
                "max_tokens": 600,
            }
        ).encode("utf-8")
        groq_request = Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "LearnSync/1.0",
            },
            method="POST",
        )

        try:
            with urlopen(groq_request, timeout=45) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if model == models_to_try[-1] or "model_not_found" not in detail:
                raise HTTPException(status_code=502, detail=f"Groq request failed: {detail}") from error
        except URLError as error:
            raise HTTPException(status_code=502, detail="Unable to reach Groq.") from error

    try:
        reply = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise HTTPException(status_code=502, detail="Groq returned an unexpected response.") from error

    return ChatResponse(reply=reply)
