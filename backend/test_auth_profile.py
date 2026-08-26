import asyncio
import unittest
from unittest.mock import patch

from routers.auth import get_user_profile


class FakeCursor:
    def __init__(self):
        self._rows = []

    def execute(self, sql, params=()):
        sql_norm = sql.strip()
        if sql_norm.startswith('SELECT user_id, name, email, role FROM account WHERE user_id = %s'):
            self._rows = [
                {
                    'user_id': 5,
                    'name': 'Jane Student',
                    'email': 'jane@example.com',
                    'role': 'student',
                }
            ]
        elif 'STRING_AGG(DISTINCT sec.section' in sql_norm:
            self._rows = [{'student_id': 42, 'grade_level': '2nd Year - A'}]
        else:
            self._rows = []

    def fetchone(self):
        if not self._rows:
            return None
        return self._rows.pop(0)

    def close(self):
        pass


class FakeConn:
    def cursor(self, cursor_factory=None):
        return FakeCursor()

    def close(self):
        pass


class StudentProfileTests(unittest.TestCase):
    def test_student_profile_includes_student_details(self):
        with patch('routers.auth.get_db_connection', return_value=FakeConn()):
            result = asyncio.run(get_user_profile(5))

        self.assertEqual(result.user_id, 5)
        self.assertEqual(result.name, 'Jane Student')
        self.assertEqual(result.role, 'student')
        self.assertEqual(result.student_number, '42')
        self.assertEqual(result.grade_level, '2nd Year - A')
        self.assertIsNone(result.employee_id)


if __name__ == '__main__':
    unittest.main()
