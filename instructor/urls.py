from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('',        views.instructor_login_view,  name='instructor_login'),
    path('logout/', views.instructor_logout_view, name='instructor_logout'),

    # Dashboard
    path('dashboard/', views.instructor_dashboard, name='instructor_dashboard'),

    # Hours
    path('hours/',              views.instructor_hours,      name='instructor_hours'),
    path('hours/add/',          views.instructor_hours_add,  name='instructor_hours_add'),
    path('hours/<int:pk>/edit/',   views.instructor_hours_edit,   name='instructor_hours_edit'),
    path('hours/<int:pk>/delete/', views.instructor_hours_delete,  name='instructor_hours_delete'),
    path('hours/pdf/',             views.instructor_hours_pdf,     name='instructor_hours_pdf'),

    # Attendance
    path('attendance/',               views.instructor_attendance,        name='instructor_attendance'),
    path('attendance/add/',           views.instructor_attendance_add,    name='instructor_attendance_add'),
    path('attendance/<int:pk>/',      views.instructor_attendance_detail, name='instructor_attendance_detail'),
    path('attendance/<int:pk>/edit/', views.instructor_attendance_edit,   name='instructor_attendance_edit'),

    # Courses
    path('courses/',          views.instructor_courses,       name='instructor_courses'),
    path('courses/<int:pk>/', views.instructor_course_detail, name='instructor_course_detail'),

    # Documents
    path('documents/',               views.instructor_documents,        name='instructor_documents'),
    path('documents/add/',           views.instructor_document_add,     name='instructor_document_add'),
    path('documents/<int:pk>/edit/', views.instructor_document_edit,    name='instructor_document_edit'),
    path('documents/<int:pk>/delete/', views.instructor_document_delete, name='instructor_document_delete'),

    # Students
    path('students/<int:pk>/', views.instructor_student_detail, name='instructor_student_detail'),

    # Profile
    path('profile/', views.instructor_profile, name='instructor_profile'),

    # Observations
    path('observations/',                       views.instructor_observations,             name='instructor_observations'),
    path('observations/<int:pk>/acknowledge/', views.instructor_observation_acknowledge,  name='instructor_observation_acknowledge'),

    # Meetings
    path('meetings/',                       views.instructor_meetings,             name='instructor_meetings'),
    path('meetings/<int:pk>/acknowledge/', views.instructor_meeting_acknowledge,  name='instructor_meeting_acknowledge'),

    # Calendar
    path('calendar/',                    views.instructor_calendar,        name='instructor_calendar'),
    path('calendar/add/',                views.instructor_calendar_add,    name='instructor_calendar_add'),
    path('calendar/<int:pk>/edit/',      views.instructor_calendar_edit,   name='instructor_calendar_edit'),
    path('calendar/<int:pk>/delete/',    views.instructor_calendar_delete, name='instructor_calendar_delete'),
]
