"""Tests for the game engine: word handling, letter guessing, scoring, turns.

Task 3 requirements (from the plan):
  1. Correct letter reveals ALL occurrences and scores by scheme.
  2. Incorrect letter passes the turn to the next player.
  3. Repeated letter is ignored (no state change, same object).
  4. Revealing every letter completes the round (phase → round_won).
  5. «ё» is equivalent to «е».
  6. Words with «й», «ъ/ь», and hyphens work correctly.

These tests run WITHOUT Django.
"""

import pytest

from engine.actions import (
    Action,
    InvalidAction,
    apply,
    guess_letter,
    guess_word,
    manual_score,
    skip_turn,
)
from engine.state import GameState, new_game
from engine.words import (
    check_word,
    count_occurrences,
    is_fully_revealed,
    make_mask,
    normalize,
    reveal_letter,
)


# ===================================================================
#  words.py
# ===================================================================


class TestNormalize:
    def test_lowercase(self):
        assert normalize("ДОЛОМИТ") == "доломит"

    def test_yo_to_ye(self):
        assert normalize("МОЛОДЁЖЬ") == "молодежь"

    def test_mixed_case_and_yo(self):
        assert normalize("Ёлка") == "елка"

    def test_already_normalized(self):
        assert normalize("привет") == "привет"

    def test_empty_string(self):
        assert normalize("") == ""


class TestMakeMask:
    def test_all_letters_hidden(self):
        assert make_mask("СЛОВО") == (False, False, False, False, False)

    def test_hyphen_pre_revealed(self):
        # К И Н О - Т Е А Т Р
        mask = make_mask("КИНО-ТЕАТР")
        assert mask == (
            False, False, False, False,
            True,   # hyphen
            False, False, False, False, False,
        )

    def test_space_pre_revealed(self):
        mask = make_mask("ДВА СЛОВА")
        assert mask[3] is True  # the space

    def test_single_letter(self):
        assert make_mask("А") == (False,)


class TestRevealLetter:
    def test_reveals_all_occurrences(self):
        word = "МОЛОКО"
        mask = make_mask(word)
        new = reveal_letter(word, mask, "о")
        #  М  О  Л  О  К  О
        assert new == (False, True, False, True, False, True)

    def test_no_match_unchanged(self):
        word = "СЛОВО"
        mask = make_mask(word)
        assert reveal_letter(word, mask, "а") == mask

    def test_keeps_already_revealed(self):
        word = "МОЛОКО"
        mask = (False, True, False, True, False, True)  # О already open
        after = reveal_letter(word, mask, "м")
        assert after == (True, True, False, True, False, True)


class TestCountOccurrences:
    def test_multiple(self):
        assert count_occurrences("МОЛОКО", "О") == 3

    def test_zero(self):
        assert count_occurrences("МОЛОКО", "А") == 0

    def test_yo_matches_ye(self):
        assert count_occurrences("МОЛОДЁЖЬ", "Е") == 1
        assert count_occurrences("МОЛОДЁЖЬ", "Ё") == 1

    def test_single(self):
        assert count_occurrences("ДОЛОМИТ", "Д") == 1


class TestCheckWord:
    def test_exact_match(self):
        assert check_word("доломит", "ДОЛОМИТ") is True

    def test_yo_equivalence(self):
        assert check_word("молодежь", "МОЛОДЁЖЬ") is True

    def test_mismatch(self):
        assert check_word("гранит", "ДОЛОМИТ") is False


class TestIsFullyRevealed:
    def test_all_true(self):
        assert is_fully_revealed((True, True, True)) is True

    def test_has_false(self):
        assert is_fully_revealed((True, False, True)) is False

    def test_empty(self):
        assert is_fully_revealed(()) is True


# ===================================================================
#  state.py — new_game()
# ===================================================================


class TestNewGame:
    def test_defaults(self):
        s = new_game(word="ДА", players=["Аня"])
        assert s.phase == "await_letter"
        assert s.word == "ДА"
        assert s.mask == (False, False)
        assert s.players == ("Аня",)
        assert s.current_player == 0
        assert s.scores == (0,)
        assert s.guessed_letters == frozenset()
        assert s.version == 0

    def test_accepts_list_of_players(self):
        s = new_game(word="А", players=["X", "Y"])
        assert s.players == ("X", "Y")
        assert s.scores == (0, 0)

    def test_hyphenated_word_mask(self):
        s = new_game(word="КИНО-ТЕАТР", players=["Игрок"])
        assert s.mask[4] is True  # hyphen pre-revealed


# ===================================================================
#  actions.py — apply()
# ===================================================================


@pytest.fixture()
def three_players() -> GameState:
    """ДОЛОМИТ, 3 players, per_occurrence, 100 pts/letter, 500 word bonus."""
    return new_game(
        word="ДОЛОМИТ",
        players=["Анна", "Борис", "Вера"],
        scoring="per_occurrence",
        word_bonus=500,
        sector_value=100,
    )


# ---- 1. Correct letter reveals all & scores -------------------------


class TestCorrectLetter:
    def test_reveals_all_occurrences_and_scores(self, three_players):
        # "О" appears twice in "ДОЛОМИТ" (positions 1, 3)
        result = apply(three_players, guess_letter("о"))

        assert result.mask[1] is True   # first О
        assert result.mask[3] is True   # second О
        assert result.mask[0] is False  # Д still hidden
        assert result.scores[0] == 200  # 100 × 2 occurrences
        assert result.phase == "await_letter"
        assert result.version == three_players.version + 1

    def test_per_letter_scoring(self):
        s = new_game(
            word="МОЛОКО", players=["Игрок"],
            scoring="per_letter", sector_value=100,
        )
        result = apply(s, guess_letter("о"))
        # 3 occurrences, but per_letter → flat 100
        assert result.scores[0] == 100

    def test_per_occurrence_scoring(self):
        s = new_game(
            word="МОЛОКО", players=["Игрок"],
            scoring="per_occurrence", sector_value=100,
        )
        result = apply(s, guess_letter("о"))
        # 3 occurrences × 100 = 300
        assert result.scores[0] == 300

    def test_correct_guess_keeps_current_player(self, three_players):
        result = apply(three_players, guess_letter("д"))
        assert result.current_player == 0

    def test_letter_added_to_guessed(self, three_players):
        result = apply(three_players, guess_letter("Д"))
        assert "д" in result.guessed_letters


# ---- 2. Incorrect letter passes turn --------------------------------


class TestIncorrectLetter:
    def test_passes_turn(self, three_players):
        result = apply(three_players, guess_letter("а"))  # not in ДОЛОМИТ
        assert result.current_player == 1
        assert result.scores[0] == 0
        assert result.version == three_players.version + 1

    def test_turn_wraps_around(self, three_players):
        s = three_players
        s = apply(s, guess_letter("а"))  # 0 → 1
        s = apply(s, guess_letter("б"))  # 1 → 2
        s = apply(s, guess_letter("в"))  # 2 → 0
        assert s.current_player == 0

    def test_miss_added_to_guessed(self, three_players):
        result = apply(three_players, guess_letter("А"))
        assert "а" in result.guessed_letters


# ---- 3. Repeated letter is ignored ----------------------------------


class TestRepeatedLetter:
    def test_returns_exact_same_object(self, three_players):
        s1 = apply(three_players, guess_letter("д"))
        s2 = apply(s1, guess_letter("д"))
        assert s2 is s1

    def test_different_case_still_ignored(self, three_players):
        s1 = apply(three_players, guess_letter("д"))
        s2 = apply(s1, guess_letter("Д"))
        assert s2 is s1

    def test_no_version_bump(self, three_players):
        s1 = apply(three_players, guess_letter("д"))
        s2 = apply(s1, guess_letter("д"))
        assert s2.version == s1.version


# ---- 4. All letters revealed → round_won ----------------------------


class TestRoundCompletion:
    def test_last_letter_completes_round(self):
        s = new_game(word="ДА", players=["Игрок"], sector_value=100)
        s = apply(s, guess_letter("д"))
        assert s.phase == "await_letter"
        s = apply(s, guess_letter("а"))
        assert s.phase == "round_won"
        assert is_fully_revealed(s.mask)

    def test_guess_word_correct_completes_round(self, three_players):
        result = apply(three_players, guess_word(correct=True))
        assert result.phase == "round_won"
        assert all(result.mask)
        assert result.scores[0] == 500  # word_bonus

    def test_guess_word_incorrect_passes_turn(self, three_players):
        result = apply(three_players, guess_word(correct=False))
        assert result.phase == "await_letter"
        assert result.current_player == 1
        assert result.scores[0] == 0


# ---- 5. «ё» / «е» equivalence (Review Focus #1) --------------------


class TestYoEquivalence:
    def test_ye_reveals_yo_in_word(self):
        # Word has ё, player guesses е
        s = new_game(word="МОЛОДЁЖЬ", players=["Игрок"], sector_value=100)
        result = apply(s, guess_letter("е"))
        assert result.mask[5] is True   # position of Ё
        assert result.scores[0] == 100

    def test_yo_reveals_yo_in_word(self):
        # Word has ё, player guesses ё
        s = new_game(word="МОЛОДЁЖЬ", players=["Игрок"], sector_value=100)
        result = apply(s, guess_letter("ё"))
        assert result.mask[5] is True

    def test_yo_not_counted_twice(self):
        # Guessing е then ё must not double-count
        s = new_game(word="МОЛОДЁЖЬ", players=["Игрок"], sector_value=100)
        s = apply(s, guess_letter("е"))
        s2 = apply(s, guess_letter("ё"))
        assert s2 is s  # ё is already covered


# ---- 6. Special characters: й, ъ, ь, hyphen -------------------------


class TestSpecialCharacters:
    def test_word_with_й(self):
        s = new_game(word="ЧАЙНИК", players=["Игрок"], sector_value=100)
        result = apply(s, guess_letter("й"))
        assert result.mask[2] is True   # Й at position 2
        assert result.scores[0] == 100

    def test_word_with_ь(self):
        s = new_game(word="МОЛОДЁЖЬ", players=["Игрок"], sector_value=100)
        result = apply(s, guess_letter("ь"))
        assert result.mask[7] is True   # Ь at last position

    def test_word_with_ъ(self):
        s = new_game(word="ОБЪЕКТ", players=["Игрок"], sector_value=100)
        result = apply(s, guess_letter("ъ"))
        assert result.mask[2] is True   # Ъ at position 2

    def test_hyphenated_word_letters(self):
        s = new_game(word="КИНО-ТЕАТР", players=["Игрок"], sector_value=100)
        assert s.mask[4] is True  # hyphen pre-revealed

        result = apply(s, guess_letter("т"))
        assert result.mask[5] is True   # first Т
        assert result.mask[8] is True   # second Т
        assert result.scores[0] == 200  # 2 × 100

    def test_hyphenated_word_completion(self):
        s = new_game(word="НА-КА", players=["Игрок"], sector_value=10)
        s = apply(s, guess_letter("н"))
        s = apply(s, guess_letter("а"))
        s = apply(s, guess_letter("к"))
        assert s.phase == "round_won"
        assert is_fully_revealed(s.mask)


# ---- SKIP_TURN & MANUAL_SCORE ----------------------------------------


class TestSkipTurn:
    def test_passes_to_next(self, three_players):
        result = apply(three_players, skip_turn())
        assert result.current_player == 1
        assert result.version == three_players.version + 1

    def test_wraps_around(self, three_players):
        s = apply(three_players, skip_turn())    # 0 → 1
        s = apply(s, skip_turn())                # 1 → 2
        s = apply(s, skip_turn())                # 2 → 0
        assert s.current_player == 0


class TestManualScore:
    def test_add_points(self, three_players):
        result = apply(three_players, manual_score(player=1, delta=250))
        assert result.scores == (0, 250, 0)

    def test_subtract_points(self, three_players):
        s = apply(three_players, manual_score(player=0, delta=500))
        s = apply(s, manual_score(player=0, delta=-200))
        assert s.scores[0] == 300

    def test_invalid_player_raises(self, three_players):
        with pytest.raises(InvalidAction):
            apply(three_players, manual_score(player=5, delta=100))

    def test_negative_player_raises(self, three_players):
        with pytest.raises(InvalidAction):
            apply(three_players, manual_score(player=-1, delta=100))

    def test_allowed_in_any_phase(self):
        """Manual score adjustment should work even after round is won."""
        s = new_game(word="ДА", players=["Игрок"], sector_value=100)
        s = apply(s, guess_letter("д"))
        s = apply(s, guess_letter("а"))  # round_won
        # Still allowed — host might correct a mistake
        result = apply(s, manual_score(player=0, delta=50))
        assert result.scores[0] == s.scores[0] + 50


# ---- Invalid actions -------------------------------------------------


class TestInvalidActions:
    def test_guess_letter_after_round_won(self):
        s = new_game(word="ДА", players=["Игрок"], sector_value=100)
        s = apply(s, guess_letter("д"))
        s = apply(s, guess_letter("а"))
        assert s.phase == "round_won"
        with pytest.raises(InvalidAction):
            apply(s, guess_letter("х"))

    def test_guess_word_after_round_won(self):
        s = new_game(word="ДА", players=["Игрок"], sector_value=100)
        s = apply(s, guess_letter("д"))
        s = apply(s, guess_letter("а"))
        with pytest.raises(InvalidAction):
            apply(s, guess_word(correct=True))

    def test_skip_turn_after_round_won(self):
        s = new_game(word="ДА", players=["Игрок"], sector_value=100)
        s = apply(s, guess_letter("д"))
        s = apply(s, guess_letter("а"))
        with pytest.raises(InvalidAction):
            apply(s, skip_turn())

    def test_unknown_action_type(self, three_players):
        with pytest.raises(InvalidAction):
            apply(three_players, Action(type="NONEXISTENT"))


# ---- Version counter -------------------------------------------------


class TestVersion:
    def test_increments_on_each_action(self, three_players):
        assert three_players.version == 0
        s = apply(three_players, guess_letter("д"))  # hit
        assert s.version == 1
        s = apply(s, guess_letter("а"))  # miss
        assert s.version == 2

    def test_no_increment_on_repeated_letter(self, three_players):
        s = apply(three_players, guess_letter("д"))
        s2 = apply(s, guess_letter("д"))
        assert s2.version == s.version


# ---- Cumulative scoring across turns ---------------------------------


class TestCumulativeScoring:
    def test_scores_accumulate(self):
        s = new_game(
            word="ДОЛОМИТ",
            players=["Анна", "Борис"],
            scoring="per_occurrence",
            sector_value=100,
        )
        # Анна guesses Д (1 hit → 100)
        s = apply(s, guess_letter("д"))
        assert s.scores[0] == 100
        # Анна guesses О (2 hits → 200)
        s = apply(s, guess_letter("о"))
        assert s.scores[0] == 300  # 100 + 200
        # Анна misses Я → turn to Борис
        s = apply(s, guess_letter("я"))
        assert s.current_player == 1
        # Борис guesses Л (1 hit → 100)
        s = apply(s, guess_letter("л"))
        assert s.scores[1] == 100
        assert s.scores[0] == 300  # unchanged
