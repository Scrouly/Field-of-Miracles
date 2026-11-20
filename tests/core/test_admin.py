import json

import pytest
from django.apps import apps
from django.contrib import admin
from django.urls import reverse

from apps.core.defaults import default_rules
from apps.core.models import Event
from tests.factories import QuestionFactory, WheelFactory

pytestmark = pytest.mark.django_db


def _core_models():
    return [m for m in apps.get_app_config("core").get_models() if m in admin.site._registry]


def test_every_content_model_is_registered_in_admin():
    registered = {m.__name__ for m in _core_models()}
    assert {
        "Event", "Theme", "Round", "Question", "Tag", "Wheel", "Sector", "Effect",
        "Player", "Prize", "Sound", "SoundBinding", "GameSession", "GameLog",
    } <= registered  # fmt: skip


@pytest.mark.parametrize("model", _core_models(), ids=lambda m: m.__name__)
def test_admin_pages_open(client, superuser, model):
    client.force_login(superuser)
    opts = model._meta
    list_url = reverse(f"admin:{opts.app_label}_{opts.model_name}_changelist")
    add_url = reverse(f"admin:{opts.app_label}_{opts.model_name}_add")
    assert client.get(list_url).status_code == 200
    assert client.get(add_url).status_code == 200


def _inline(prefix, total, **fields):
    data = {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    data.update({f"{prefix}-{k}": v for k, v in fields.items()})
    return data


def test_event_with_round_question_wheel_and_players_is_created_from_admin(client, superuser):
    """Критерий готовности задачи 2: событие с туром, вопросом, барабаном и игроками."""
    client.force_login(superuser)
    question = QuestionFactory()
    wheel = WheelFactory()
    data = {
        "name": "Молодёжный форум",
        "rules": json.dumps(default_rules()),
        **_inline(
            "players", 2,
            **{"0-name": "Анна", "0-order": "1", "1-name": "Борис", "1-order": "2"},
        ),
        **_inline(
            "rounds", 1,
            **{
                "0-order": "1", "0-type": "qualifying", "0-question": str(question.pk),
                "0-wheel": str(wheel.pk), "0-params": "{}",
            },
        ),
        **_inline("prizes", 0),
        "_save": "Сохранить",
    }  # fmt: skip
    response = client.post(reverse("admin:core_event_add"), data)
    assert response.status_code == 302, response.context["errors"] if response.context else ""
    event = Event.objects.get(name="Молодёжный форум")
    assert event.players.count() == 2
    assert event.rounds.get().question == question
    assert event.rounds.get().wheel == wheel


def test_question_admin_normalizes_word_and_displays_tags(client, superuser):
    """Задача 10: нормализация слов и отображение тегов."""
    from apps.core.models import Question, Tag
    client.force_login(superuser)

    tag1 = Tag.objects.create(name="История")
    tag2 = Tag.objects.create(name="Руба")

    data = {
        "text": "Как назывался посёлок доломитчиков?",
        "word": " руба ",  # Lowercase with spaces -> should be normalized to 'РУБА'
        "hint": "Посёлок",
        "difficulty": "1",
        "tags": [str(tag1.pk), str(tag2.pk)],
    }
    resp = client.post(reverse("admin:core_question_add"), data)
    assert resp.status_code == 302

    q = Question.objects.get(text="Как назывался посёлок доломитчиков?")
    assert q.word == "РУБА"
    assert q.tags.count() == 2

    # Verify changelist page displays tags and filters
    list_resp = client.get(reverse("admin:core_question_changelist"))
    assert list_resp.status_code == 200
    html = list_resp.content.decode("utf-8")
    assert "История" in html
    assert "Руба" in html


def test_question_admin_filters_by_tag(client, superuser):
    """Задача 10: фильтрация вопросов по тегам."""
    from apps.core.models import Question, Tag
    client.force_login(superuser)

    tag_geo = Tag.objects.create(name="Геология")
    tag_chem = Tag.objects.create(name="Химия")

    q1 = Question.objects.create(word="ДОЛОМИТ", text="Карбонат кальция и магния", difficulty=1)
    q1.tags.add(tag_geo, tag_chem)

    q2 = Question.objects.create(word="КАЛЬЦИТ", text="Минерал", difficulty=2)
    q2.tags.add(tag_geo)

    url = reverse("admin:core_question_changelist") + f"?tags__id__exact={tag_chem.pk}"
    resp = client.get(url)
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert "ДОЛОМИТ" in html
    assert "КАЛЬЦИТ" not in html


def test_sector_admin_color_badge_and_effect_summary(client, superuser):
    """Задача 10: цветной бейдж сектора и сводка действий эффекта."""
    from apps.core.models import Effect, Sector
    client.force_login(superuser)
    wheel = WheelFactory()
    effect = Effect.objects.create(
        name="Супер-бонус",
        actions=[{"type": "add_points", "amount": 500}, "play_sound"],
    )
    Sector.objects.create(
        wheel=wheel, order=1, label="Бонус", color="#ff0000", value=500, effect=effect
    )

    # Sector list
    sector_list = client.get(reverse("admin:core_sector_changelist"))
    assert sector_list.status_code == 200
    assert "#ff0000" in sector_list.content.decode("utf-8")

    # Effect list
    effect_list = client.get(reverse("admin:core_effect_changelist"))
    assert effect_list.status_code == 200
    assert "add_points" in effect_list.content.decode("utf-8")


def test_create_player_and_prize_from_admin(client, superuser):
    """Задача 10: создание игроков и призов без обращения к коду."""
    from apps.core.models import Player, Prize
    client.force_login(superuser)
    event = Event.objects.create(name="Корпоратив 2026")

    # Add Player
    player_data = {"event": str(event.pk), "name": "Иван Петров", "team": "Цех №1", "order": "1"}
    resp_player = client.post(reverse("admin:core_player_add"), player_data)
    assert resp_player.status_code == 302
    assert Player.objects.filter(name="Иван Петров", event=event).exists()

    # Add Prize
    prize_data = {"event": str(event.pk), "name": "Микроволновка", "cost": "800"}
    resp_prize = client.post(reverse("admin:core_prize_add"), prize_data)
    assert resp_prize.status_code == 302
    assert Prize.objects.filter(name="Микроволновка", event=event).exists()

