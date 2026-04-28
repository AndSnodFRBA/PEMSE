from django.urls import path
from . import views
from evaluations import views as eval_views

urlpatterns = [
    path('',                                   views.staff_dashboard,       name='staff_dashboard'),
    path('login/',                             views.staff_login_view,      name='staff_login'),
    path('logout/',                            views.staff_logout_view,     name='staff_logout'),
    path('students/<int:pk>/',                 views.student_detail,        name='staff_student_detail'),
    path('students/<int:pk>/edit/',            views.student_edit,          name='staff_student_edit'),
    path('students/<int:pk>/pdf/',             views.student_pdf,           name='staff_student_pdf'),
    path('students/<int:pk>/add-payment/',     views.add_payment,           name='staff_add_payment'),
    path('documents/<int:doc_id>/review/',     views.review_document,       name='staff_review_document'),
    path('documents/<int:doc_id>/download/',   views.document_download,     name='staff_document_download'),
    path('invite/',                            views.invite_student,        name='staff_invite'),
    path('announcements/',                     views.announcement_list,     name='staff_announcements'),
    path('announcements/new/',                 views.announcement_create,   name='staff_announcement_create'),
    path('announcements/<int:pk>/edit/',       views.announcement_edit,     name='staff_announcement_edit'),
    path('announcements/<int:pk>/delete/',     views.announcement_delete,   name='staff_announcement_delete'),
    path('courses/',                           views.course_list,           name='staff_course_list'),
    path('courses/add/',                       views.course_add,            name='staff_course_add'),
    path('courses/<int:pk>/edit/',             views.course_edit,           name='staff_course_edit'),
    path('courses/<int:pk>/delete/',           views.course_delete,            name='staff_course_delete'),
    path('evaluations/',                       eval_views.staff_eval_list,     name='staff_eval_list'),
    path('evaluations/<int:pk>/',              eval_views.staff_eval_detail,   name='staff_eval_detail'),
    path('evaluations/<int:pk>/pdf/',          eval_views.staff_eval_pdf,      name='staff_eval_pdf'),
    # Compliance — cognitive exams
    path('students/<int:pk>/add-exam/',                             views.add_cognitive_exam,       name='staff_add_exam'),
    path('students/<int:pk>/exams/<int:exam_pk>/delete/',           views.delete_cognitive_exam,    name='staff_delete_exam'),
    # Compliance — psychomotor skills
    path('students/<int:pk>/add-skill/',                            views.add_psychomotor_skill,    name='staff_add_skill'),
    path('students/<int:pk>/skills/<int:skill_pk>/delete/',         views.delete_psychomotor_skill, name='staff_delete_skill'),
    # Compliance — patient contacts
    path('students/<int:pk>/add-contact/',                          views.add_patient_contact,      name='staff_add_contact'),
    path('students/<int:pk>/contacts/<int:contact_pk>/delete/',     views.delete_patient_contact,   name='staff_delete_contact'),
    # Compliance — entrance requirements & completion
    path('students/<int:pk>/entrance-reqs/',                        views.save_entrance_requirements, name='staff_save_entrance_reqs'),
    path('students/<int:pk>/completion/',                           views.save_completion_record,   name='staff_save_completion'),
    path('students/<int:pk>/completion/pdf/',                       views.verification_pdf,         name='staff_verification_pdf'),
    # Course reports
    path('course-reports/',                                         views.course_reports,           name='staff_course_reports'),
    path('course-reports/<int:course_pk>/',                         views.course_report_detail,     name='staff_course_report_detail'),
    path('course-reports/<int:course_pk>/pdf/',                     views.department_report_pdf,    name='staff_department_report_pdf'),
    # NREMT pass rates
    path('pass-rates/',                                             views.pass_rates,               name='staff_pass_rates'),
    # Course evaluations
    path('course-evaluations/',                                     views.course_eval_overview,     name='staff_course_eval_overview'),
    path('course-evaluations/send/',                                views.course_eval_send,         name='staff_course_eval_send'),
    path('course-evaluations/<int:pk>/',                            views.course_eval_detail,       name='staff_course_eval_detail'),
    path('course-evaluations/results/<int:course_pk>/',             views.course_eval_results,      name='staff_course_eval_results'),
    path('course-evaluations/results/<int:course_pk>/csv/',         views.course_eval_results_csv,  name='staff_course_eval_results_csv'),
    path('course-evaluations/results/<int:course_pk>/pdf/',         views.course_eval_results_pdf,  name='staff_course_eval_results_pdf'),
    # Instructor management
    path('instructors/',                              views.staff_instructor_list,         name='staff_instructor_list'),
    path('instructors/add/',                          views.staff_instructor_add,          name='staff_instructor_add'),
    path('instructors/<int:pk>/',                     views.staff_instructor_detail,       name='staff_instructor_detail'),
    path('instructors/<int:pk>/assign-course/',       views.staff_instructor_assign_course, name='staff_instructor_assign_course'),
    path('instructors/<int:pk>/verify-hours/',        views.staff_instructor_verify_hours, name='staff_instructor_verify_hours'),
    path('instructors/<int:pk>/observe/',             views.staff_instructor_observe,      name='staff_instructor_observe'),
    path('instructors/<int:pk>/meeting/',             views.staff_instructor_meeting,      name='staff_instructor_meeting'),
    path('instructors/<int:pk>/remediation/',         views.staff_instructor_remediation,  name='staff_instructor_remediation'),
]
