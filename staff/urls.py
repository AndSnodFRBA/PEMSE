from django.urls import path
from . import views
from evaluations import views as eval_views
from grades import views as grade_views
from students.views import registration_pdf_view

urlpatterns = [
    path('',                                   views.staff_dashboard,       name='staff_dashboard'),
    path('login/',                             views.staff_login_view,      name='staff_login'),
    path('logout/',                            views.staff_logout_view,     name='staff_logout'),
    path('students/<int:pk>/',                 views.student_detail,        name='staff_student_detail'),
    path('students/<int:pk>/edit/',            views.student_edit,          name='staff_student_edit'),
    path('students/<int:student_id>/pdf/',     registration_pdf_view,       name='staff_student_pdf'),
    path('students/<int:pk>/invoice/',         views.invoice_pdf,           name='staff_invoice_pdf'),
    path('students/<int:pk>/add-payment/',     views.add_payment,           name='staff_add_payment'),
    path('payments/<int:payment_id>/receipt/', views.payment_receipt_pdf,   name='staff_payment_receipt'),
    path('attendance/<int:session_id>/pdf/',   views.staff_attendance_pdf,  name='staff_attendance_pdf'),
    path('students/<int:pk>/payment-info/',    views.edit_payment_info,     name='staff_edit_payment_info'),
    path('students/<int:pk>/add-note/',        views.add_student_note,      name='staff_add_note'),
    path('students/<int:pk>/notes/<int:note_pk>/delete/', views.delete_student_note, name='staff_delete_note'),
    path('students/<int:pk>/assign-course/',   views.assign_course,         name='staff_assign_course'),
    path('documents/<int:doc_id>/review/',     views.review_document,       name='staff_review_document'),
    path('documents/<int:doc_id>/download/',   views.document_download,     name='staff_document_download'),
    path('documents/bulk-approve/',            views.bulk_approve_documents, name='staff_bulk_approve_documents'),
    path('documents/pending/',                 views.document_review_queue, name='staff_document_queue'),
    path('students/export/csv/',               views.export_students_csv,   name='staff_export_students_csv'),
    path('invite/',                            views.invite_student,        name='staff_invite'),
    path('invite/<int:pk>/resend/',            views.resend_student_invite, name='staff_invite_resend'),
    path('invite/<int:pk>/edit/',              views.edit_student_invite,   name='staff_invite_edit'),
    path('announcements/',                     views.announcement_list,     name='staff_announcements'),
    path('announcements/new/',                 views.announcement_create,   name='staff_announcement_create'),
    path('announcements/<int:pk>/edit/',       views.announcement_edit,     name='staff_announcement_edit'),
    path('announcements/<int:pk>/delete/',     views.announcement_delete,   name='staff_announcement_delete'),
    path('courses/',                           views.course_list,           name='staff_course_list'),
    path('courses/add/',                       views.course_add,            name='staff_course_add'),
    path('courses/<int:pk>/',                  views.course_detail,         name='staff_course_detail'),
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
    path('course-reports/<int:report_id>/dhhs-pdf/',                views.dhhs_report_pdf,           name='staff_dhhs_report_pdf'),
    path('course-reports/<int:report_id>/mark-submitted/',          views.mark_report_submitted,     name='staff_mark_report_submitted'),
    # NREMT pass rates
    path('pass-rates/',                                             views.pass_rates,               name='staff_pass_rates'),
    path('pass-rates/quick-update/<int:record_id>/',                views.pass_rates_quick_update,   name='staff_pass_rates_quick_update'),
    # Backups
    path('backups/',                                                views.backup_list,             name='staff_backup_list'),
    # Reminders
    path('reminders/',                                              views.reminder_dashboard,       name='staff_reminder_dashboard'),
    path('reminders/send/',                                         views.reminder_bulk_send,       name='staff_reminder_send'),
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
    # Staff account management
    path('accounts/',                                 views.staff_account_list,            name='staff_account_list'),
    path('accounts/invite/',                          views.staff_account_invite,          name='staff_account_invite'),
    path('accounts/invite/<int:pk>/resend/',          views.resend_staff_invite,           name='staff_account_invite_resend'),
    path('accounts/invite/<int:pk>/edit/',            views.edit_staff_invite,             name='staff_account_invite_edit'),
    path('accounts/invite/<uuid:token>/',             views.staff_invite_accept,           name='staff_invite_accept'),
    # Calendar
    path('calendar/',                          views.staff_calendar,        name='staff_calendar'),
    path('calendar/add/',                      views.staff_calendar_add,    name='staff_calendar_add'),
    path('calendar/<int:pk>/edit/',            views.staff_calendar_edit,   name='staff_calendar_edit'),
    path('calendar/<int:pk>/delete/',          views.staff_calendar_delete, name='staff_calendar_delete'),
    # Grades
    path('grades/',                                  grade_views.staff_grade_overview,        name='staff_grade_overview'),
    path('grades/report/<int:course_id>/',           grade_views.staff_grade_report,           name='staff_grade_report'),
    path('grades/report/<int:course_id>/csv/',       grade_views.staff_grade_report_csv,       name='staff_grade_report_csv'),
    path('grades/<int:student_id>/',                 grade_views.staff_gradebook_detail,       name='staff_gradebook_detail'),
    path('grades/<int:student_id>/create/',          grade_views.staff_gradebook_create,       name='staff_gradebook_create'),
    path('grades/<int:student_id>/quiz/<int:quiz_number>/', grade_views.staff_quiz_edit,        name='staff_quiz_edit'),
    path('grades/<int:student_id>/exam/<str:exam_id>/',     grade_views.staff_exam_edit,        name='staff_exam_edit'),
    path('grades/<int:student_id>/worksheet/<str:worksheet_id>/', grade_views.staff_worksheet_edit, name='staff_worksheet_edit'),
    path('grades/<int:student_id>/skill/<str:skill_id>/',   grade_views.staff_skill_edit,       name='staff_skill_edit'),
    path('grades/<int:student_id>/participation/deduct/',   grade_views.staff_participation_deduct, name='staff_participation_deduct'),
    path('grades/<int:student_id>/fisdap/',                 grade_views.staff_fisdap_edit,      name='staff_fisdap_edit'),
]
