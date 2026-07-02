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

    def test_deterministic_selection_same_seed(self, temp_question_file: str) -> None:
        """Same seed should produce the same question order."""
        seed = "test-seed-abc123"
        qs1 = QuestionBankService(data_path=temp_question_file, seed=seed)
        qs1.set_initial_difficulty("junior")

        qs2 = QuestionBankService(data_path=temp_question_file, seed=seed)
        qs2.set_initial_difficulty("junior")

        seq1 = []
        while qs1.has_more_questions():
            q = qs1.select_question()
            if q is None:
                break
            seq1.append(q.question_text)

        seq2 = []
        while qs2.has_more_questions():
            q = qs2.select_question()
            if q is None:
                break
            seq2.append(q.question_text)

        assert seq1 == seq2

    def test_different_seeds_different_sequences(self, temp_question_file: str) -> None:
        """Different seeds produce different Random instances (structural check)."""
        qs_a = QuestionBankService(data_path=temp_question_file, seed="seed-alpha")
        qs_b = QuestionBankService(data_path=temp_question_file, seed="seed-beta")

        # The internal RNG instances should produce different sequences
        # of random numbers, even if small pools may occasionally collide.
        rng_a_vals = [qs_a._rng.random() for _ in range(5)]
        rng_b_vals = [qs_b._rng.random() for _ in range(5)]
        assert rng_a_vals != rng_b_vals, (
            "Different seeds should produce different RNG streams"
        )

    def test_seed_after_reset_reproduces_sequence(self, temp_question_file: str) -> None:
        """After reset, the same seed reproduces the same order."""
        seed = "reset-test-seed"
        qs = QuestionBankService(data_path=temp_question_file, seed=seed)
        qs.set_initial_difficulty("junior")

        # Pick first two questions
        q1 = qs.select_question()
        q2 = qs.select_question()
        assert q1 is not None and q2 is not None

        # Reset and pick again
        qs.reset()
        qs.set_initial_difficulty("junior")
        q1_again = qs.select_question()
        q2_again = qs.select_question()

        assert q1.question_text == q1_again.question_text
        assert q2.question_text == q2_again.question_text

    def test_no_seed_still_random(self, temp_question_file: str) -> None:
        """Without a seed, the service should still work (random mode)."""
        qs = QuestionBankService(data_path=temp_question_file)
        q = qs.select_question()
        assert q is not None
        assert q.difficulty is not None

    def test_language_is_stored(self, temp_question_file: str) -> None:
        """The language parameter should be stored on the service instance."""
        qs_en = QuestionBankService(data_path=temp_question_file, language="en")
        qs_zh = QuestionBankService(data_path=temp_question_file, language="zh")
        assert qs_en.language == "en"
        assert qs_zh.language == "zh"

    def test_chinese_file_questions_in_chinese(self) -> None:
        """Questions loaded from zh file should have Chinese question_text."""
        from pathlib import Path
        data_dir = Path(__file__).parent.parent / "data"
        zh_path = data_dir / "questions_zh.json"
        if not zh_path.exists():
            return  # skip if file not available

        qs = QuestionBankService(data_path=str(zh_path), language="zh")
        assert qs.total_count > 0
        q = qs.select_question()
        assert q is not None
        # Chinese text should contain CJK characters
        import re
        assert re.search(r'[一-鿿]', q.question_text), (
            f"Expected Chinese characters in question_text, got: {q.question_text[:50]}"
        )

    def test_english_file_questions_in_english(self) -> None:
        """Questions loaded from en file should have English question_text."""
        from pathlib import Path
        data_dir = Path(__file__).parent.parent / "data"
        en_path = data_dir / "questions_en.json"
        if not en_path.exists():
            return  # skip if file not available

        qs = QuestionBankService(data_path=str(en_path), language="en")
        assert qs.total_count > 0
        q = qs.select_question()
        assert q is not None
        # Should be primarily ASCII (English)
        assert q.question_text.isascii() or all(
            ord(c) < 128 for c in q.question_text if c not in '—–''""'
        ), f"Expected English text, got: {q.question_text[:50]}"
