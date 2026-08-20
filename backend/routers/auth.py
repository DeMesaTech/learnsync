"""Authentication endpoints"""
from fastapi import APIRouter, HTTPException
import psycopg2
from psycopg2.extras import RealDictCursor

from models import LoginRequest, LoginResponse, UserProfileResponse
from db import get_db_connection
from utils import verify_password

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


@auth_router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    LOGIN FLOW:
    1. User submits form with email & password
    2. Backend queries User table by email
    3. Backend verifies password hash
    4. Returns user_id, role, and name to frontend
    5. Frontend stores in session/localStorage and redirects
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
            # Query user by email; the stored role determines the dashboard.
        cur.execute(
                'SELECT user_id, email, password, role, name FROM account WHERE email = %s',
                (request.email,)
        )
        user = cur.fetchone()
        
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        # Verify password
        if not verify_password(request.password, user['password']):
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password"
            )
        
        # Successful login
        teacher_id = None
        student_id = None
        if user['role'] == 'teacher':
            # try to fetch employee_id from teacher table
            cur.execute('SELECT employee_id FROM teacher WHERE user_id = %s', (user['user_id'],))
            t = cur.fetchone()
            if t:
                teacher_id = t.get('employee_id')
        elif user['role'] == 'student':
            # try to fetch employee_id from student table
            cur.execute('SELECT student_id FROM student WHERE user_id = %s', (user['user_id'],))
            s = cur.fetchone()
            if s:
                student_id = s.get('student_id')

        return LoginResponse(
            success=True,
            message=f"Welcome back, {user['name']}!",
            user_id=user['user_id'],
            role=user['role'],
            name=user['name'],
            teacher_id=teacher_id,
            student_id=student_id
        )
        
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()


@auth_router.get("/user/{user_id}", response_model=UserProfileResponse)
async def get_user_profile(user_id: int):
    """Return basic profile info for a user, including student details when available."""
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get user info
        cur.execute(
            'SELECT user_id, name, email, role FROM account WHERE user_id = %s',
            (user_id,)
        )
        user = cur.fetchone()
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get student details if user is student
        student_number = None
        
        if user['role'] == 'student':
            cur.execute(
                'SELECT student_id FROM Student WHERE user_id = %s',
                (user_id,)
            )
            student = cur.fetchone()
            if student:
                student_number = str(student.get('student_id')) if student.get('student_id') else None
        elif user['role'] == 'teacher':
            cur.execute(
                'SELECT employee_id FROM Teacher WHERE user_id = %s',
                (user_id,)
            )
            teacher = cur.fetchone()
            if teacher:
                employee_id = str(teacher.get('employee_id')) if teacher.get('employee_id') else None

        return UserProfileResponse(
            user_id=user['user_id'],
            name=user['name'],
            email=user['email'],
            role=user['role'],
            student_number=student_number,
            employee_id=employee_id
        )

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()


@auth_router.get("/health")
async def health_check():
    """Check if backend is running"""
    return {"status": "Backend is running"}
