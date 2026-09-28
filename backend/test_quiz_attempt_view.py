"""A submitted student's quiz view shows the persisted answer count."""

import unittest
from unittest.mock import MagicMock, patch

from routers.quizzes import get_quiz


class QuizAttemptViewTests(unittest.TestCase):
    @patch("routers.quizzes._assert_student_quiz_access")
    @patch("routers.quizzes._quiz_payload")
    @patch("routers.quizzes.get_db_connection")
    def test_submitted_view_reports_saved_answers(self, connect, payload, access):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [
            {"attempt_count": 1},
            {"answered_count": 4},
        ]
        connect.return_value.cursor.return_value = cursor
        payload.return_value = {"status": "Published", "max_attempts": 1}

        quiz = get_quiz(10, student_id=5)

        self.assertFalse(quiz["can_attempt"])
        self.assertEqual(quiz["answered_count"], 4)
        access.assert_called_once_with(cursor, 10, 5)


if __name__ == "__main__":
    unittest.main()
