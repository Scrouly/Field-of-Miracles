"""Views for the main site navigation and landing portal."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.core.models import Event


def index(request: HttpRequest) -> HttpResponse:
    """Главная страница: стартовый навигационный портал игры «Поле чудес»."""
    event_name = "Молодёжный форум ОАО «Доломит»"
    try:
        active_event = Event.objects.filter(is_active=True).first() or Event.objects.first()
        if active_event:
            event_name = active_event.name
    except Exception:
        pass

    context = {
        "event_name": event_name,
    }
    return render(request, "portal.html", context)
