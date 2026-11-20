"""Модели «Поля чудес».

Всё содержимое игры (вопросы, сектора, правила, цвета, звуки, логотип) хранится
данными в БД, а не кодом. Правила самой игры лежат в чистом модуле engine/.
"""
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from .defaults import default_rules

HEX_COLOR = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Цвет в формате #RRGGBB, например #1e90ff.")


class Theme(models.Model):
    """Оформление: цвета, шрифты, логотип, фон."""

    name = models.CharField("название", max_length=100, unique=True)
    colors = models.JSONField("цвета", default=dict, blank=True)
    fonts = models.JSONField("шрифты", default=dict, blank=True)
    # FileField, а не ImageField: логотип часто бывает в SVG, а ImageField его не принимает.
    logo = models.FileField("логотип", upload_to="images/", blank=True)
    background = models.FileField("фон", upload_to="images/", blank=True)

    class Meta:
        verbose_name = "тема оформления"
        verbose_name_plural = "темы оформления"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Event(models.Model):
    """Мероприятие: корпоратив, молодёжный форум и т. д."""

    name = models.CharField("название", max_length=200)
    theme = models.ForeignKey(
        Theme,
        verbose_name="тема оформления",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="events",
    )
    rules = models.JSONField(
        "правила", default=default_rules, help_text="Параметры игры в формате JSON."
    )
    is_active = models.BooleanField("активное", default=False)

    class Meta:
        verbose_name = "мероприятие"
        verbose_name_plural = "мероприятия"
        ordering = ["-is_active", "name"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField("тег", max_length=50, unique=True)

    class Meta:
        verbose_name = "тег"
        verbose_name_plural = "теги"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Question(models.Model):
    class Difficulty(models.IntegerChoices):
        EASY = 1, "лёгкий"
        MEDIUM = 2, "средний"
        HARD = 3, "сложный"

    text = models.CharField("вопрос", max_length=500)
    word = models.CharField("слово", max_length=50)
    hint = models.CharField("подсказка", max_length=200, blank=True)
    tags = models.ManyToManyField(Tag, verbose_name="теги", blank=True, related_name="questions")
    difficulty = models.PositiveSmallIntegerField(
        "сложность", choices=Difficulty.choices, default=Difficulty.EASY
    )

    class Meta:
        verbose_name = "вопрос"
        verbose_name_plural = "вопросы"
        ordering = ["word"]

    def __str__(self):
        return f"{self.word} — {self.text[:40]}"


class Effect(models.Model):
    """Эффект сектора: список действий в JSON (add_points, bankrupt, ...).

    Так администратор создаёт новые типы секторов без правки кода.
    """

    name = models.CharField("название", max_length=100, unique=True)
    actions = models.JSONField("действия", default=list, blank=True)

    class Meta:
        verbose_name = "эффект"
        verbose_name_plural = "эффекты"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Wheel(models.Model):
    name = models.CharField("название", max_length=100)

    class Meta:
        verbose_name = "барабан"
        verbose_name_plural = "барабаны"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Sector(models.Model):
    wheel = models.ForeignKey(
        Wheel, verbose_name="барабан", on_delete=models.CASCADE, related_name="sectors"
    )
    order = models.PositiveSmallIntegerField("порядок")
    label = models.CharField("подпись", max_length=30)
    color = models.CharField("цвет", max_length=7, default="#cccccc", validators=[HEX_COLOR])
    value = models.IntegerField("значение (очки)", default=0)
    weight = models.PositiveIntegerField(
        "вес", default=1, help_text="Чем больше вес, тем чаще выпадает сектор."
    )
    effect = models.ForeignKey(
        Effect,
        verbose_name="эффект",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sectors",
    )

    class Meta:
        verbose_name = "сектор"
        verbose_name_plural = "сектора"
        ordering = ["wheel", "order"]
        constraints = [
            models.UniqueConstraint(fields=["wheel", "order"], name="unique_sector_order_in_wheel")
        ]

    def __str__(self):
        return f"{self.wheel} · {self.order}: {self.label}"


class Prize(models.Model):
    event = models.ForeignKey(
        Event, verbose_name="мероприятие", on_delete=models.CASCADE, related_name="prizes"
    )
    name = models.CharField("название", max_length=200)
    cost = models.PositiveIntegerField("цена в очках", default=0)
    image = models.FileField("картинка", upload_to="images/", blank=True)

    class Meta:
        verbose_name = "приз"
        verbose_name_plural = "призы"
        ordering = ["event", "cost"]

    def __str__(self):
        return self.name


class Round(models.Model):
    class Type(models.TextChoices):
        QUALIFYING = "qualifying", "отборочный"
        FINAL = "final", "финал"
        SUPERGAME = "supergame", "суперигра"

    event = models.ForeignKey(
        Event, verbose_name="мероприятие", on_delete=models.CASCADE, related_name="rounds"
    )
    order = models.PositiveSmallIntegerField("порядок", validators=[MinValueValidator(1)])
    type = models.CharField("тип", max_length=20, choices=Type.choices, default=Type.QUALIFYING)
    question = models.ForeignKey(
        Question,
        verbose_name="вопрос",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="rounds",
    )
    wheel = models.ForeignKey(
        Wheel,
        verbose_name="барабан",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="rounds",
    )
    prize = models.ForeignKey(
        Prize,
        verbose_name="приз",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="rounds",
    )
    params = models.JSONField("параметры тура", default=dict, blank=True)

    class Meta:
        verbose_name = "тур"
        verbose_name_plural = "туры"
        ordering = ["event", "order"]
        constraints = [
            models.UniqueConstraint(fields=["event", "order"], name="unique_round_order_in_event")
        ]

    def __str__(self):
        return f"{self.event} · тур {self.order}"


class Player(models.Model):
    event = models.ForeignKey(
        Event, verbose_name="мероприятие", on_delete=models.CASCADE, related_name="players"
    )
    name = models.CharField("имя", max_length=100)
    team = models.CharField("команда или подразделение", max_length=100, blank=True)
    order = models.PositiveSmallIntegerField("порядок", default=1)

    class Meta:
        verbose_name = "игрок"
        verbose_name_plural = "игроки"
        ordering = ["event", "order"]

    def __str__(self):
        return self.name


class Sound(models.Model):
    name = models.CharField("название", max_length=100, unique=True)
    file = models.FileField("файл", upload_to="sounds/")

    class Meta:
        verbose_name = "звук"
        verbose_name_plural = "звуки"
        ordering = ["name"]

    def __str__(self):
        return self.name


class SoundBinding(models.Model):
    class Trigger(models.TextChoices):
        SPIN = "spin", "вращение барабана"
        HIT = "hit", "буква есть"
        MISS = "miss", "буквы нет"
        BANKRUPT = "bankrupt", "банкрот"
        WIN = "win", "победа"

    event = models.ForeignKey(
        Event, verbose_name="мероприятие", on_delete=models.CASCADE, related_name="sound_bindings"
    )
    trigger = models.CharField("событие", max_length=20, choices=Trigger.choices)
    sound = models.ForeignKey(
        Sound, verbose_name="звук", on_delete=models.PROTECT, related_name="bindings"
    )

    class Meta:
        verbose_name = "привязка звука"
        verbose_name_plural = "привязки звуков"
        ordering = ["event", "trigger"]
        constraints = [
            models.UniqueConstraint(
                fields=["event", "trigger"], name="unique_sound_trigger_in_event"
            )
        ]

    def __str__(self):
        return f"{self.event} · {self.get_trigger_display()} → {self.sound}"


class GameSession(models.Model):
    event = models.ForeignKey(
        Event, verbose_name="мероприятие", on_delete=models.CASCADE, related_name="sessions"
    )
    state = models.JSONField("состояние игры", default=dict, blank=True)
    version = models.PositiveIntegerField("версия состояния", default=0)
    started_at = models.DateTimeField("начало", auto_now_add=True)
    finished_at = models.DateTimeField("конец", null=True, blank=True)

    class Meta:
        verbose_name = "игровая сессия"
        verbose_name_plural = "игровые сессии"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.event} · сессия {self.pk}"


class GameLog(models.Model):
    """Журнал действий: от него работают Undo и восстановление после сбоя."""

    session = models.ForeignKey(
        GameSession, verbose_name="сессия", on_delete=models.CASCADE, related_name="logs"
    )
    number = models.PositiveIntegerField("номер действия")
    action = models.CharField("действие", max_length=50)
    data = models.JSONField("данные", default=dict, blank=True)
    created_at = models.DateTimeField("время", auto_now_add=True)

    class Meta:
        verbose_name = "запись журнала"
        verbose_name_plural = "журнал игры"
        ordering = ["session", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "number"], name="unique_log_number_in_session"
            )
        ]

    def __str__(self):
        return f"#{self.number} {self.action}"
