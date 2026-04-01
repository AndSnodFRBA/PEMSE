from django.urls import path
from . import views

urlpatterns = [
    path('', views.handbook_view, name='handbook'),
]
