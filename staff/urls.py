from django.urls import path
from . import views

urlpatterns = [
    path('',                                   views.staff_dashboard,       name='staff_dashboard'),
    path('login/',                             views.staff_login_view,      name='staff_login'),
    path('logout/',                            views.staff_logout_view,     name='staff_logout'),
    path('students/<int:pk>/',                 views.student_detail,        name='staff_student_detail'),
    path('students/<int:pk>/edit/',            views.student_edit,          name='staff_student_edit'),
    path('students/<int:pk>/pdf/',             views.student_pdf,           name='staff_student_pdf'),
    path('documents/<int:doc_id>/review/',     views.review_document,       name='staff_review_document'),
    path('invite/',                            views.invite_student,        name='staff_invite'),
    path('announcements/',                     views.announcement_list,     name='staff_announcements'),
    path('announcements/new/',                 views.announcement_create,   name='staff_announcement_create'),
    path('announcements/<int:pk>/edit/',       views.announcement_edit,     name='staff_announcement_edit'),
    path('announcements/<int:pk>/delete/',     views.announcement_delete,   name='staff_announcement_delete'),
    path('courses/',                           views.course_list,           name='staff_course_list'),
    path('courses/add/',                       views.course_add,            name='staff_course_add'),
    path('courses/<int:pk>/edit/',             views.course_edit,           name='staff_course_edit'),
    path('courses/<int:pk>/delete/',           views.course_delete,         name='staff_course_delete'),
]
