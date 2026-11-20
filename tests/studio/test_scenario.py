"""Tests for Studio Event Scenario and Round sequencing (Task 12)."""

import json
import pytest
from django.test import Client

from apps.core.models import Event, Prize, Question, Round, Wheel
from apps.studio import scenario
from apps.studio.scenario import ScenarioError


@pytest.mark.django_db
class TestScenarioLogic:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.event = Event.objects.create(name="Тестовое мероприятие", is_active=True)
        self.q1 = Question.objects.create(word="ДОЛОМИТ", text="Минерал и порода")
        self.q2 = Question.objects.create(word="КАРЬЕР", text="Место добычи")
        self.q3 = Question.objects.create(word="ЦЕМЕНТ", text="Вяжущий материал")
        self.wheel = Wheel.objects.create(name="Барабан 1")

        # Create 3 rounds
        self.r1 = scenario.create_round(self.event, Round.Type.QUALIFYING, question=self.q1, wheel=self.wheel)
        self.r2 = scenario.create_round(self.event, Round.Type.QUALIFYING, question=self.q2, wheel=self.wheel)
        self.r3 = scenario.create_round(self.event, Round.Type.FINAL, question=self.q3, wheel=self.wheel)

    def test_initial_round_orders(self):
        rounds = scenario.get_event_rounds(self.event)
        assert len(rounds) == 3
        assert [r.order for r in rounds] == [1, 2, 3]
        assert [r.pk for r in rounds] == [self.r1.pk, self.r2.pk, self.r3.pk]

    def test_reorder_rounds_reverse_no_duplicates(self):
        # Reverse the order: r3, r2, r1
        new_ids = [self.r3.pk, self.r2.pk, self.r1.pk]
        updated = scenario.reorder_rounds(self.event, new_ids)

        assert [r.pk for r in updated] == new_ids
        assert [r.order for r in updated] == [1, 2, 3]

        # Verify in DB
        self.r1.refresh_from_db()
        self.r2.refresh_from_db()
        self.r3.refresh_from_db()

        assert self.r3.order == 1
        assert self.r2.order == 2
        assert self.r1.order == 3

    def test_reorder_rounds_arbitrary_permutation(self):
        # r2, r3, r1
        new_ids = [self.r2.pk, self.r3.pk, self.r1.pk]
        updated = scenario.reorder_rounds(self.event, new_ids)

        assert [r.pk for r in updated] == new_ids
        assert [r.order for r in updated] == [1, 2, 3]

    def test_reorder_invalid_ids_raises_error(self):
        with pytest.raises(ScenarioError):
            scenario.reorder_rounds(self.event, [self.r1.pk, 9999])

        with pytest.raises(ScenarioError):
            scenario.reorder_rounds(self.event, [self.r1.pk, self.r2.pk])

    def test_create_round_appends_to_end(self):
        r4 = scenario.create_round(self.event, Round.Type.SUPERGAME)
        assert r4.order == 4
        rounds = scenario.get_event_rounds(self.event)
        assert len(rounds) == 4
        assert [r.order for r in rounds] == [1, 2, 3, 4]

    def test_delete_round_recompacts_orders(self):
        # Delete the middle round (r2)
        scenario.delete_round(self.r2)

        rounds = scenario.get_event_rounds(self.event)
        assert len(rounds) == 2
        assert [r.pk for r in rounds] == [self.r1.pk, self.r3.pk]
        assert [r.order for r in rounds] == [1, 2]

        self.r1.refresh_from_db()
        self.r3.refresh_from_db()
        assert self.r1.order == 1
        assert self.r3.order == 2

    def test_update_round(self):
        prize = Prize.objects.create(event=self.event, name="Сертификат", cost=500)
        scenario.update_round(
            self.r1,
            round_type=Round.Type.FINAL,
            prize_id=prize.pk,
            params={"timer_seconds": 45},
        )
        self.r1.refresh_from_db()
        assert self.r1.type == Round.Type.FINAL
        assert self.r1.prize == prize
        assert self.r1.params == {"timer_seconds": 45}


@pytest.mark.django_db
class TestScenarioAPI:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = Client()
        self.event = Event.objects.create(name="Тестовое мероприятие", is_active=True)
        self.wheel = Wheel.objects.create(name="Барабан")
        self.q1 = Question.objects.create(word="ДОЛОМИТ", text="Минерал")
        self.q2 = Question.objects.create(word="КАРЬЕР", text="Место")
        self.r1 = scenario.create_round(self.event, question=self.q1, wheel=self.wheel)
        self.r2 = scenario.create_round(self.event, question=self.q2, wheel=self.wheel)

        session = self.client.session
        session["studio_authenticated"] = True
        session.save()

    def test_get_event_rounds_api(self):
        resp = self.client.get(f"/studio/api/events/{self.event.id}/rounds/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert len(data["rounds"]) == 2
        assert len(data["questions"]) >= 2
        assert len(data["wheels"]) >= 1

    def test_reorder_rounds_api_success(self):
        payload = {"round_ids": [self.r2.id, self.r1.id]}
        resp = self.client.post(
            f"/studio/api/events/{self.event.id}/rounds/reorder/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert [r["id"] for r in data["rounds"]] == [self.r2.id, self.r1.id]
        assert [r["order"] for r in data["rounds"]] == [1, 2]

    def test_create_round_api(self):
        payload = {
            "type": "final",
            "question_id": self.q1.id,
            "wheel_id": self.wheel.id,
        }
        resp = self.client.post(
            f"/studio/api/events/{self.event.id}/rounds/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "ok"
        assert data["round"]["order"] == 3
        assert data["round"]["type"] == "final"

    def test_update_round_api(self):
        payload = {
            "type": "supergame",
            "question_id": self.q2.id,
            "wheel_id": self.wheel.id,
        }
        resp = self.client.put(
            f"/studio/api/rounds/{self.r1.id}/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["round"]["type"] == "supergame"

    def test_delete_round_api(self):
        resp = self.client.delete(f"/studio/api/rounds/{self.r1.id}/")
        assert resp.status_code == 200
        assert not Round.objects.filter(pk=self.r1.id).exists()
        self.r2.refresh_from_db()
        assert self.r2.order == 1

    def test_scenario_html_view(self):
        resp = self.client.get(f"/studio/scenario/{self.event.id}/")
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")
        assert "Тестовое мероприятие" in content
        assert "rounds-list" in content
