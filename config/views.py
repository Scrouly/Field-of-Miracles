from django.http import HttpResponse

INDEX_HTML = (
    "<!doctype html>\n"
    '<html lang="ru"><head><meta charset="utf-8"><title>Поле чудес</title></head>'
    "<body></body></html>\n"
)


def index(request):
    """Пустая страница-заглушка: проверка, что сервер поднялся."""
    return HttpResponse(INDEX_HTML)
