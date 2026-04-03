from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Announcement, PaymentHistory, PaymentRecord, Student


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


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display  = ['title', 'is_active', 'created_at', 'created_by']
    list_filter   = ['is_active']
    search_fields = ['title', 'body']
