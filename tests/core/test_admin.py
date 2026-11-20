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
