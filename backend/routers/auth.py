"""Authentication endpoints"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

from models import LoginRequest, SignupRequest, LoginResponse, UserProfileResponse
from db import get_db_connection
from utils import hash_password, verify_password

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
        
        # Query user by email and role
        cur.execute(
            'SELECT user_id, email, password, role, name FROM "User" WHERE email = %s AND role = %s',
            (request.email, request.role)
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
        return LoginResponse(
            success=True,
            message=f"Welcome back, {user['name']}!",
            user_id=user['user_id'],
            role=user['role'],
            name=user['name']
        )
        
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()


@auth_router.post("/signup", response_model=LoginResponse)
async def signup(request: SignupRequest):
    """
    SIGNUP FLOW:
    1. User submits form with all details
    2. Backend validates email doesn't exist
    3. Backend hashes password
    4. Backend inserts new User record
    5. Backend creates Student/Teacher record linked to User
    6. Returns success message to frontend
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if email already exists
        cur.execute('SELECT user_id FROM "User" WHERE email = %s', (request.email,))
        if cur.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Email already registered"
            )
        
        # Hash password
        hashed_password = hash_password(request.password)
        full_name = f"{request.firstName} {request.middleName} {request.lastName}"
        
        # Insert new user
        cur.execute(
            '''INSERT INTO "User" (email, name, password, role, created_at)
               VALUES (%s, %s, %s, %s, %s)
               RETURNING user_id''',
            (request.email, full_name, hashed_password, request.role, datetime.now())
        )
        user_id = cur.fetchone()['user_id']
        
        # Create Student or Teacher record
        if request.role == 'student':
            cur.execute(
                'INSERT INTO student (user_id, student_id) VALUES (%s, %s)',
                (user_id, request.idNumber)
            )
        elif request.role == 'teacher':
            cur.execute(
                'INSERT INTO teacher (user_id) VALUES (%s)',
                (user_id,)
            )
        
        conn.commit()
        
        return LoginResponse(
            success=True,
            message="Account created successfully! You can now log in.",
            user_id=user_id,
            role=request.role,
            name=full_name
        )
        
    except psycopg2.Error as e:
        conn.rollback()
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
            'SELECT user_id, name, email, role FROM "User" WHERE user_id = %s',
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

        return UserProfileResponse(
            user_id=user['user_id'],
            name=user['name'],
            email=user['email'],
            role=user['role'],
            student_number=student_number,
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
