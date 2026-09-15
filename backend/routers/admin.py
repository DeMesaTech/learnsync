"""Administrator account management endpoints."""
import secrets

import psycopg2
from fastapi import APIRouter, HTTPException
from psycopg2.extras import RealDictCursor

from db import get_db_connection
from models import AdminAccountCreate, AdminAccountResponse, AdminResendResponse
from utils import hash_password


admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


def _account_response(row):
    return AdminAccountResponse(
        user_id=row["user_id"],
        name=row["name"],
        email=row["email"],
        role=row["role"],
        status="active",
        idNumber=str(row["id_number"]) if row.get("id_number") is not None else None,
    )


@admin_router.get("/accounts", response_model=list[AdminAccountResponse])
async def list_accounts():
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT a.user_id, a.name, a.email, a.role,
                   COALESCE(s.student_id, t.employee_id) AS id_number
            FROM account a
            LEFT JOIN student s ON s.user_id = a.user_id
            LEFT JOIN teacher t ON t.user_id = a.user_id
            WHERE a.role IN ('student', 'teacher')
            ORDER BY a.created_at DESC, a.user_id DESC
            """
        )
        return [_account_response(row) for row in cur.fetchall()]
    except psycopg2.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        cur.close()
        conn.close()


@admin_router.post("/accounts", response_model=AdminAccountResponse, status_code=201)
async def create_account(request: AdminAccountCreate):
    if request.role not in {"student", "teacher"}:
        raise HTTPException(status_code=400, detail="Role must be student or teacher")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        temporary_password = secrets.token_urlsafe(12)
        name = f"{request.firstName.strip()} {request.lastName.strip()}".strip()
        cur.execute(
            """
            INSERT INTO account (name, email, password, role)
            VALUES (%s, %s, %s, %s)
            RETURNING user_id, name, email, role
            """,
            (name, request.email, hash_password(temporary_password), request.role),
        )
        account = cur.fetchone()

        if request.role == "student":
            if not request.idNumber or not request.idNumber.isdigit():
                raise HTTPException(status_code=400, detail="A numeric student ID is required")
            cur.execute(
                "INSERT INTO student (student_id, user_id) VALUES (%s, %s)",
                (int(request.idNumber), account["user_id"]),
            )
        else:
            cur.execute(
                "INSERT INTO teacher (user_id) VALUES (%s) RETURNING employee_id",
                (account["user_id"],),
            )
            account["id_number"] = cur.fetchone()["employee_id"]

        conn.commit()
        account["id_number"] = account.get("id_number") or request.idNumber
        return _account_response(account)
    except HTTPException:
        conn.rollback()
        raise
    except psycopg2.IntegrityError:
        conn.rollback()
        raise HTTPException(status_code=409, detail="Email or ID number already exists")
    except psycopg2.Error as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        cur.close()
        conn.close()


@admin_router.post("/accounts/{user_id}/resend", response_model=AdminResendResponse)
async def resend_activation(user_id: int):
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            "SELECT email FROM account WHERE user_id = %s AND role IN ('student', 'teacher')",
            (user_id,),
        )
        account = cur.fetchone()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        return AdminResendResponse(
            message="Activation email queued; configure a mail provider to deliver it.",
            email=account["email"],
        )
    except psycopg2.Error as exc:
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        cur.close()
        conn.close()