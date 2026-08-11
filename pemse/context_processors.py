from django.conf import settings


def site_settings(request):
    return {'BETA_MODE': settings.BETA_MODE}
