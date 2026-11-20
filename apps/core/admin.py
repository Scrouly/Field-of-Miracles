"""Административный интерфейс моделей ядра игры «Поле чудес».

Предоставляет удобное редактирование вопросов, раундов, секторов,
игроков и призов без вмешательства в исходный код.
"""

from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from . import models


# ------------------------------------------------------------------ #
#  Инлайны
# ------------------------------------------------------------------ #


class PlayerInline(admin.TabularInline):
    model = models.Player
    extra = 1
    fields = ("order", "name", "team")


class RoundInline(admin.TabularInline):
    model = models.Round
    extra = 1
    fields = ("order", "type", "question", "wheel", "prize", "params")


class PrizeInline(admin.TabularInline):
    model = models.Prize
    extra = 0
    fields = ("name", "cost", "image")


class SectorInline(admin.TabularInline):
    model = models.Sector
    extra = 0
    fields = ("order", "label", "value", "color", "weight", "effect")


# ------------------------------------------------------------------ #
#  Модели контента
# ------------------------------------------------------------------ #


@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "theme", "is_active", "rounds_count", "players_count")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = [PlayerInline, RoundInline, PrizeInline]

    @admin.display(description="Туров")
    def rounds_count(self, obj: models.Event) -> int:
        return obj.rounds.count()

    @admin.display(description="Игроков")
    def players_count(self, obj: models.Event) -> int:
        return obj.players.count()


@admin.register(models.Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("word", "text", "hint", "difficulty", "display_tags")
    list_filter = ("difficulty", "tags")
    search_fields = ("word", "text", "hint", "tags__name")
    filter_horizontal = ("tags",)
    list_per_page = 25

    @admin.display(description="Теги")
    def display_tags(self, obj: models.Question) -> str:
        tag_names = list(obj.tags.values_list("name", flat=True))
        return ", ".join(tag_names) if tag_names else "—"

    def save_model(self, request, obj, form, change):
        # Автоматическая нормализация слова: заглавные буквы, обрезка пробелов
        if obj.word:
            obj.word = obj.word.strip().upper()
        super().save_model(request, obj, form, change)


@admin.register(models.Wheel)
class WheelAdmin(admin.ModelAdmin):
    list_display = ("name", "sectors_count")
    search_fields = ("name",)
    inlines = [SectorInline]

    @admin.display(description="Кол-во секторов")
    def sectors_count(self, obj: models.Wheel) -> int:
        return obj.sectors.count()


@admin.register(models.Sector)
class SectorAdmin(admin.ModelAdmin):
    list_display = ("wheel", "order", "label", "value", "color_badge", "weight", "effect")
    list_filter = ("wheel", "effect")
    search_fields = ("label", "wheel__name")
    ordering = ("wheel", "order")

    @admin.display(description="Цвет")
    def color_badge(self, obj: models.Sector) -> str:
        color = obj.color or "#1e90ff"
        return format_html(
            '<span style="display:inline-block;width:18px;height:18px;background:{};'
            'border-radius:3px;border:1px solid #aaa;vertical-align:middle;margin-right:4px;"></span> {}',
            color,
            color,
        )


@admin.register(models.Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("name", "team", "event", "order")
    list_filter = ("event",)
    search_fields = ("name", "team")
    ordering = ("event", "order")


@admin.register(models.Prize)
class PrizeAdmin(admin.ModelAdmin):
    list_display = ("name", "cost", "event")
    list_filter = ("event",)
    search_fields = ("name", "event__name")


@admin.register(models.Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ("event", "order", "type", "question", "wheel", "prize")
    list_filter = ("event", "type")
    search_fields = ("question__word", "question__text", "event__name")
    ordering = ("event", "order")


@admin.register(models.Effect)
class EffectAdmin(admin.ModelAdmin):
    list_display = ("name", "actions_summary")
    search_fields = ("name",)

    @admin.display(description="Список действий")
    def actions_summary(self, obj: models.Effect) -> str:
        if not obj.actions:
            return "—"
        summary_items: list[str] = []
        for a in obj.actions:
            if isinstance(a, str):
                summary_items.append(a)
            elif isinstance(a, dict):
                act_type = a.get("type", "")
                params = [f"{k}={v}" for k, v in a.items() if k != "type"]
                summary_items.append(f"{act_type}({', '.join(params)})" if params else act_type)
        return ", ".join(summary_items)


@admin.register(models.SoundBinding)
class SoundBindingAdmin(admin.ModelAdmin):
    list_display = ("event", "trigger", "sound")
    list_filter = ("event", "trigger")


@admin.register(models.GameSession)
class GameSessionAdmin(admin.ModelAdmin):
    list_display = ("pk", "event", "version", "started_at", "finished_at")
    list_filter = ("event", "finished_at")
    readonly_fields = ("state", "version", "started_at")


@admin.register(models.GameLog)
class GameLogAdmin(admin.ModelAdmin):
    list_display = ("session", "number", "action", "created_at")
    list_filter = ("action", "session")
    search_fields = ("action",)
    readonly_fields = ("session", "number", "action", "data", "created_at")


# Простая регистрация для моделей без сложной логики
admin.site.register(models.Theme)
admin.site.register(models.Tag)
admin.site.register(models.Sound)
