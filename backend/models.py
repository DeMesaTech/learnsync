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
    classes_count: int
    student_count: int
    submission_count: int
    quiz_count: int

# ============= CLASS MODELS =============
class CreateClassRequest(BaseModel):
    teacher_id: int
    class_name: str
    subject_code: str
    schedule: str  # "MWF 9:00-10:00"
    room_number: str
    semester: str


class ClassResponse(BaseModel):
    class_id: int
    class_name: str
    subject_code: str
    teacher_id: int
    teacher_name: str
    schedule: str
    room_number: str
    semester: str
    created_at: datetime
