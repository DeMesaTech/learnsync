import unittest
from datetime import datetime, timedelta, timezone

from routers.submit import get_submission_status_for_activity


class SubmissionDeadlineTests(unittest.TestCase):
    def test_naive_deadline_is_compared_without_timezone(self):
        future_deadline = datetime.now() + timedelta(days=1)
        past_deadline = datetime.now() - timedelta(days=1)

        self.assertEqual(get_submission_status_for_activity(future_deadline), "Submitted")
        self.assertEqual(get_submission_status_for_activity(past_deadline), "Late")

    def test_aware_deadline_uses_its_timezone(self):
        future_deadline = datetime.now(timezone.utc) + timedelta(days=1)
        past_deadline = datetime.now(timezone.utc) - timedelta(days=1)

        self.assertEqual(get_submission_status_for_activity(future_deadline), "Submitted")
        self.assertEqual(get_submission_status_for_activity(past_deadline), "Late")


if __name__ == "__main__":
    unittest.main()