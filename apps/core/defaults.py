"""Значения по умолчанию для JSON-полей моделей."""


def default_rules() -> dict:
    """Правила нового мероприятия (Event.rules).

    Функция, а не словарь-константа: у каждого события должна быть своя копия.
    """
    return {
        "players_count": 3,
        "scoring": "per_letter",  # или "per_occurrence"
        "word_bonus": 0,
        "box_streak_threshold": 3,
        "supergame_letters": 3,
        "timer_seconds": 30,
        "keyboard_layout": "ru",
    }
