"""Management command to populate a rich demo game for ОАО «Доломит»."""

from django.core.management.base import BaseCommand
from apps.core.models import (
    Effect,
    Event,
    GameSession,
    Player,
    Prize,
    Question,
    Round,
    Sector,
    Tag,
    Theme,
    Wheel,
)
from engine.state import new_game, state_to_dict


def populate_dolomit_demo() -> Event:
    """Create or update full demo event with Dolomite questions, sectors, players, and prizes."""
    # 1. Corporate Theme
    theme, _ = Theme.objects.get_or_create(
        name="Корпоративный Доломит",
        defaults={
            "colors": {
                "bg_main": "#0b132b",
                "bg_card": "#1c2541",
                "color_gold": "#f4c430",
            },
            "fonts": {"main": "Segoe UI, sans-serif"},
        },
    )

    # 2. Event
    event, _ = Event.objects.get_or_create(
        name="Молодёжный форум ОАО «Доломит»",
        defaults={
            "theme": theme,
            "rules": {"scoring": "per_occurrence", "word_bonus": 500, "tv_mode": True},
            "is_active": True,
        },
    )
    rules = event.rules or {}
    if not rules.get("tv_mode"):
        rules["tv_mode"] = True
        event.rules = rules
    if not event.is_active:
        event.is_active = True
    event.save(update_fields=["rules", "is_active"])

    # 3. Tags
    tag_factory, _ = Tag.objects.get_or_create(name="Производство")
    tag_geo, _ = Tag.objects.get_or_create(name="Геология")

    # 4. Questions
    q_r1, _ = Question.objects.get_or_create(
        word="ДОЛОМИТ",
        defaults={
            "text": "Главный минерал предприятия и осадочная карбонатная горная порода",
            "hint": "Название предприятия",
            "difficulty": Question.Difficulty.EASY,
        },
    )
    q_r1.tags.add(tag_factory, tag_geo)

    q_r2, _ = Question.objects.get_or_create(
        word="КАРЬЕР",
        defaults={
            "text": "Горное предприятие по добыче полезных ископаемых открытым способом",
            "hint": "Место добычи камня",
            "difficulty": Question.Difficulty.EASY,
        },
    )
    q_r2.tags.add(tag_factory)

    q_r3, _ = Question.objects.get_or_create(
        word="МАШИНИСТ",
        defaults={
            "text": "Специалист, управляющий карьерным экскаватором или дробильной установкой",
            "hint": "Горная профессия",
            "difficulty": Question.Difficulty.MEDIUM,
        },
    )
    q_r3.tags.add(tag_factory)

    q_final, _ = Question.objects.get_or_create(
        word="ФЛОТАЦИЯ",
        defaults={
            "text": "Один из методов обогащения полезных ископаемых, основанный на смачиваемости",
            "hint": "Технологический процесс",
            "difficulty": Question.Difficulty.HARD,
        },
    )
    q_final.tags.add(tag_factory)

    q_super, _ = Question.objects.get_or_create(
        word="ДРОБИЛКА",
        defaults={
            "text": "Оборудование для разрушения кусков горной породы на фракции нужного размера",
            "hint": "Агрегат на дробильно-сортировочном заводе",
            "difficulty": Question.Difficulty.MEDIUM,
        },
    )
    q_super.tags.add(tag_factory)

    # 5. Wheels and Sectors
    wheel, _ = Wheel.objects.get_or_create(
        name="Классический барабан Доломит (16 секторов)"
    )

    if wheel.sectors.count() == 0:
        eff_points, _ = Effect.objects.get_or_create(name="points", defaults={"actions": [{"action": "add_points"}]})
        eff_bankrupt, _ = Effect.objects.get_or_create(name="bankrupt", defaults={"actions": [{"action": "bankrupt"}]})
        eff_plus, _ = Effect.objects.get_or_create(name="plus", defaults={"actions": [{"action": "plus"}]})
        eff_prize, _ = Effect.objects.get_or_create(name="prize", defaults={"actions": [{"action": "prize"}]})
        eff_double, _ = Effect.objects.get_or_create(name="double", defaults={"actions": [{"action": "multiply", "factor": 2}]})

        sectors_config = [
            ("100", 100, "#3a86ff", eff_points),
            ("200", 200, "#8338ec", eff_points),
            ("300", 300, "#ff006e", eff_points),
            ("ПРИЗ", 0, "#fb5607", eff_prize),
            ("400", 400, "#ffbe0b", eff_points),
            ("БАНКРОТ", 0, "#000000", eff_bankrupt),
            ("500", 500, "#06d6a0", eff_points),
            ("+", 0, "#118ab2", eff_plus),
            ("150", 150, "#3a86ff", eff_points),
            ("250", 250, "#8338ec", eff_points),
            ("x2", 0, "#ff006e", eff_double),
            ("350", 350, "#ffbe0b", eff_points),
            ("450", 450, "#06d6a0", eff_points),
            ("600", 600, "#fb5607", eff_points),
            ("750", 750, "#118ab2", eff_points),
            ("1000", 1000, "#f4c430", eff_points),
        ]
        for idx, (label, val, color, eff) in enumerate(sectors_config, start=1):
            Sector.objects.create(
                wheel=wheel,
                label=label,
                value=val,
                color=color,
                order=idx,
                effect=eff,
            )

    # 6. Players
    players_data = [
        ("Иван Кузнецов", "Цех добычи и переработки", 1),
        ("Елена Смирнова", "Лаборатория ОТК", 2),
        ("Сергей Морозов", "Ремонтно-механический цех", 3),
        ("Дмитрий Волков", "Отдел АСУТП", 4),
        ("Ольга Васильева", "Бухгалтерия", 5),
        ("Алексей Петров", "Транспортный цех", 6),
        ("Наталья Ковалева", "Отдел кадров", 7),
        ("Максим Соколов", "Энергетический цех", 8),
        ("Татьяна Новикова", "ПТО", 9),
    ]
    for name, org, order in players_data:
        Player.objects.get_or_create(
            event=event,
            name=name,
            defaults={"team": org, "order": order},
        )

    # 7. Prizes
    prizes_data = [
        ("Фирменная кружка «Доломит»", 100),
        ("Набор инструментов слесаря", 300),
        ("Электрический чайник", 500),
        ("Умная колонка", 800),
        ("Планшет 10 дюймов", 1200),
        ("Телевизор 4K", 2500),
        ("Автомобиль", 5000),
    ]
    for name, cost in prizes_data:
        Prize.objects.get_or_create(
            event=event,
            name=name,
            defaults={"cost": cost},
        )

    # 8. Rounds with assigned 3 players per tour
    rounds_config = [
        (1, Round.Type.QUALIFYING, q_r1, ["Иван Кузнецов", "Елена Смирнова", "Сергей Морозов"]),
        (2, Round.Type.QUALIFYING, q_r2, ["Дмитрий Волков", "Ольга Васильева", "Алексей Петров"]),
        (3, Round.Type.QUALIFYING, q_r3, ["Наталья Ковалева", "Максим Соколов", "Татьяна Новикова"]),
        (4, Round.Type.FINAL, q_final, ["Иван Кузнецов", "Дмитрий Волков", "Максим Соколов"]),
        (5, Round.Type.SUPERGAME, q_super, ["Иван Кузнецов"]),
    ]

    for order_val, r_type, question_obj, round_players in rounds_config:
        r_obj, created = Round.objects.get_or_create(
            event=event,
            order=order_val,
            defaults={
                "type": r_type,
                "question": question_obj,
                "wheel": wheel,
                "params": {"players": round_players},
            },
        )
        if not created and (not r_obj.params or "players" not in r_obj.params):
            r_obj.params = {"players": round_players}
            r_obj.save(update_fields=["params"])

    # 9. Clean active GameSession for Round 1
    init_state = new_game(
        word="ДОЛОМИТ",
        players=["Иван Кузнецов", "Елена Смирнова", "Сергей Морозов"],
        scoring="per_occurrence",
        word_bonus=500,
        sector_value=0,
        question=q_r1.text,
        hint=q_r1.hint,
        tv_mode=True,
    )
    state_dict = state_to_dict(init_state)

    # Clear old sessions or reset active session
    active_session = GameSession.objects.filter(event=event).order_by("-started_at").first()
    if active_session:
        active_session.state = state_dict
        active_session.version = 0
        active_session.logs.all().delete()
        active_session.save(update_fields=["state", "version"])
    else:
        GameSession.objects.create(
            event=event,
            state=state_dict,
            version=0,
        )

    return event


class Command(BaseCommand):
    help = "Заполнить базу данных демонстрационным мероприятием ОАО «Доломит» и подготовить тестовую игру"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Создание демонстрационного мероприятия ОАО «Доломит»..."))
        event = populate_dolomit_demo()
        self.stdout.write(
            self.style.SUCCESS(
                f"Успешно создано мероприятивное шоу: '{event.name}' с 5 турами и чистой игровой сессией!"
            )
        )
