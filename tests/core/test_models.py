import pytest
from django.db import IntegrityError, transaction

from apps.core.defaults import default_rules
from apps.core.models import Event, GameLog
from tests.factories import (
    EventFactory,
    GameSessionFactory,
    RoundFactory,
    SectorFactory,
    WheelFactory,
)

pytestmark = pytest.mark.django_db


def test_sector_cannot_be_created_without_wheel():
    with pytest.raises(IntegrityError), transaction.atomic():
        SectorFactory(wheel=None)


def test_sector_order_is_unique_within_wheel():
    wheel = WheelFactory()
    SectorFactory(wheel=wheel, order=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        SectorFactory(wheel=wheel, order=1)


def test_same_sector_order_is_allowed_in_another_wheel():
    SectorFactory(wheel=WheelFactory(), order=1)
    SectorFactory(wheel=WheelFactory(), order=1)


def test_round_order_is_unique_within_event():
    event = EventFactory()
    RoundFactory(event=event, order=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        RoundFactory(event=event, order=1)


def test_same_round_order_is_allowed_in_another_event():
    RoundFactory(event=EventFactory(), order=1)
    RoundFactory(event=EventFactory(), order=1)


def test_new_event_gets_default_rules():
    event = EventFactory()
    assert set(event.rules) == {
        "players_count",
        "scoring",
        "word_bonus",
        "box_streak_threshold",
        "supergame_letters",
        "timer_seconds",
        "keyboard_layout",
    }


def test_default_rules_are_not_shared_between_events():
    first, second = EventFactory(), EventFactory()
    first.rules["players_count"] = 8
    assert second.rules["players_count"] != 8
    assert default_rules() is not default_rules()


def test_game_log_number_is_unique_within_session():
    session = GameSessionFactory()
    GameLog.objects.create(session=session, number=1, action="GUESS_LETTER")
    with pytest.raises(IntegrityError), transaction.atomic():
        GameLog.objects.create(session=session, number=1, action="SKIP_TURN")


def test_deleting_event_removes_its_rounds():
    event = EventFactory()
    RoundFactory(event=event, order=1)
    event.delete()
    assert Event.objects.count() == 0
