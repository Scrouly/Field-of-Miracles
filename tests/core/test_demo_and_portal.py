"""Tests for the landing portal and setup_demo management command."""

import pytest
from django.core.management import call_command
from django.test import Client

from apps.core.models import Event, Prize, Question, Round, Sector, Theme, Wheel


@pytest.mark.django_db
def test_portal_renders_all_navigation_links(client: Client):
    response = client.get("/")
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "/display/" in content
    assert "/host/" in content
    assert "/studio/" in content
    assert "/admin/" in content
    assert "Поле чудес" in content
    assert "ОАО «Доломит»" in content
    assert "1931" in content


@pytest.mark.django_db
def test_setup_demo_command():
    # Verify command execution creates full event hierarchy
    call_command("setup_demo")

    event = Event.objects.get(name="Молодёжный форум ОАО «Доломит»")
    assert event.is_active is True
    assert event.theme.name == "Корпоративный Доломит"

    # Check questions
    words = list(Question.objects.values_list("word", flat=True))
    assert "ДОЛОМИТ" in words
    assert "КАРЬЕР" in words
    assert "МАШИНИСТ" in words
    assert "ФЛОТАЦИЯ" in words
    assert "ДРОБИЛКА" in words

    # Check rounds
    assert event.rounds.count() == 5
    first_round = event.rounds.get(order=1)
    assert first_round.question.word == "ДОЛОМИТ"
    assert first_round.type == Round.Type.QUALIFYING

    super_round = event.rounds.get(order=5)
    assert super_round.type == Round.Type.SUPERGAME
    assert super_round.question.word == "ДРОБИЛКА"

    # Check wheel and sectors
    wheel = Wheel.objects.get(name="Классический барабан Доломит (16 секторов)")
    assert wheel.sectors.count() == 16

    # Check players and prizes
    assert event.players.count() >= 9
    assert event.prizes.count() >= 7
