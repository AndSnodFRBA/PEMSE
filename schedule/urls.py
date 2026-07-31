from django.urls import path

from . import views

urlpatterns = [
    path('feed/<uuid:token>.ics', views.calendar_feed, name='calendar_feed'),
    path('feed/regenerate/', views.regenerate_feed_token, name='calendar_feed_regenerate'),
]
