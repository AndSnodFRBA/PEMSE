from django.contrib import admin

from .models import ClinicalRotation, CourseEvaluation, PreceptorEvaluation, StudentSiteEvaluation


@admin.register(CourseEvaluation)
class CourseEvaluationAdmin(admin.ModelAdmin):
    list_display   = ('student', 'course', 'eval_type', 'status', 'average_score', 'completed_at', 'created_at')
    list_filter    = ('eval_type', 'status', 'course')
    search_fields  = ('student__first_name', 'student__last_name', 'student__email')
    readonly_fields = ('token', 'created_at', 'completed_at')
    fieldsets = (
        ('Evaluation', {
            'fields': ('student', 'course', 'eval_type', 'status', 'token', 'created_by', 'created_at', 'completed_at')
        }),
        ('Section 1 — Course Content', {
            'fields': (
                'content_objectives_clear', 'content_material_relevant', 'content_material_current',
                'content_difficulty_appropriate', 'content_theory_lab_balance',
            )
        }),
        ('Section 2 — Instruction Quality', {
            'fields': (
                'instruction_knowledge', 'instruction_communication', 'instruction_feedback',
                'instruction_availability', 'instruction_preparation', 'instruction_respected_students',
            )
        }),
        ('Section 3 — Facilities & Resources', {
            'fields': (
                'facility_classroom_adequate', 'facility_equipment_adequate',
                'facility_supplies_adequate', 'facility_schedule_reasonable',
            )
        }),
        ('Section 4 — Online/Hybrid', {
            'fields': ('online_platform_easy_to_use', 'online_content_organized', 'online_support_available')
        }),
        ('Section 5 — Overall', {
            'fields': ('overall_satisfaction', 'overall_recommend_to_others', 'overall_prepared_for_nremt')
        }),
        ('End-of-Course Fields', {
            'fields': (
                'eoc_registration_process', 'eoc_staff_helpfulness', 'eoc_value_for_money',
                'eoc_would_take_future_course', 'eoc_how_did_you_hear',
            )
        }),
        ('Mid-Course Fields', {
            'fields': ('mid_keeping_up_with_material', 'mid_support_needed', 'mid_concerns')
        }),
        ('Written Feedback', {
            'fields': ('what_worked_well', 'what_could_be_improved', 'suggestions_for_future', 'additional_comments')
        }),
    )


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
