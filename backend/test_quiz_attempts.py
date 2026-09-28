import unittest

from routers.quizzes import _can_submit_attempt


class QuizAttemptLimitTests(unittest.TestCase):
    def test_unset_limit_allows_only_first_attempt(self):
        self.assertTrue(_can_submit_attempt(0, None))
        self.assertFalse(_can_submit_attempt(1, None))

    def test_explicit_limit_allows_remaining_attempts(self):
        self.assertTrue(_can_submit_attempt(1, 2))
        self.assertFalse(_can_submit_attempt(2, 2))


if __name__ == "__main__":
    unittest.main()
