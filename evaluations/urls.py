from django.urls import path

from . import views

urlpatterns = [
    path('',                                   views.rotation_log,         name='rotation_log'),
    path('add/',                               views.add_rotation,         name='rotation_add'),
    path('preceptor/<int:eval_id>/resend/',    views.resend_preceptor_eval, name='resend_preceptor_eval'),
    path('<int:pk>/site-eval/',                views.site_eval,            name='rotation_site_eval'),
    path('preceptor/<uuid:token>/',            views.preceptor_eval,       name='preceptor_eval'),
    path('preceptor/<uuid:token>/submitted/',  views.preceptor_submitted,  name='preceptor_submitted'),
    # Course evaluations (student-facing)
    path('course/',                            views.course_eval_list,     name='course_eval_list'),
    path('course/<uuid:token>/',               views.course_eval_form,     name='course_eval_form'),
    path('course/<uuid:token>/submitted/',     views.course_eval_submitted, name='course_eval_submitted'),
]
