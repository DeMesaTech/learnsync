"""Database connection and helper functions"""
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException

from local_env import load_local_env


# ============= DATABASE CONFIGURATION =============
load_local_env()
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "dpg-datgqc093c1s73ai0gog-a"),
    "database": os.getenv("DB_NAME", "lms_nivi"),
    "user": os.getenv("DB_USER", "logiclab"),
    "password": os.getenv("DB_PASSWORD", "9Ea2XuAeV6YyPdUxHIkVDOA04F926xBX"),
    "port": os.getenv("DB_PORT", "5432"),
}
DATABASE_URL = os.getenv("postgresql://logiclab:9Ea2XuAeV6YyPdUxHIkVDOA04F926xBX@dpg-datgqc093c1s73ai0gog-a/lms_nivi")


def get_db_connection():
    """Create and return a PostgreSQL database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG) if not DATABASE_URL else psycopg2.connect(DATABASE_URL)
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
