from django.urls import path

from . import views

app_name = "whatsnew"

urlpatterns = [
    path("", views.note_list, name="list"),
    path("seen/", views.seen, name="seen"),
]
