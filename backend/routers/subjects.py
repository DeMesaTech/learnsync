from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body, UploadFile
import psycopg2
import json 
import os
from psycopg2.extras import RealDictCursor

#from models import 
from db import get_db_connection

subject_router = APIRouter(prefix="/api/subjects", tags=["subjects"])
# ===========================================================

# Enroll students into a specific class
@subject_router.post("/{class_id}/enroll")
async def enroll_students(class_id: str, payload: dict = Body(...)):
    """Enroll a list of student IDs into the given class_id.

    Expects JSON: { "student_ids": [123, 456, ...] }
    """
    student_ids = payload.get('student_ids')
    if not isinstance(student_ids, list):
        raise HTTPException(status_code=400, detail="student_ids must be a list of integers")

    conn = get_db_connection()
    try:
        cur = conn.cursor()
        enrolled = 0
        for sid in student_ids:
            try:
                sid_int = int(sid)
            except Exception:
                continue

            # ensure student record exists (insert if missing)
            cur.execute('''INSERT INTO student (student_id) VALUES (%s) ON CONFLICT (student_id) DO NOTHING''', (sid_int,))

            # check existing enrollment
            cur.execute('SELECT 1 FROM enrollment WHERE student_id = %s AND class_id = %s', (sid_int, class_id))
            if not cur.fetchone():
                cur.execute('INSERT INTO enrollment (student_id, class_id) VALUES (%s, %s)', (sid_int, class_id))
                enrolled += 1

        conn.commit()
        return {"enrolled": enrolled}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# ===========================================================

# Upload Module into a specific class
@subject_router.post("/{class_id}/up_module")
async def upload_module(
    class_id: str,
    title: str = Form(...),
    summary: str = Form(""),
    sections: str = Form(...),  # JSON string from frontend
    file: UploadFile = File(...)
):
    """
    Upload Module for the class
    """

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Convert sections back to Python list
        sections_list = json.loads(sections)

        # Save file (example path)
        upload_dir = "uploads/modules"
        os.makedirs(upload_dir, exist_ok=True)

        file_location = f"{upload_dir}/{file.filename}"
        print(f"Received title: {title}, path: {file_location}, summary: {summary}, class_id: {class_id}")
        print(f"Received sections: {sections_list}")

        with open(file_location, "wb") as buffer:
            buffer.write(await file.read())

        # Verify teacher's employee_id currently logged in.
        cursor.execute("SELECT employee_id FROM class WHERE class_id = %s", (class_id,))
        employee_id = cursor.fetchone()
        print(f"Queried employee_id for class_id {class_id}: {employee_id}")

        # Insert into DB
        cursor.execute("""
            INSERT INTO module (employee_id, title, file_path, summary)
            VALUES (%s, %s, %s, %s)
        """, (
            employee_id,
            title,
            file_location,
            summary
        ))

        conn.commit()

        return {
            "message": "Module uploaded successfully",
            "class_id": class_id,
            "file_path": file_location,
            "summary": summary,
            "sections": sections_list
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        cursor.close()
        conn.close()
