"""Apply the additive academic schema to an existing LearnSync database."""
from pathlib import Path

from db import get_db_connection


def migrate():
    sql = Path(__file__).with_name("academic_schema.sql").read_text(encoding="utf-8")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
    print("Academic schema ready.")
