from django.urls import path
from . import views

urlpatterns = [
    path('', views.student_grades_view, name='student_grades'),
    path('progress-report/', views.progress_report_pdf, name='progress_report_pdf'),
]
