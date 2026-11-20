from django.contrib import admin

from . import models


class PlayerInline(admin.TabularInline):
    model = models.Player
    extra = 1


class RoundInline(admin.TabularInline):
    model = models.Round
    extra = 1


class PrizeInline(admin.TabularInline):
    model = models.Prize
    extra = 0


class SectorInline(admin.TabularInline):
    model = models.Sector
    extra = 0


@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "theme", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = [PlayerInline, RoundInline, PrizeInline]


@admin.register(models.Wheel)
class WheelAdmin(admin.ModelAdmin):
    search_fields = ("name",)
    inlines = [SectorInline]


@admin.register(models.Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("word", "text", "difficulty")
    search_fields = ("word", "text", "hint")
    filter_horizontal = ("tags",)


admin.site.register(models.Theme)
admin.site.register(models.Tag)
admin.site.register(models.Effect)
admin.site.register(models.Sector)
admin.site.register(models.Round)
admin.site.register(models.Player)
admin.site.register(models.Prize)
admin.site.register(models.Sound)
admin.site.register(models.SoundBinding)
admin.site.register(models.GameSession)
admin.site.register(models.GameLog)
