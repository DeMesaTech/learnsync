"""Initialize or update a LearnSync PostgreSQL database without Docker.

The target database must exist. Each additive file is applied in its own
transaction and recorded only after it succeeds. Data repairs are excluded.
"""

import hashlib
from pathlib import Path

import psycopg2

from db import DATABASE_URL, DB_CONFIG


SCHEMA_FILES = (
    "quiz_schema.sql",
    "syllabus_progress_schema.sql",
    "grading_schema.sql",
    "academic_schema.sql",
    "program_enrollment_schema.sql",
)
SCHEMA_DIR = Path(__file__).resolve().parent
BASE_SCHEMA = SCHEMA_DIR.parent / "learnsync.sql"
LOCK_ID = 745129061  # Keep concurrent migrators from applying the same file twice.


def migrate():
    """Initialize the base schema if needed, then apply pending schema files."""
    base_sql = BASE_SCHEMA.read_text(encoding="utf-8-sig")
    migrations = [
        (name, SCHEMA_DIR.joinpath(name).read_bytes()) for name in SCHEMA_FILES
    ]
    conn = psycopg2.connect(DATABASE_URL) if DATABASE_URL else psycopg2.connect(**DB_CONFIG)
    applied = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            cur.execute("SELECT to_regclass('public.account')")
            if cur.fetchone()[0] is None:
                cur.execute(base_sql)
                applied.append("learnsync.sql")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    filename text PRIMARY KEY,
                    sha256 text NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
            """)
        conn.commit()

        for name, sql_bytes in migrations:
            checksum = hashlib.sha256(sql_bytes).hexdigest()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT sha256 FROM public.schema_migrations WHERE filename = %s",
                        (name,),
                    )
                    row = cur.fetchone()
                    if row:
                        if row[0] != checksum:
                            raise RuntimeError(
                                f"{name} changed after it was applied; add a new migration file instead."
                            )
                        conn.commit()
                        continue
                    cur.execute(sql_bytes.decode("utf-8-sig"))
                    cur.execute(
                        "INSERT INTO public.schema_migrations (filename, sha256) VALUES (%s, %s)",
                        (name, checksum),
                    )
                conn.commit()
                applied.append(name)
            except Exception as exc:
                conn.rollback()
                raise RuntimeError(f"Migration {name} failed: {exc}") from exc
        return applied
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    changed = migrate()
    print("Applied: " + ", ".join(changed) if changed else "Schema is up to date.")
