from django.contrib import admin
from django.urls import path, include, reverse_lazy
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.conf import settings
from django.conf.urls.static import static

from students.views import daily_tasks_webhook


def health(request):
    return HttpResponse('ok', status=200)


urlpatterns = [
    path('', include('students.urls')),          # landing_view is registered at '' inside students.urls
    path('health/', health),
    path('webhooks/daily-tasks/', daily_tasks_webhook, name='daily_tasks_webhook'),
    path('admin/', admin.site.urls),
    path('courses/', include('courses.urls')),
    path('documents/', include('documents.urls')),
    path('handbook/', include('handbook.urls')),
    path('staff/',       include('staff.urls')),
    path('evaluations/', include('evaluations.urls')),
    path('instructor/',  include('instructor.urls')),
    path('calendar/',    include('schedule.urls')),
    path('grades/',      include('grades.urls')),

    # Password reset — shared across student/staff/instructor accounts, all
    # backed by the same Student model.
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='auth/password_reset_form.html',
        email_template_name='auth/password_reset_email.txt',
        subject_template_name='auth/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done'),
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='auth/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='auth/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete'),
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='auth/password_reset_complete.html',
    ), name='password_reset_complete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
