"""
LearnSync Backend - FastAPI Application
Organized modular structure with routers, models, and database helpers
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

# Import routers
from routers.auth import auth_router
from routers.classes import classes_router
from routers.subjects import subject_router

# ============= APP INITIALIZATION =============
app = FastAPI(
    title="LearnSync API",
    description="Backend for LearnSync - AI-assisted LMS",
    version="1.0.0"
)


# ============= CORS CONFIGURATION =============
origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============= INCLUDE ROUTERS =============
app.include_router(auth_router)
app.include_router(classes_router)
app.include_router(subject_router)


# ============= SERVE STATIC FILES =============
BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR.parent / "static"      # or "static" if your folder is lowercase
UPLOADS_DIR = BASE_DIR / "uploads"

print(STATIC_DIR)
print(UPLOADS_DIR)

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=True)