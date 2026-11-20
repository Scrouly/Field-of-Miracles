"""Management command to export an Event to a ZIP package (Task 17)."""

from pathlib import Path
from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Event
from apps.core.packaging import export_event


class Command(BaseCommand):
    help = "Экспорт мероприятия и всех медиафайлов в переносимый ZIP-архив"

    def add_arguments(self, parser):
        parser.add_argument(
            "--event-id",
            type=int,
            help="ID мероприятия (по умолчанию активное)",
        )
        parser.add_argument(
            "--name",
            type=str,
            help="Название мероприятия",
        )
        parser.add_argument(
            "--output",
            type=str,
            default="event_package.zip",
            help="Путь к результирующему .zip файлу (по умолчанию event_package.zip)",
        )

    def handle(self, *args, **options):
        event_id = options.get("event_id")
        name = options.get("name")
        output = options.get("output")

        if event_id:
            event = Event.objects.filter(pk=event_id).first()
            if not event:
                raise CommandError(f"Мероприятие с ID={event_id} не найдено")
        elif name:
            event = Event.objects.filter(name=name).first()
            if not event:
                raise CommandError(f"Мероприятие с названием '{name}' не найдено")
        else:
            event = Event.objects.filter(is_active=True).first() or Event.objects.first()
            if not event:
                raise CommandError("В базе данных нет мероприятий для экспорта")

        self.stdout.write(f"Экспорт мероприятия: «{event.name}» (ID={event.id})...")
        out_path = export_event(event, output)
        self.stdout.write(self.style.SUCCESS(f"Мероприятие успешно упаковано в: {out_path}"))
