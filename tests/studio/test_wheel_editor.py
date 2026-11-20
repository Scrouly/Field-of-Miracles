"""Tests for Studio Wheel Editor (Task 11)."""

import json
import pytest
from django.test import Client

from apps.core.models import Effect, Sector, Wheel


@pytest.mark.django_db
class TestStudioWheelEditor:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = Client()
        # Create an effect
        self.effect_bankrupt = Effect.objects.create(
            name="Банкрот",
            actions=[{"type": "bankrupt"}],
        )
        self.effect_plus = Effect.objects.create(
            name="Сектор Плюс",
            actions=[{"type": "reveal_cell"}],
        )
        # Create a wheel
        self.wheel = Wheel.objects.create(name="Тестовый барабан")
        for i in range(4):
            Sector.objects.create(
                wheel=self.wheel,
                order=i,
                label=f"{100 * (i + 1)}",
                color="#1f4e5b",
                value=100 * (i + 1),
                weight=1,
            )

    def _login(self):
        session = self.client.session
        session["studio_authenticated"] = True
        session.save()

    def test_unauthorized_access_redirects_to_login(self):
        resp = self.client.get("/studio/")
        assert resp.status_code == 302
        assert "/studio/login/" in resp.url

    def test_login_with_correct_pin(self):
        resp = self.client.post("/studio/login/", {"pin": "1931"})
        assert resp.status_code == 302
        assert self.client.session.get("studio_authenticated") is True

    def test_login_with_wrong_pin(self):
        resp = self.client.post("/studio/login/", {"pin": "0000"})
        assert resp.status_code == 200
        assert "Неверный PIN-код" in resp.content.decode("utf-8")
        assert not self.client.session.get("studio_authenticated")

    def test_logout_clears_session(self):
        self._login()
        resp = self.client.get("/studio/logout/")
        assert resp.status_code == 302
        assert not self.client.session.get("studio_authenticated")

    def test_authorized_get_wheel_editor_page(self):
        self._login()
        resp = self.client.get(f"/studio/wheels/{self.wheel.id}/")
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")
        assert "Тестовый барабан" in content
        assert "wheel-preview-canvas" in content

    def test_api_unauthorized_returns_401(self):
        resp = self.client.get("/studio/api/wheels/")
        assert resp.status_code == 401

    def test_api_get_wheels_list(self):
        self._login()
        resp = self.client.get("/studio/api/wheels/")
        assert resp.status_code == 200
        data = resp.json()
        assert "wheels" in data
        assert any(w["id"] == self.wheel.id for w in data["wheels"])

    def test_api_create_wheel(self):
        self._login()
        resp = self.client.post(
            "/studio/api/wheels/",
            data=json.dumps({"name": "Новый барабан", "with_defaults": True}),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "ok"
        wheel_id = data["wheel"]["id"]
        assert data["wheel"]["name"] == "Новый барабан"
        assert data["wheel"]["sector_count"] == 16
        assert Wheel.objects.filter(pk=wheel_id).exists()

    def test_api_get_wheel_detail(self):
        self._login()
        resp = self.client.get(f"/studio/api/wheels/{self.wheel.id}/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["wheel"]["name"] == "Тестовый барабан"
        assert len(data["wheel"]["sectors"]) == 4
        assert len(data["effects"]) >= 2

    def test_api_save_sectors_success(self):
        self._login()
        payload = {
            "name": "Обновлённый барабан",
            "sectors": [
                {
                    "label": "500",
                    "value": 500,
                    "color": "#d97706",
                    "weight": 2,
                    "effect_id": None,
                },
                {
                    "label": "Б",
                    "value": 0,
                    "color": "#162447",
                    "weight": 1,
                    "effect_id": self.effect_bankrupt.id,
                },
                {
                    "label": "+",
                    "value": 0,
                    "color": "#2a9d8f",
                    "weight": 1,
                    "effect_id": self.effect_plus.id,
                },
            ],
        }
        resp = self.client.post(
            f"/studio/api/wheels/{self.wheel.id}/sectors/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["wheel"]["name"] == "Обновлённый барабан"
        assert data["wheel"]["sector_count"] == 3

        # Check DB
        self.wheel.refresh_from_db()
        assert self.wheel.name == "Обновлённый барабан"
        sectors = list(self.wheel.sectors.all().order_by("order"))
        assert len(sectors) == 3
        assert sectors[0].label == "500"
        assert sectors[0].value == 500
        assert sectors[0].weight == 2
        assert sectors[1].label == "Б"
        assert sectors[1].effect == self.effect_bankrupt
        assert sectors[2].label == "+"
        assert sectors[2].effect == self.effect_plus

    def test_api_save_sectors_too_few(self):
        self._login()
        payload = {
            "sectors": [{"label": "100", "value": 100, "color": "#1f4e5b", "weight": 1}]
        }
        resp = self.client.post(
            f"/studio/api/wheels/{self.wheel.id}/sectors/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "too_few_sectors"

    def test_api_save_sectors_empty_label(self):
        self._login()
        payload = {
            "sectors": [
                {"label": "100", "value": 100, "color": "#1f4e5b", "weight": 1},
                {"label": "", "value": 200, "color": "#1f4e5b", "weight": 1},
            ]
        }
        resp = self.client.post(
            f"/studio/api/wheels/{self.wheel.id}/sectors/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_sector"

    def test_api_delete_wheel(self):
        self._login()
        wheel_to_delete = Wheel.objects.create(name="Лишний барабан")
        resp = self.client.delete(f"/studio/api/wheels/{wheel_to_delete.id}/")
        assert resp.status_code == 200
        assert not Wheel.objects.filter(pk=wheel_to_delete.id).exists()
