from django.conf import settings


def map_settings(request):
    return {
        "yandex_api_key": settings.YANDEX_API_KEY,
    }
