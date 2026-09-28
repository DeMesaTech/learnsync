import asyncio
import unittest
from unittest.mock import patch

from routers.subjects import delete_activity, delete_module


class FakeCursor:
    def __init__(self, record_id):
        self.record_id = record_id
        self.statements = []
        self.last_statement = ""

    def execute(self, sql, params=()):
        self.last_statement = " ".join(sql.split())
        self.statements.append(self.last_statement)

    def fetchone(self):
        if "RETURNING module_id" in self.last_statement or "RETURNING activity_id" in self.last_statement:
            return (self.record_id,)
        return None

    def close(self):
        pass


class FakeConnection:
    def __init__(self, record_id):
        self.cursor_instance = FakeCursor(record_id)
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class DeleteManagementTests(unittest.TestCase):
    def test_module_delete_clears_dependent_references_first(self):
        connection = FakeConnection(7)
        with patch("routers.subjects.get_db_connection", return_value=connection):
            result = asyncio.run(delete_module(7))

        statements = connection.cursor_instance.statements
        delete_module_statement = "DELETE FROM module WHERE module_id = %s RETURNING module_id"
        self.assertEqual(result, {"module_id": 7})
        self.assertLess(
            statements.index("UPDATE quiz SET module_id = NULL WHERE module_id = %s"),
            statements.index(delete_module_statement),
        )
        self.assertTrue(any(statement.startswith("DELETE FROM query_context") for statement in statements))
        self.assertTrue(connection.committed)

    def test_activity_delete_removes_submissions_before_activity(self):
        connection = FakeConnection(9)
        with patch("routers.subjects.get_db_connection", return_value=connection):
            result = asyncio.run(delete_activity(9))

        statements = connection.cursor_instance.statements
        delete_activity_statement = "DELETE FROM activity WHERE activity_id = %s RETURNING activity_id"
        self.assertEqual(result, {"activity_id": 9})
        self.assertLess(
            statements.index("DELETE FROM act_submission WHERE activity_id = %s"),
            statements.index(delete_activity_statement),
        )
        self.assertTrue(connection.committed)


if __name__ == "__main__":
    unittest.main()
