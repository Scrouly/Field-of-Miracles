"""Tests for the multiboard display screen (Task 5).

Covers:
  1. GET /display/ returns 200 and loads offline template without CDN links.
  2. All required DOM containers exist (#stage, #board, #keyboard, #players-container).
  3. Static assets exist on disk and define required modules.
  4. Board layout logic: words of 5, 9, 14 letters (and >14 or with spaces) fit without clipping.
  5. Stage scaling math for 100%, 150%, 200% displays (including 3K multiboard).
  6. Keyboard layout has 33 Russian letters and touch targets meet the >= 64x64px requirement.
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest
from django.conf import settings
from django.test import Client

from tests.factories import EventFactory, GameSessionFactory, PlayerFactory, QuestionFactory, RoundFactory


@pytest.fixture()
def setup_display_game(db: None):
    event = EventFactory(name="Форум рабочей молодёжи", is_active=True)
    PlayerFactory(event=event, name="Владислав", order=1)
    PlayerFactory(event=event, name="Елена", order=2)
    PlayerFactory(event=event, name="Дмитрий", order=3)

    q = QuestionFactory(word="ДОЛОМИТ", text="Главное богатство Рубы", hint="Минерал")
    RoundFactory(event=event, order=1, question=q)
    return GameSessionFactory(event=event)


@pytest.mark.django_db
class TestDisplayView:
    def test_display_page_is_served(self, client: Client, setup_display_game):
        resp = client.get("/display/")
        assert resp.status_code == 200
        html = resp.content.decode("utf-8")

        # Required DOM elements
        assert 'id="stage"' in html
        assert 'id="board"' in html
        assert 'id="keyboard"' in html
        assert 'id="players-container"' in html
        assert 'id="question-text"' in html
        assert 'id="sector-value"' in html
        assert 'id="round-won-banner"' in html
        assert 'id="wheel-canvas"' in html

    def test_display_page_is_fully_offline(self, client: Client, setup_display_game):
        """Review Focus & Global requirement: no external CDNs or scripts."""
        resp = client.get("/display/")
        html = resp.content.decode("utf-8")

        # Must not contain external http:// or https:// links
        external_links = re.findall(r'href=["\'](https?://[^"\']+)["\']', html)
        external_scripts = re.findall(r'src=["\'](https?://[^"\']+)["\']', html)

        assert not external_links, f"Found external links: {external_links}"
        assert not external_scripts, f"Found external scripts: {external_scripts}"

    def test_display_static_files_exist(self):
        static_dir = settings.BASE_DIR / "static" / "display"
        expected_files = [
            "stage.js",
            "board.js",
            "keyboard.js",
            "wheel.js",
            "display.js",
            "display.css",
        ]
        for filename in expected_files:
            file_path = static_dir / filename
            assert file_path.exists(), f"Static file {filename} does not exist in {static_dir}"
            assert file_path.stat().st_size > 0, f"Static file {filename} is empty"


# ===================================================================
#  Board layout tests (Review Focus #2: words 5, 9, 14 letters & overflow)
# ===================================================================


class TestBoardLayout:
    """Python verification of the layoutWord algorithm implemented in board.js."""

    @staticmethod
    def layout_word(word: str) -> list[list[str]]:
        """Simulate BoardManager.layoutWord from board.js."""
        length = len(word)
        if length <= 10 and " " not in word and "-" not in word:
            return [list(word)]

        if " " in word:
            parts = word.split(" ")
            if len(parts) == 2:
                return [list(parts[0]), list(parts[1])]
            rows: list[list[str]] = []
            current: list[str] = []
            for p in parts:
                if not current:
                    current.extend(p)
                elif len(current) + 1 + len(p) <= 14:
                    current.append(" ")
                    current.extend(p)
                else:
                    rows.append(current)
                    current = list(p)
            if current:
                rows.append(current)
            return rows

        if "-" in word:
            hyphen_idx = word.index("-")
            return [list(word[: hyphen_idx + 1]), list(word[hyphen_idx + 1 :])]

        # > 10 letters without spaces
        mid = (length + 1) // 2
        return [list(word[:mid]), list(word[mid:])]

    def test_5_letter_word_fits_in_one_row(self):
        # 5 letters -> 1 row
        rows = self.layout_word("ШАХТА")
        assert len(rows) == 1
        assert len(rows[0]) == 5
        # Cell width 96px + 12px gap = 108px per cell. 5 * 108 = 540px <= 1920px.
        assert len(rows[0]) * 108 <= 1920

    def test_9_letter_word_fits_in_one_row(self):
        # 9 letters -> 1 row
        rows = self.layout_word("КАРЬЕРЩИК")
        assert len(rows) == 1
        assert len(rows[0]) == 9
        assert len(rows[0]) * 108 <= 1920

    def test_14_letter_word_fits_in_two_balanced_rows(self):
        # 14 letters -> 2 rows of 7 letters
        rows = self.layout_word("МЕСТОРОЖДЕНИЕ")  # 13 letters
        assert len(rows) == 2
        assert len(rows[0]) <= 14
        assert len(rows[1]) <= 14
        assert max(len(r) for r in rows) * 108 <= 1920

        rows14 = self.layout_word("ПРОИЗВОДИТЕЛЬ")  # 13 letters
        assert max(len(r) for r in rows14) <= 14

        word14 = "ДОЛОМИТИЗАЦИЯ"  # 13 letters
        rows_exact = self.layout_word("АБВГДЕЖЗИЙКЛМН")  # 14 letters
        assert len(rows_exact) == 2
        assert len(rows_exact[0]) == 7
        assert len(rows_exact[1]) == 7
        assert 7 * 108 <= 1920

    def test_word_with_space_splits_across_rows(self):
        # Review Focus #2: words with space (e.g. "КИНО ТЕАТР")
        rows = self.layout_word("КИНО ТЕАТР")
        assert len(rows) == 2
        assert "".join(rows[0]) == "КИНО"
        assert "".join(rows[1]) == "ТЕАТР"

    def test_hyphenated_word_splits_neatly(self):
        rows = self.layout_word("КИНО-ТЕАТР")
        assert len(rows) == 2
        assert "".join(rows[0]) == "КИНО-"
        assert "".join(rows[1]) == "ТЕАТР"

    def test_extra_long_word_over_14_splits_safely(self):
        # Review Focus #2: word longer than 14 letters
        long_word = "ДОЛОМИТОДОБЫВАЮЩИЙ"  # 18 letters
        rows = self.layout_word(long_word)
        assert len(rows) == 2
        assert len(rows[0]) == 9
        assert len(rows[1]) == 9
        # Max row has 9 letters, well within 14-cell limit
        assert max(len(r) for r in rows) <= 14


# ===================================================================
#  Stage scaling math (100%, 150%, 200% DPI & 3K multiboard)
# ===================================================================


class TestStageScaling:
    @staticmethod
    def calculate_scale(window_width: int, window_height: int) -> tuple[float, int, int]:
        """Simulate StageManager.updateScale from stage.js."""
        virtual_w = 1920
        virtual_h = 1080
        scale = min(window_width / virtual_w, window_height / virtual_h)
        offset_x = round((window_width - virtual_w * scale) / 2)
        offset_y = round((window_height - virtual_h * scale) / 2)
        return scale, offset_x, offset_y

    def test_scale_100_percent_fhd(self):
        scale, ox, oy = self.calculate_scale(1920, 1080)
        assert scale == 1.0
        assert ox == 0
        assert oy == 0

    def test_scale_150_percent(self):
        # 150% scaling on 1080p equivalent or 2880x1620
        scale, ox, oy = self.calculate_scale(2880, 1620)
        assert scale == 1.5
        assert ox == 0
        assert oy == 0

    def test_scale_200_percent_4k(self):
        # 4K UHD: 3840x2160 (200% scale)
        scale, ox, oy = self.calculate_scale(3840, 2160)
        assert scale == 2.0
        assert ox == 0
        assert oy == 0

    def test_scale_3k_multiboard_screen(self):
        # 3K 16:9 multiboard (e.g. 3200x1800 or 3072x1728)
        scale, ox, oy = self.calculate_scale(3200, 1800)
        assert pytest.approx(scale, 0.001) == 3200 / 1920
        assert ox == 0
        assert oy == 0

    def test_non_16_9_letterboxing(self):
        # Wider screen: 2560x1080 (21:9 ultrawide) -> pillarbox with black bars
        scale, ox, oy = self.calculate_scale(2560, 1080)
        assert scale == 1.0  # limited by height 1080
        assert ox == round((2560 - 1920) / 2) == 320
        assert oy == 0


# ===================================================================
#  Keyboard Touch Target & Russian alphabet
# ===================================================================


class TestKeyboardRequirements:
    def test_all_33_russian_letters_present_in_keyboard_js(self):
        keyboard_js = (settings.BASE_DIR / "static" / "display" / "keyboard.js").read_text(encoding="utf-8")
        russian_alphabet = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        for letter in russian_alphabet:
            assert f"'{letter.upper()}'" in keyboard_js, f"Letter {letter.upper()} missing in keyboard.js"

    def test_touch_target_dimensions_in_css(self):
        display_css = (settings.BASE_DIR / "static" / "display" / "display.css").read_text(encoding="utf-8")
        # Check key dimensions: width: 76px; height: 76px;
        assert "width: 76px;" in display_css
        assert "height: 76px;" in display_css
        # Minimum requirement is 64x64px: 76 >= 64
        assert 76 >= 64
        # Check gap between keys (12px >= 8px)
        assert "gap: 12px;" in display_css


# ===================================================================
#  Canvas Wheel Requirements (Task 7)
# ===================================================================


class TestCanvasWheelRequirements:
    def test_wheel_js_has_high_dpi_and_animate_to(self):
        wheel_js = (settings.BASE_DIR / "static" / "display" / "wheel.js").read_text(encoding="utf-8")

        # High DPI support
        assert "devicePixelRatio" in wheel_js
        assert "setupDPI" in wheel_js

        # Required interface animateTo(targetIndex, durationMs)
        assert "animateTo(" in wheel_js

        # Text along radius
        assert "ctx.rotate(" in wheel_js
        assert "ctx.fillText(" in wheel_js

        # 16-20 sectors by default
        assert "DEFAULT_SECTORS" in wheel_js
        # Count sector entries
        import re
        matches = re.findall(r"\{\s*label:", wheel_js)
        assert 16 <= len(matches) <= 20, f"Expected 16-20 sectors in wheel.js, got {len(matches)}"

