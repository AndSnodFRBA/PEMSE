from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static


def health(request):
    return HttpResponse("ok")


urlpatterns = [
    path('', health),
    path('health/', health),
    path('admin/', admin.site.urls),
    path('', include('students.urls')),
    path('courses/', include('courses.urls')),
    path('documents/', include('documents.urls')),
    path('handbook/', include('handbook.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
