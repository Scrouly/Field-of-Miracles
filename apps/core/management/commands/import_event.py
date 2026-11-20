"""Management command to import an Event from a ZIP package (Task 17)."""

from django.core.management.base import BaseCommand, CommandError

from apps.core.packaging import PackagingError, import_event


class Command(BaseCommand):
    help = "Импорт мероприятия и медиафайлов из ZIP-пакета"

    def add_arguments(self, parser):
        parser.add_argument(
            "zip_file",
            type=str,
            help="Путь к zip-файлу пакета мероприятия",
        )
        parser.add_argument(
            "--no-activate",
            action="store_true",
            help="Не делать импортированное мероприятие активным",
        )

    def handle(self, *args, **options):
        zip_file = options["zip_file"]
        activate = not options.get("no_activate", False)

        self.stdout.write(f"Импорт мероприятия из: {zip_file}...")
        try:
            event = import_event(zip_file, activate=activate)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Мероприятие «{event.name}» (ID={event.id}) успешно импортировано! "
                    f"Активно: {event.is_active}."
                )
            )
        except PackagingError as exc:
            raise CommandError(str(exc)) from exc
