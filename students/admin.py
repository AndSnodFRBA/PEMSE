from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    Announcement, CognitiveExamRecord, CourseCompletionRecord,
    CourseReportRecord, EntranceRequirementRecord,
    PatientContactRecord, PaymentHistory, PaymentRecord,
    PsychomotorSkillRecord, ReminderLog, SiteSettings, Student, StudentNote,
)


@admin.register(Student)
class StudentAdmin(UserAdmin):
    list_display  = ['email', 'get_full_name', 'enroll_status', 'reg_submitted',
                     'handbook_signed', 'contract_signed', 'date_joined']
    list_filter   = ['enroll_status', 'reg_submitted', 'handbook_signed', 'contract_signed']
    search_fields = ['email', 'first_name', 'last_name', 'reg_conf_number']
    ordering      = ['-date_joined']
    readonly_fields = ['date_joined', 'last_login', 'reg_conf_number',
                       'contract_signed_at', 'handbook_signed_at', 'reg_submitted_at']

    fieldsets = (
        ('Account',      {'fields': ('email', 'username', 'password')}),
        ('Personal',     {'fields': ('first_name', 'last_name', 'date_of_birth',
                                     'phone', 'ok_to_text')}),
        ('Address',      {'fields': ('address', 'city', 'state', 'zip_code')}),
        ('Enrollment',   {'fields': ('enroll_status', 'reg_submitted', 'reg_submitted_at',
                                     'reg_conf_number', 'shirt_size')}),
        ('Signatures',   {'fields': ('contract_signed', 'contract_sig_name', 'contract_signed_at',
                                     'handbook_signed', 'handbook_sig_name', 'handbook_signed_at')}),
        ('Permissions',  {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups')}),
        ('Dates',        {'fields': ('date_joined', 'last_login')}),
    )
    add_fieldsets = (
        (None, {'fields': ('email', 'first_name', 'last_name', 'password1', 'password2')}),
    )


@admin.register(PaymentRecord)
class PaymentRecordAdmin(admin.ModelAdmin):
    list_display  = ['student', 'method', 'pay_option', 'dept_name', 'updated_at']
    list_filter   = ['method', 'pay_option']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'dept_name']


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display  = ['student', 'amount', 'payment_date', 'method', 'check_number', 'recorded_by', 'created_at']
    list_filter   = ['method', 'payment_date']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'check_number', 'notes']
    ordering      = ['-payment_date']
    date_hierarchy = 'payment_date'


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display  = ['student', 'rule_key', 'channel', 'sent_by', 'sent_at']
    list_filter   = ['channel', 'rule_key']
    search_fields = ['student__email', 'student__first_name', 'student__last_name']
    date_hierarchy = 'sent_at'
    raw_id_fields = ('student', 'sent_by')


@admin.register(StudentNote)
class StudentNoteAdmin(admin.ModelAdmin):
    list_display  = ['student', 'note_type', 'created_by', 'created_at']
    list_filter   = ['note_type']
    search_fields = ['student__email', 'student__first_name', 'student__last_name', 'body']
    raw_id_fields = ('student', 'created_by')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display  = ['title', 'is_active', 'created_at', 'created_by']
    list_filter   = ['is_active']
    search_fields = ['title', 'body']


# ── 172 NAC Compliance Models ─────────────────────────────────────────────────

@admin.register(CognitiveExamRecord)
class CognitiveExamRecordAdmin(admin.ModelAdmin):
    list_display   = ['student', 'exam_name', 'exam_date', 'score', 'passed', 'attempt_number', 'recorded_by']
    list_filter    = ['passed', 'exam_date']
    search_fields  = ['student__first_name', 'student__last_name', 'exam_name']
    date_hierarchy = 'exam_date'
    raw_id_fields  = ('student', 'recorded_by')


@admin.register(PsychomotorSkillRecord)
class PsychomotorSkillRecordAdmin(admin.ModelAdmin):
    list_display   = ['student', 'skill_name', 'evaluation_date', 'passed', 'attempt_number', 'evaluator_name']
    list_filter    = ['passed', 'evaluation_date']
    search_fields  = ['student__first_name', 'student__last_name', 'skill_name', 'evaluator_name']
    date_hierarchy = 'evaluation_date'
    raw_id_fields  = ('student', 'recorded_by')


@admin.register(PatientContactRecord)
class PatientContactRecordAdmin(admin.ModelAdmin):
    list_display  = ['student', 'contact_date', 'site_name', 'contact_type', 'supervisor_name',
                     'iv_start_attempted', 'iv_start_successful',
                     'airway_placement_attempted', 'airway_placement_successful']
    list_filter   = ['contact_type', 'contact_date', 'iv_start_attempted', 'airway_placement_attempted']
    search_fields = ['student__first_name', 'student__last_name', 'site_name', 'supervisor_name']
    date_hierarchy = 'contact_date'
    raw_id_fields  = ('student',)


@admin.register(EntranceRequirementRecord)
class EntranceRequirementRecordAdmin(admin.ModelAdmin):
    list_display  = ['student', 'requirement_name', 'verified', 'document_on_file', 'verified_date', 'verified_by']
    list_filter   = ['verified', 'document_on_file']
    search_fields = ['student__first_name', 'student__last_name', 'requirement_name']
    raw_id_fields = ('student', 'verified_by')


@admin.register(CourseCompletionRecord)
class CourseCompletionRecordAdmin(admin.ModelAdmin):
    list_display  = ['student', 'course', 'completion_date', 'withdrew', 'total_hours',
                     'certificate_issued', 'nremt_eligibility_sent']
    list_filter   = ['withdrew', 'certificate_issued', 'nremt_eligibility_sent']
    search_fields = ['student__first_name', 'student__last_name', 'course__name', 'verified_by_name']
    raw_id_fields = ('student',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Student & Course',   {'fields': ('student', 'course')}),
        ('Completion',         {'fields': ('completion_date', 'withdrew', 'withdrawal_date', 'withdrawal_reason')}),
        ('Hours',              {'fields': ('total_hours', 'didactic_hours', 'clinical_hours', 'field_internship_hours')}),
        ('Official Verification', {'fields': ('verified_by_name', 'verified_by_title', 'verification_date')}),
        ('Certificate & NREMT',{'fields': ('certificate_issued', 'certificate_issued_date',
                                            'nremt_eligibility_sent', 'nremt_eligibility_date')}),
        ('Timestamps',         {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(CourseReportRecord)
class CourseReportRecordAdmin(admin.ModelAdmin):
    list_display  = ['course', 'students_enrolled', 'students_completed', 'pass_rate',
                     'report_submitted_to_department', 'report_submitted_date', 'submission_deadline']
    list_filter   = ['report_submitted_to_department']
    search_fields = ['course__name', 'instructor_names', 'training_agency_name']
    readonly_fields = ('created_at',)
    fieldsets = (
        ('Course',        {'fields': ('course', 'training_agency_name', 'course_location', 'instructor_names')}),
        ('Enrollment',    {'fields': ('students_enrolled', 'students_withdrew', 'students_completed')}),
        ('Hours',         {'fields': ('total_didactic_hours', 'total_clinical_hours', 'total_field_hours')}),
        ('Submission',    {'fields': ('report_submitted_to_department', 'report_submitted_date',
                                      'submission_deadline', 'notes')}),
        ('Timestamps',    {'fields': ('created_at',)}),
    )


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Medical Director', {'fields': ('medical_director_name', 'medical_director_phone',
                                          'medical_director_title')}),
        ('Agency',            {'fields': ('agency_name', 'agency_address', 'agency_phone', 'agency_email',
                                           'agency_director', 'agency_director_title',
                                           'asst_director', 'asst_director_title')}),
        ('Regulatory',        {'fields': ('ne_approval_number',)}),
        ('Timestamps',        {'fields': ('updated_at',)}),
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
