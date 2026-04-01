from django.urls import path
from . import views

urlpatterns = [
    path('',              views.course_list_view, name='course_list'),
    path('<int:course_id>/enroll/', views.enroll_view, name='enroll'),
]
