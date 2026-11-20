"""Tests for Строгий ТВ-режим (автоматический цикл вращения барабана).

Правила ТВ-режима (tv_mode=True):
1. Раунд начинается в фазе "idle" (ожидание вращения). Ввод букв заблокирован.
2. Вращение барабана:
   - START_SPIN -> "spinning"
   - SPIN_RESULT -> "await_letter" (сектор с очками разблокирует ввод букв).
3. При отгадывании буквы (GUESS_LETTER):
   - Угадал (hit), слово не закончено: игрок сохраняет ход, но обязан
     СНОВА вращать барабан (фаза переходит в "idle").
   - Не угадал (miss): ход переходит следующему игроку, фаза "idle" (следующий игрок вращает).
   - Слово закончено: фаза "round_won".
4. Секторы «Банкрот» и «Пропуск хода» передают ход в фазу "idle".
5. В суперигре вращение барабана не требуется.
"""

import pytest

from engine.actions import (
    InvalidAction,
    apply,
    guess_letter,
    guess_word,
    skip_turn,
    spin_result,
    start_spin,
)
from engine.effects import run_effect
from engine.state import new_game


class TestStrictTvMode:
    def test_initial_state_is_idle_when_tv_mode(self):
        state = new_game(
            word="ДОЛОМИТ",
            players=["Иван", "Елена", "Сергей"],
            tv_mode=True,
        )
        assert state.tv_mode is True
        assert state.phase == "idle"
        assert state.sector_value == 0
        assert state.current_player == 0

        # Попытка ввести букву без вращения барабана отвергается движком
        with pytest.raises(InvalidAction, match="Cannot guess letter in phase 'idle'"):
            apply(state, guess_letter("Д"))

    def test_spin_unlocks_letter_guess(self):
        state = new_game(
            word="ДОЛОМИТ",
            players=["Иван", "Елена", "Сергей"],
            tv_mode=True,
        )

        # 1. Старт вращения
        s1 = apply(state, start_spin())
        assert s1.phase == "spinning"

        # 2. Барабан остановился на секторе 300 очков
        s2 = apply(s1, spin_result(sector_index=1, sector_value=300))
        assert s2.phase == "await_letter"
        assert s2.sector_value == 300
        assert s2.current_player == 0

        # 3. Игрок называет букву 'Д' (попадание)
        s3 = apply(s2, guess_letter("Д"))
        assert s3.scores[0] == 300
        assert s3.mask[0] is True
        assert s3.current_player == 0  # Сохраняет ход
        assert s3.letter_streak == 1
        # ГЛАВНОЕ ПРАВИЛО ТВ-РЕЖИМА: ход сохранён, но для следующей буквы нужно снова крутить!
        assert s3.phase == "idle"

        # Попытка назвать ещё букву без повторного вращения барабана не проходит
        with pytest.raises(InvalidAction, match="Cannot guess letter in phase 'idle'"):
            apply(s3, guess_letter("О"))

    def test_full_turn_cycle_with_multiple_hits_and_miss(self):
        state = new_game(
            word="ДОЛОМИТ",
            players=["Иван", "Елена", "Сергей"],
            tv_mode=True,
        )

        # Иван: вращение 1 -> 250 очков -> буква 'Д' -> попадание
        s = apply(state, start_spin())
        s = apply(s, spin_result(sector_index=0, sector_value=250))
        s = apply(s, guess_letter("Д"))
        assert s.scores[0] == 250
        assert s.current_player == 0
        assert s.phase == "idle"

        # Иван: вращение 2 -> 500 очков -> буква 'О' (2 штуки) -> попадание (+1000)
        s = apply(s, start_spin())
        s = apply(s, spin_result(sector_index=4, sector_value=500))
        assert s.phase == "await_letter"
        s = apply(s, guess_letter("О"))
        assert s.scores[0] == 1250
        assert s.current_player == 0
        assert s.letter_streak == 2
        assert s.phase == "idle"

        # Иван: вращение 3 -> 100 очков -> буква 'Щ' -> промах!
        s = apply(s, start_spin())
        s = apply(s, spin_result(sector_index=1, sector_value=100))
        s = apply(s, guess_letter("Щ"))
        assert s.scores[0] == 1250
        # Ход переходит Елене (индекс 1)
        assert s.current_player == 1
        assert s.letter_streak == 0
        # Елена начинает свой ход в фазе idle (обязана вращать барабан)
        assert s.phase == "idle"

        # Елена не может назвать букву сразу
        with pytest.raises(InvalidAction):
            apply(s, guess_letter("Л"))

        # Елена вращает -> 400 очков -> буква 'Л'
        s = apply(s, start_spin())
        s = apply(s, spin_result(sector_index=2, sector_value=400))
        assert s.phase == "await_letter"
        s = apply(s, guess_letter("Л"))
        assert s.scores[1] == 400
        assert s.current_player == 1
        assert s.phase == "idle"

    def test_bankrupt_and_skip_turn_effects_in_tv_mode(self):
        state = new_game(
            word="ДОЛОМИТ",
            players=["Иван", "Елена", "Сергей"],
            sector_value=200,
            tv_mode=True,
        )
        # Начислим Ивану 500 очков
        state = apply(state, start_spin())
        state = apply(state, spin_result(0, 500))
        state = apply(state, guess_letter("Д"))
        assert state.scores[0] == 500
        assert state.phase == "idle"

        # Иван крутит барабан, выпадает Сектор «Банкрот»
        state = apply(state, start_spin())
        state = apply(state, spin_result(sector_index=3, sector_value=0))
        state = run_effect(state, {"type": "bankrupt"})

        assert state.scores[0] == 0
        assert state.current_player == 1  # Елена
        assert state.phase == "idle"  # Елена должна крутить

        # Елена крутит, выпадает «Пропуск хода»
        state = apply(state, start_spin())
        state = apply(state, spin_result(sector_index=5, sector_value=0))
        state = run_effect(state, {"type": "skip_turn"})

        assert state.current_player == 2  # Сергей
        assert state.phase == "idle"  # Сергей должен крутить

    def test_skip_turn_and_incorrect_word_in_tv_mode(self):
        state = new_game(
            word="ДОЛОМИТ",
            players=["Иван", "Елена", "Сергей"],
            tv_mode=True,
        )
        # Иван пропускает ход из idle
        s1 = apply(state, skip_turn())
        assert s1.current_player == 1
        assert s1.phase == "idle"

        # Елена пытается назвать слово целиком и ошибается
        s2 = apply(s1, guess_word(correct=False))
        assert s2.current_player == 2
        assert s2.phase == "idle"

    def test_round_won_in_tv_mode(self):
        state = new_game(
            word="ДА",
            players=["Иван", "Елена"],
            tv_mode=True,
        )
        # Крутим -> 'Д'
        s = apply(state, start_spin())
        s = apply(s, spin_result(0, 100))
        s = apply(s, guess_letter("Д"))
        assert s.phase == "idle"

        # Крутим -> 'А' -> победа в туре!
        s = apply(s, start_spin())
        s = apply(s, spin_result(0, 100))
        s = apply(s, guess_letter("А"))
        assert s.phase == "round_won"
        assert s.scores[0] == 200
