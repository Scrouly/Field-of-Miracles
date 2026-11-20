"""Management command to populate a rich demo game for ОАО «Доломит»."""

from django.core.management.base import BaseCommand
from apps.core.models import (
    Effect,
    Event,
    Player,
    Prize,
    Question,
    Round,
    Sector,
    Tag,
    Theme,
    Wheel,
)


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
            "rules": {"scoring": "per_occurrence", "word_bonus": 500},
            "is_active": True,
        },
    )
    if not event.is_active:
        event.is_active = True
        event.save(update_fields=["is_active"])

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

    # 8. Rounds
    if event.rounds.count() == 0:
        Round.objects.create(
            event=event,
            order=1,
            type=Round.Type.QUALIFYING,
            question=q_r1,
            wheel=wheel,
        )
        Round.objects.create(
            event=event,
            order=2,
            type=Round.Type.QUALIFYING,
            question=q_r2,
            wheel=wheel,
        )
        Round.objects.create(
            event=event,
            order=3,
            type=Round.Type.QUALIFYING,
            question=q_r3,
            wheel=wheel,
        )
        Round.objects.create(
            event=event,
            order=4,
            type=Round.Type.FINAL,
            question=q_final,
            wheel=wheel,
        )
        Round.objects.create(
            event=event,
            order=5,
            type=Round.Type.SUPERGAME,
            question=q_super,
            wheel=wheel,
        )

    return event


class Command(BaseCommand):
    help = "Заполнить базу данных демонстрационным мероприятием ОАО «Доломит»"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Создание демонстрационного мероприятия ОАО «Доломит»..."))
        event = populate_dolomit_demo()
        self.stdout.write(
            self.style.SUCCESS(
                f"Успешно создано мероприятие: '{event.name}' с раундами, вопросами, барабаном и призами!"
            )
        )
