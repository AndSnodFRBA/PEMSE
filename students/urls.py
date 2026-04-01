from django.urls import path
from . import views

urlpatterns = [
    path('',          views.dashboard_view,       name='dashboard'),
    path('login/',    views.login_view,            name='login'),
    path('register/', views.register_view,         name='register'),
    path('logout/',   views.logout_view,           name='logout'),
    path('profile/',  views.profile_view,          name='profile'),
    path('register/form/', views.registration_form_view, name='registration_form'),
    path('dashboard/', views.dashboard_view,       name='dashboard'),
]
