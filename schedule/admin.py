from django.contrib import admin

from .models import CalendarEvent


@admin.register(CalendarEvent)
class CalendarEventAdmin(admin.ModelAdmin):
    list_display  = ['course', 'event_type', 'title', 'date', 'all_day', 'created_by']
    list_filter   = ['event_type', 'course']
    search_fields = ['title', 'description']
    ordering      = ['date']
