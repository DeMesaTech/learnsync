"""Database connection and helper functions"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException

from sqlalchemy import create_engine

# ============= DATABASE CONFIGURATION =============

DATABASE_URL = os.getenv(
    "postgresql://lms_72tg_user:YD3IiTezojIHU6gcqkFUB5yybZ0QsTcF@dpg-d8j1725ckfvc73caogk0-a/lms_72tg")
engine = create_engine(DATABASE_URL, echo=True)

DB_CONFIG = {
    "host": "localhost",
    "database": "lms",
    "user": "postgres",
    "password": "logiclab",
    "port": "5432"
}


def get_db_connection():
    """Create and return a PostgreSQL database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"[DB ERROR] Connection failed: {e}")
        raise HTTPException(
            status_code=500,
            detail="Database connection failed"
        )


def execute_query(sql: str, params: tuple = None, fetch_one=False):
    """
    Execute a query and return results (reduces boilerplate)
    
    Args:
        sql: SQL query string
        params: Tuple of parameters for parameterized query
        fetch_one: If True, returns one row; if False, returns all rows
    
    Returns:
        Single row dict or list of dicts
    """
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params or ())
        
        if fetch_one:
            result = cur.fetchone()
        else:
            result = cur.fetchall()
        
        conn.commit()
        return result
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cur.close()
        conn.close()
