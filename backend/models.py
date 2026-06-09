"""Pydantic models for request/response validation (like Java POJOs)"""
from pydantic import BaseModel, EmailStr
from typing import Dict, Optional
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
    teacher_id: Optional[int] = None
    student_id: Optional[int] = None

class UserProfileResponse(BaseModel):
    user_id: int
    name: str
    email: str
    role: str
    student_number: Optional[str] = None
    grade_level: Optional[str] = None


# ============= CLASS MODELS =============
class CreateClassRequest(BaseModel):
    teacher_id: int
    subject: str
    year: int
    class_code: str
    sections: Dict[str, str]
    attendance: float
    quizzes: float
    activities: float
    exam: float


class ClassResponse(BaseModel):
    class_id: int
    class_code: str
    subject: str
    section_count: int
    attendance_weight: float
    quizzes_weight: float
    activities_weight: float
    exam_weight: float
    teacher_id: int
    teacher_name: str
    
# ========== TEACHER DASHBOARD ===========
class TeacherDashboardResponse(BaseModel):
    teacher_id: Optional[int] = None
    classes_count: int
    student_count: int
    submission_count: int
    quiz_count: int
    module_count: int
    activity_count: int

# ========= STUDENT DASHBOARD ===========
class StudentDashboardResponse(BaseModel):
    student_id: Optional[int] = None
    classes_count: int
    submission_count: int
    quiz_count: int
    module_count: int
    activity_count: int
