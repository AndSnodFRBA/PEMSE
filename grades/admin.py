from django.contrib import admin
from .models import GradeBook, QuizGrade, SectionExamGrade, WorksheetGrade, SkillsGrade, ParticipationDeduction


class QuizGradeInline(admin.TabularInline):
    model = QuizGrade
    extra = 0


class SectionExamGradeInline(admin.TabularInline):
    model = SectionExamGrade
    extra = 0


class WorksheetGradeInline(admin.TabularInline):
    model = WorksheetGrade
    extra = 0


class SkillsGradeInline(admin.TabularInline):
    model = SkillsGrade
    extra = 0


class ParticipationDeductionInline(admin.TabularInline):
    model = ParticipationDeduction
    extra = 0


@admin.register(GradeBook)
class GradeBookAdmin(admin.ModelAdmin):
    list_display = ['student', 'course', 'overall_grade', 'letter_grade', 'is_passing', 'participation_score']
    list_filter = ['course']
    search_fields = ['student__first_name', 'student__last_name', 'student__email']
    inlines = [QuizGradeInline, SectionExamGradeInline, WorksheetGradeInline, SkillsGradeInline, ParticipationDeductionInline]


@admin.register(ParticipationDeduction)
class ParticipationDeductionAdmin(admin.ModelAdmin):
    list_display = ['gradebook', 'reason', 'points', 'date', 'recorded_by']
    list_filter = ['reason']
