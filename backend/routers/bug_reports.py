"""Bug report submission and admin review endpoints."""

from typing import Literal

import psycopg2
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from psycopg2.extras import RealDictCursor

from db import get_db_connection


bug_reports_router = APIRouter(prefix="/api/bug-reports", tags=["bug-reports"])


class BugReportCreate(BaseModel):
    reporter_user_id: int = Field(gt=0)
    issue_type: Literal[
        "Bug / Error",
        "Feature Request",
        "UI / Design Problem",
        "Performance Issue",
        "Other",
    ]
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)


class BugReportStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved"]


def ensure_bug_reports_table(conn):
    cur = conn.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bug_report (
                report_id bigserial PRIMARY KEY,
                reporter_user_id integer REFERENCES account(user_id) ON DELETE SET NULL,
                reporter_name varchar(100) NOT NULL,
                reporter_email varchar(100) NOT NULL,
                reporter_role varchar(20) NOT NULL CHECK (reporter_role IN ('student', 'teacher')),
                issue_type varchar(50) NOT NULL,
                subject varchar(200) NOT NULL,
                description text NOT NULL,
                status varchar(20) NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'in_progress', 'resolved')),
                created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()
    finally:
        cur.close()


def assert_admin(cur, admin_user_id: int):
    cur.execute(
        "SELECT 1 FROM account WHERE user_id = %s AND role = 'admin'",
        (admin_user_id,),
    )
    if not cur.fetchone():
        raise HTTPException(status_code=403, detail="Administrator access required.")


@bug_reports_router.post("", status_code=201)
async def create_bug_report(payload: BugReportCreate):
    subject = payload.subject.strip()
    description = payload.description.strip()
    if not subject or not description:
        raise HTTPException(status_code=422, detail="Subject and description are required.")

    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        ensure_bug_reports_table(conn)
        cur.execute(
            """
            SELECT user_id, COALESCE(NULLIF(BTRIM(name), ''), email) AS name, email, role
            FROM account
            WHERE user_id = %s AND role IN ('student', 'teacher')
            """,
            (payload.reporter_user_id,),
        )
        reporter = cur.fetchone()
        if not reporter:
            raise HTTPException(status_code=403, detail="A student or teacher account is required to submit a report.")

        cur.execute(
            """
            INSERT INTO bug_report
                (reporter_user_id, reporter_name, reporter_email, reporter_role,
                 issue_type, subject, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING report_id, status, created_at
            """,
            (
                reporter["user_id"],
                reporter["name"],
                reporter["email"],
                reporter["role"],
                payload.issue_type,
                subject,
                description,
            ),
        )
        report = cur.fetchone()
        conn.commit()
        return dict(report)
    except HTTPException:
        conn.rollback()
        raise
    except psycopg2.Error as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        cur.close()
        conn.close()


@bug_reports_router.get("/admin")
async def list_bug_reports(admin_user_id: int = Query(..., gt=0)):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        ensure_bug_reports_table(conn)
        assert_admin(cur, admin_user_id)
        cur.execute(
            """
            SELECT report_id, reporter_user_id, reporter_name, reporter_email,
                   reporter_role, issue_type, subject, description, status,
                   created_at, updated_at
            FROM bug_report
            ORDER BY created_at DESC, report_id DESC
            """
        )
        return [dict(row) for row in cur.fetchall()]
    except HTTPException:
        conn.rollback()
        raise
    except psycopg2.Error as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        cur.close()
        conn.close()


@bug_reports_router.patch("/admin/{report_id}/status")
async def update_bug_report_status(
    report_id: int,
    payload: BugReportStatusUpdate,
    admin_user_id: int = Query(..., gt=0),
):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    try:
        ensure_bug_reports_table(conn)
        assert_admin(cur, admin_user_id)
        cur.execute(
            """
            UPDATE bug_report
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE report_id = %s
            RETURNING report_id, status, updated_at
            """,
            (payload.status, report_id),
        )
        report = cur.fetchone()
        if not report:
            raise HTTPException(status_code=404, detail="Bug report not found.")
        conn.commit()
        return dict(report)
    except HTTPException:
        conn.rollback()
        raise
    except psycopg2.Error as exc:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}")
    finally:
        cur.close()
        conn.close()