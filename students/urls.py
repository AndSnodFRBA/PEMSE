from django.urls import path
from . import views

urlpatterns = [
    path('',           views.landing_view,          name='landing'),
    path('dashboard/', views.dashboard_view,        name='dashboard'),
    path('login/',     views.login_view,            name='login'),
    path('register/',  views.register_view,         name='register'),
    path('logout/',    views.logout_view,           name='logout'),
    path('profile/',   views.profile_view,          name='profile'),
    path('register/form/', views.registration_form_view, name='registration_form'),
    path('register/pdf/',  views.registration_pdf_view,  name='registration_pdf'),
    path('register/invite/<uuid:token>/', views.register_with_invite, name='register_invite'),
    path('calendar/',  views.calendar_view, name='calendar'),
    path('notifications/',                    views.notifications_view,           name='notifications'),
    path('notifications/mark-read/<int:notif_id>/',  views.mark_notification_read,       name='mark_notification_read'),
    path('notifications/mark-all-read/',      views.mark_all_notifications_read,  name='mark_all_notifications_read'),
    path('notifications/delete/<int:notif_id>/', views.delete_notification,          name='delete_notification'),
]
