from app.services.question_bank import QuestionBankService


class TestQuestionBankService:
    def test_load_questions(self, temp_question_file: str) -> None:
        qs = QuestionBankService(data_path=temp_question_file)
        assert qs.total_count == 4

    def test_select_question(self, temp_question_file: str) -> None:
        qs = QuestionBankService(data_path=temp_question_file)
        qs.set_initial_difficulty("junior")
        q = qs.select_question()
        assert q is not None
        assert q.difficulty == "junior"

    def test_no_repeat_questions(self, temp_question_file: str) -> None:
        qs = QuestionBankService(data_path=temp_question_file)
        selected = []
        while qs.has_more_questions():
            q = qs.select_question()
            if q is None:
                break
            selected.append(q.question_text)

        # All should be unique
        assert len(selected) == len(set(selected))

    def test_select_question_exhausts(self, temp_question_file: str) -> None:
        qs = QuestionBankService(data_path=temp_question_file)
        # Select all 4 questions
        for _ in range(4):
            qs.select_question()
        assert qs.has_more_questions() is False
        assert qs.select_question() is None

    def test_adaptive_difficulty_up(self, temp_question_file: str) -> None:
        qs = QuestionBankService(data_path=temp_question_file)
        qs.set_initial_difficulty("junior")
        assert qs.current_difficulty == "junior"
        qs.update_difficulty(4)
        qs.update_difficulty(4)
        assert qs.current_difficulty == "mid"
        qs.update_difficulty(5)
        qs.update_difficulty(5)
        assert qs.current_difficulty == "senior"

    def test_adaptive_difficulty_down(self, temp_question_file: str) -> None:
        qs = QuestionBankService(data_path=temp_question_file)
        qs.set_initial_difficulty("senior")
        qs.update_difficulty(2)
        qs.update_difficulty(1)
        assert qs.current_difficulty == "mid"
        qs.update_difficulty(2)
        qs.update_difficulty(2)
        assert qs.current_difficulty == "junior"

    def test_adaptive_difficulty_stays_at_bounds(self, temp_question_file: str) -> None:
        qs = QuestionBankService(data_path=temp_question_file)
        qs.set_initial_difficulty("junior")
        qs.update_difficulty(2)
        qs.update_difficulty(1)
        assert qs.current_difficulty == "junior"  # Can't go below junior

    def test_difficulty_reset_by_mixed_scores(self, temp_question_file: str) -> None:
        qs = QuestionBankService(data_path=temp_question_file)
        qs.set_initial_difficulty("mid")
        qs.update_difficulty(4)
        qs.update_difficulty(3)  # Neutral score resets the streak
        qs.update_difficulty(4)
        assert qs.current_difficulty == "mid"  # Not enough consecutive good scores

    def test_filter_by_category(self, temp_question_file: str) -> None:
        qs = QuestionBankService(data_path=temp_question_file)
        q = qs.select_question(category="frontend")
        assert q is not None
        assert q.category == "frontend"

    def test_set_initial_difficulty(self, temp_question_file: str) -> None:
        qs = QuestionBankService(data_path=temp_question_file)
        qs.set_initial_difficulty("senior")
        assert qs.current_difficulty == "senior"
        q = qs.select_question()
        assert q is not None
        assert q.difficulty == "senior"

    def test_reset(self, temp_question_file: str) -> None:
        qs = QuestionBankService(data_path=temp_question_file)
        qs.select_question()
        qs.select_question()
        assert qs.used_count == 2
        qs.reset()
        assert qs.used_count == 0
        assert qs.current_difficulty == "junior"
