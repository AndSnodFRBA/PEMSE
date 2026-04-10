from django.contrib import admin

from .models import ClinicalRotation, PreceptorEvaluation, StudentSiteEvaluation


@admin.register(ClinicalRotation)
class ClinicalRotationAdmin(admin.ModelAdmin):
    list_display  = ('student', 'site_name', 'site_type', 'rotation_date', 'hours_completed', 'patient_contacts', 'created_at')
    list_filter   = ('site_type', 'rotation_date')
    search_fields = ('student__first_name', 'student__last_name', 'site_name', 'site_city')
    date_hierarchy = 'rotation_date'
    raw_id_fields  = ('student',)


@admin.register(PreceptorEvaluation)
class PreceptorEvaluationAdmin(admin.ModelAdmin):
    list_display   = ('rotation', 'preceptor_name', 'preceptor_email', 'status', 'completed_at', 'token_expires')
    list_filter    = ('status',)
    search_fields  = ('preceptor_name', 'preceptor_email', 'rotation__site_name')
    readonly_fields = ('token', 'token_expires', 'link_sent_at', 'completed_at', 'preceptor_ip')
    fieldsets = (
        ('Rotation', {'fields': ('rotation',)}),
        ('Preceptor Contact', {'fields': ('preceptor_name', 'preceptor_email', 'preceptor_title')}),
        ('Status & Token', {'fields': ('status', 'token', 'token_expires', 'link_sent_at', 'completed_at', 'preceptor_ip')}),
        ('Professional Behavior', {'fields': (
            'appearance_professional', 'punctuality', 'communication_patients',
            'communication_team', 'attitude_motivation',
        )}),
        ('Clinical Skills', {'fields': (
            'patient_assessment', 'clinical_skills_performance', 'critical_thinking',
            'medical_knowledge', 'documentation',
        )}),
        ('Overall', {'fields': ('overall_performance', 'recommended_to_pass')}),
        ('Written Feedback', {'fields': ('strengths', 'areas_for_improvement', 'additional_comments')}),
    )


@admin.register(StudentSiteEvaluation)
class StudentSiteEvaluationAdmin(admin.ModelAdmin):
    list_display  = ('rotation', 'completed_at', 'preceptor_overall', 'would_you_recommend')
    list_filter   = ('completed_at', 'would_you_recommend')
    search_fields = ('rotation__site_name', 'rotation__student__first_name', 'rotation__student__last_name')
    readonly_fields = ('completed_at',)
    fieldsets = (
        ('Rotation', {'fields': ('rotation', 'completed_at')}),
        ('Site Evaluation', {'fields': (
            'site_organization', 'site_learning_opportunities', 'site_equipment_available',
            'site_patient_volume', 'site_staff_welcoming', 'site_would_return',
        )}),
        ('Preceptor Evaluation', {'fields': (
            'preceptor_knowledge', 'preceptor_teaching_style', 'preceptor_feedback_quality',
            'preceptor_professionalism', 'preceptor_overall',
        )}),
        ('Written Feedback', {'fields': (
            'best_part_of_rotation', 'what_could_be_improved',
            'would_you_recommend', 'additional_comments',
        )}),
    )
