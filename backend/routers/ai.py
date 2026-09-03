"""AI assistant endpoint backed by Groq's hosted Llama model."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

ai_router = APIRouter(prefix="/api/ai", tags=["AI"])


class ChatRequest(BaseModel):
    messages: list[dict[str, str]] = Field(min_length=1, max_length=30)


class ChatResponse(BaseModel):
    reply: str


@ai_router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GROQ_API_KEY is not configured on the backend.",
        )

    payload = json.dumps(
        {
            "model": "openai/gpt-oss-20b",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are LearnSync AI, a patient study assistant. "
                        "Give accurate, clear explanations for students. "
                        "When context is missing, ask a focused follow-up question."
                    ),
                },
                *[
                    {
                        "role": message["role"],
                        "content": message["content"].strip(),
                    }
                    for message in request.messages
                    if message.get("role") in {"user", "assistant"}
                    and message.get("content", "").strip()
                ],
            ],
            "temperature": 0.4,
            "max_tokens": 1000,
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
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=502, detail=f"Groq request failed: {detail}") from error
    except URLError as error:
        raise HTTPException(status_code=502, detail="Unable to reach Groq.") from error

    try:
        reply = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise HTTPException(status_code=502, detail="Groq returned an unexpected response.") from error

    return ChatResponse(reply=reply)
