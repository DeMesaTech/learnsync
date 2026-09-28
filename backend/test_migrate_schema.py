"""Transaction and rerun checks for the schema migrator."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import migrate_schema


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.result = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def execute(self, sql, params=None):
        if "to_regclass" in sql:
            self.result = ("account" if self.conn.base_installed else None,)
        elif "SELECT sha256" in sql:
            checksum = self.conn.recorded.get(params[0])
            self.result = (checksum,) if checksum else None
        elif "INSERT INTO public.schema_migrations" in sql:
            self.conn.pending[params[0]] = params[1]
        elif sql == "FAIL":
            raise ValueError("bad SQL")
        elif sql == "BASE":
            self.conn.base_installed = True
            self.conn.executed.append(sql)
        elif sql in {"FIRST", "SECOND"}:
            self.conn.executed.append(sql)

    def fetchone(self):
        return self.result


class FakeConnection:
    def __init__(self):
        self.recorded = {}
        self.pending = {}
        self.executed = []
        self.rollbacks = 0
        self.base_installed = True

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.recorded.update(self.pending)
        self.pending.clear()

    def rollback(self):
        self.pending.clear()
        self.rollbacks += 1

    def close(self):
        pass


class SchemaMigrationTests(unittest.TestCase):
    def test_initializes_empty_database_before_additive_files(self):
        conn = FakeConnection()
        conn.base_installed = False
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "base.sql").write_text("BASE", encoding="utf-8")
            (path / "one.sql").write_text("FIRST", encoding="utf-8")
            with patch.object(migrate_schema, "BASE_SCHEMA", path / "base.sql"), \
                 patch.object(migrate_schema, "SCHEMA_DIR", path), \
                 patch.object(migrate_schema, "SCHEMA_FILES", ("one.sql",)), \
                 patch.object(migrate_schema.psycopg2, "connect", return_value=conn):
                self.assertEqual(migrate_schema.migrate(), ["learnsync.sql", "one.sql"])
        self.assertEqual(conn.executed, ["BASE", "FIRST"])

    def test_applies_in_order_and_skips_recorded_files(self):
        conn = FakeConnection()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "one.sql").write_text("FIRST", encoding="utf-8")
            (path / "two.sql").write_text("SECOND", encoding="utf-8")
            with patch.object(migrate_schema, "SCHEMA_DIR", path), \
                 patch.object(migrate_schema, "SCHEMA_FILES", ("one.sql", "two.sql")), \
                 patch.object(migrate_schema.psycopg2, "connect", return_value=conn):
                self.assertEqual(migrate_schema.migrate(), ["one.sql", "two.sql"])
                self.assertEqual(migrate_schema.migrate(), [])
        self.assertEqual(conn.executed, ["FIRST", "SECOND"])
        self.assertEqual(set(conn.recorded), {"one.sql", "two.sql"})

    def test_failed_file_is_not_recorded(self):
        conn = FakeConnection()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "one.sql").write_text("FIRST", encoding="utf-8")
            (path / "two.sql").write_text("FAIL", encoding="utf-8")
            with patch.object(migrate_schema, "SCHEMA_DIR", path), \
                 patch.object(migrate_schema, "SCHEMA_FILES", ("one.sql", "two.sql")), \
                 patch.object(migrate_schema.psycopg2, "connect", return_value=conn):
                with self.assertRaisesRegex(RuntimeError, "Migration two.sql failed"):
                    migrate_schema.migrate()
        self.assertEqual(set(conn.recorded), {"one.sql"})
        self.assertGreater(conn.rollbacks, 0)


if __name__ == "__main__":
    unittest.main()
