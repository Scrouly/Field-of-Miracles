"""Tests for Event Export and Import Packaging (Task 17)."""

import json
import tempfile
import zipfile
from pathlib import Path

import pytest
from django.core.management import call_command

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
from apps.core.packaging import export_event, import_event


@pytest.mark.django_db
class TestPackagingRoundTrip:
    @pytest.fixture(autouse=True)
    def setup_event(self):
        # 1. Theme
        self.theme = Theme.objects.create(
            name="Праздничный Доломит",
            colors={"bg_main": "#0b132b", "color_gold": "#f4c430"},
            fonts={"heading": "sans-serif"},
        )
        # 2. Event
        self.event = Event.objects.create(
            name="Корпоратив ОАО «Доломит» 2026",
            theme=self.theme,
            rules={"scoring": "per_occurrence", "word_bonus": 500},
            is_active=True,
        )
        # 3. Tags & Question
        self.tag = Tag.objects.create(name="производство")
        self.q1 = Question.objects.create(
            word="ДОЛОМИТ",
            text="Минерал и природная карбонатная порода",
            hint="Название предприятия",
            difficulty=Question.Difficulty.EASY,
        )
        self.q1.tags.add(self.tag)

        # 4. Wheel, Effect, Sectors
        self.wheel = Wheel.objects.create(name="Основной барабан")
        self.eff_bankrupt = Effect.objects.create(
            name="Банкрот", actions=[{"type": "bankrupt"}]
        )
        Sector.objects.create(
            wheel=self.wheel, order=0, label="100", color="#1f4e5b", value=100, weight=1
        )
        Sector.objects.create(
            wheel=self.wheel,
            order=1,
            label="Б",
            color="#ef4444",
            value=0,
            weight=1,
            effect=self.eff_bankrupt,
        )

        # 5. Prize
        self.prize = Prize.objects.create(
            event=self.event,
            name="Набор сувениров",
            cost=300,
        )

        # 6. Round
        self.round = Round.objects.create(
            event=self.event,
            order=1,
            type=Round.Type.QUALIFYING,
            question=self.q1,
            wheel=self.wheel,
            prize=self.prize,
            params={"timer": 60},
        )

        # 7. Players
        self.p1 = Player.objects.create(
            event=self.event,
            name="Иван Иванов",
            team="Цех № 1",
            order=1,
        )

    def test_export_creates_valid_zip_with_manifest(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "event_export.zip"
            exported_file = export_event(self.event, zip_path)

            assert exported_file.is_file()
            assert zipfile.is_zipfile(exported_file)

            with zipfile.ZipFile(exported_file, "r") as zf:
                namelist = zf.namelist()
                assert "manifest.json" in namelist

                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
                assert manifest["event"]["name"] == "Корпоратив ОАО «Доломит» 2026"
                assert manifest["theme"]["name"] == "Праздничный Доломит"
                assert len(manifest["questions"]) == 1
                assert manifest["questions"][0]["word"] == "ДОЛОМИТ"
                assert len(manifest["wheels"]) == 1
                assert len(manifest["wheels"][0]["sectors"]) == 2
                assert len(manifest["prizes"]) == 1
                assert len(manifest["rounds"]) == 1
                assert len(manifest["players"]) == 1

    def test_round_trip_export_and_import_identical(self):
        """Тест: экспорт, затем импорт даёт идентичное событие."""
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "event_roundtrip.zip"
            export_event(self.event, zip_path)

            # Clear existing event and relations from DB
            Round.objects.all().delete()
            self.event.delete()
            self.wheel.delete()
            self.q1.delete()

            assert not Event.objects.filter(name="Корпоратив ОАО «Доломит» 2026").exists()

            # Import back from the zip package
            imported_event = import_event(zip_path, activate=True)

            assert imported_event.name == "Корпоратив ОАО «Доломит» 2026"
            assert imported_event.is_active is True
            assert imported_event.rules["word_bonus"] == 500
            assert imported_event.theme.name == "Праздничный Доломит"
            assert imported_event.theme.colors["color_gold"] == "#f4c430"

            # Check question
            q = Question.objects.get(word="ДОЛОМИТ")
            assert q.text == "Минерал и природная карбонатная порода"
            assert q.tags.filter(name="производство").exists()

            # Check wheel & sectors
            wheel = Wheel.objects.get(name="Основной барабан")
            sectors = list(wheel.sectors.all().order_by("order"))
            assert len(sectors) == 2
            assert sectors[0].label == "100"
            assert sectors[0].value == 100
            assert sectors[1].label == "Б"
            assert sectors[1].effect.name == "Банкрот"

            # Check prize
            prizes = list(imported_event.prizes.all())
            assert len(prizes) == 1
            assert prizes[0].name == "Набор сувениров"
            assert prizes[0].cost == 300

            # Check round
            rounds = list(imported_event.rounds.all())
            assert len(rounds) == 1
            assert rounds[0].order == 1
            assert rounds[0].question == q
            assert rounds[0].wheel == wheel
            assert rounds[0].prize == prizes[0]

            # Check players
            players = list(imported_event.players.all())
            assert len(players) == 1
            assert players[0].name == "Иван Иванов"
            assert players[0].team == "Цех № 1"

    def test_management_commands_export_and_import(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_file = str(Path(tmpdir) / "cmd_package.zip")

            # Call export_event command
            call_command("export_event", event_id=self.event.id, output=zip_file)
            assert Path(zip_file).is_file()

            # Call import_event command
            call_command("import_event", zip_file)
            assert Event.objects.filter(name="Корпоратив ОАО «Доломит» 2026").exists()
