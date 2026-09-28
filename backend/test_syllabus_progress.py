import unittest

from routers.subjects import _apply_module_coverage


class ModuleCoverageTests(unittest.TestCase):
    def test_reports_full_coverage_for_assigned_chapters(self):
        topics = [
            {"module_assigned": True},
            {"module_assigned": False},
        ]

        self.assertEqual(_apply_module_coverage(topics), (1, 50))
        self.assertEqual(
            [topic["module_completion_percent"] for topic in topics],
            [100, 0],
        )

    def test_empty_syllabus_has_zero_coverage(self):
        self.assertEqual(_apply_module_coverage([]), (0, 0))


if __name__ == "__main__":
    unittest.main()
