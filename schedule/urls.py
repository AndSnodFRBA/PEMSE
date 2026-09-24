from django.urls import path

from . import views

urlpatterns = [
    path('feed/<uuid:token>.ics', views.calendar_feed, name='calendar_feed'),
    path('feed/<uuid:token>/<int:course_id>.ics', views.calendar_course_feed, name='calendar_course_feed'),
    path('feed/regenerate/', views.regenerate_feed_token, name='calendar_feed_regenerate'),
]
