from django.urls import path

from . import views

urlpatterns = [
    path('',                                 views.rotation_log,       name='rotation_log'),
    path('add/',                             views.add_rotation,       name='rotation_add'),
    path('<int:pk>/site-eval/',              views.site_eval,          name='rotation_site_eval'),
    path('preceptor/<uuid:token>/',          views.preceptor_eval,     name='preceptor_eval'),
    path('preceptor/<uuid:token>/submitted/', views.preceptor_submitted, name='preceptor_submitted'),
]
