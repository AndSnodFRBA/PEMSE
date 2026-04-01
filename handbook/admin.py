from django.contrib import admin
from .models import HandbookChapter, HandbookAcknowledgment


@admin.register(HandbookChapter)
class HandbookChapterAdmin(admin.ModelAdmin):
    list_display  = ['number', 'title', 'is_active', 'updated_at']
    list_editable = ['is_active']
    ordering      = ['number']


@admin.register(HandbookAcknowledgment)
class HandbookAcknowledgmentAdmin(admin.ModelAdmin):
    list_display  = ['student', 'sig_name', 'signed_at', 'ip_address']
    readonly_fields = ['student', 'sig_name', 'signed_at', 'ip_address']
    search_fields = ['student__email', 'sig_name']
