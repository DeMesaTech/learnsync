"""Faculty-edited multiple-choice options must remain valid when saved."""

import unittest

from fastapi import HTTPException

from routers.quizzes import QuizQuestionDraft, _validate_saved_question


class QuizChoiceValidationTests(unittest.TestCase):
    def question(self, choices, answer="First"):
        return QuizQuestionDraft(
            question_text="Which option is correct?",
            question_type="multiple_choice",
            choices=choices,
            correct_answer=answer,
        )

    def test_four_distinct_options_with_matching_answer(self):
        _validate_saved_question(self.question(["First", "Second", "Third", "Fourth"]))

    def test_blank_or_duplicate_options_are_rejected(self):
        for choices in (["First", "Second", "", "Fourth"],
                        ["First", "Second", "first", "Fourth"]):
            with self.subTest(choices=choices), self.assertRaises(HTTPException) as error:
                _validate_saved_question(self.question(choices))
            self.assertEqual(error.exception.status_code, 422)

    def test_answer_must_match_an_option(self):
        with self.assertRaises(HTTPException) as error:
            _validate_saved_question(self.question(["First", "Second", "Third", "Fourth"], "Fifth"))
        self.assertEqual(error.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
