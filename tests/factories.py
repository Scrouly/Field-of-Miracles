"""Фабрики моделей для тестов (factory_boy)."""
import factory

from apps.core import models


class ThemeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Theme

    name = factory.Sequence(lambda n: f"Тема {n}")


class EventFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Event

    name = factory.Sequence(lambda n: f"Мероприятие {n}")


class QuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Question

    text = "Что висит на колокольне?"
    word = "колокол"
    hint = "Звонит"


class WheelFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Wheel

    name = factory.Sequence(lambda n: f"Барабан {n}")


class SectorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Sector

    wheel = factory.SubFactory(WheelFactory)
    order = factory.Sequence(lambda n: n + 1)
    label = "100"
    value = 100


class RoundFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Round

    event = factory.SubFactory(EventFactory)
    order = factory.Sequence(lambda n: n + 1)


class PlayerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.Player

    event = factory.SubFactory(EventFactory)
    name = factory.Sequence(lambda n: f"Игрок {n}")
    order = factory.Sequence(lambda n: n + 1)


class GameSessionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.GameSession

    event = factory.SubFactory(EventFactory)


class GameLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = models.GameLog

    session = factory.SubFactory(GameSessionFactory)
    number = factory.Sequence(lambda n: n + 1)
    action = "GUESS_LETTER"
    data = factory.LazyFunction(dict)

