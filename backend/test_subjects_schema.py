import unittest

from routers.subjects import ensure_syllabus_progress_tables


class FakeCursor:
    def __init__(self):
        self.sql_calls = []

    def execute(self, sql, params=()):
        self.sql_calls.append((sql, params))

    def close(self):
        pass


class FakeConn:
    def __init__(self):
        self.cursor_obj = FakeCursor()

    def cursor(self, cursor_factory=None):
        return self.cursor_obj

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


class EnsureSyllabusTablesTests(unittest.TestCase):
    def test_ensure_syllabus_progress_tables_repairs_missing_columns(self):
        conn = FakeConn()

        ensure_syllabus_progress_tables(conn)

        executed_sql = [sql for sql, _ in conn.cursor_obj.sql_calls]
        combined_sql = "\n".join(executed_sql)

        self.assertIn('ALTER TABLE IF EXISTS public.syllabus_topic ADD COLUMN IF NOT EXISTS display_order', combined_sql)
        self.assertIn('ALTER TABLE IF EXISTS public.module ADD COLUMN IF NOT EXISTS topic_id', combined_sql)
        self.assertIn('CREATE TABLE IF NOT EXISTS public.syllabus_topic', combined_sql)


if __name__ == '__main__':
    unittest.main()
