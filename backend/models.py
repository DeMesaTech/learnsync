"""Pydantic models for request/response validation (like Java POJOs)"""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ============= AUTH MODELS =============
class LoginRequest(BaseModel):
    role: str
    email: str
    password: str

class SignupRequest(BaseModel):
    role: str
    email: str
    firstName: str
    middleName: str
    lastName: str
    idNumber: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[int] = None
    role: Optional[str] = None
    name: Optional[str] = None

class UserProfileResponse(BaseModel):
    user_id: int
    name: str
    email: str
    role: str
    student_number: Optional[str] = None
    grade_level: Optional[str] = None

# ========== TEACHER DASHBOARD ===========
class TeacherDashboardResponse(BaseModel):
    classes_count: int = 0
    student_count: int = 0
    submission_count: int = 0
    quiz_count: int = 0
    module_count: int = 0
    activity_count: int = 0

# ============= CLASS MODELS =============
class CreateClassRequest(BaseModel):
    teacher_id: int
    subject: str
    sections: int
    attendance: float
    quizzes: float
    activities: float
    exam: float


class ClassResponse(BaseModel):
    class_id: int
    subject: str
    section_count: int
    attendance_weight: float
    quizzes_weight: float
    activities_weight: float
    exam_weight: float
    teacher_id: int
    teacher_name: str
    created_at: datetime
