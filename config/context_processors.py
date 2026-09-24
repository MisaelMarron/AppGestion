from django.conf import settings


def entorno(request):
    return {'demo_mode':settings.DEMO_MODE}
