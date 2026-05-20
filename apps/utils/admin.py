from django.contrib import admin
from .models import SyncLog


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = (
        'started_at',
        'direction',
        'status_colored',
        'triggered_by',
        'duration_seconds',
        'records_downloaded',
        'records_created',
        'records_updated',
        'records_deleted',
        'images_downloaded',
        'local_server_ip',
    )
    list_filter = ('status', 'direction', 'triggered_by', 'started_at')
    search_fields = ('error_message', 'local_server_ip', 'tables_synced')
    readonly_fields = (
        'started_at', 'finished_at', 'duration_seconds', 'direction',
        'status', 'error_message', 'records_downloaded', 'records_uploaded',
        'records_created', 'records_updated', 'records_deleted',
        'images_downloaded', 'tables_synced', 'sync_from_datetime',
        'triggered_by', 'local_server_ip',
    )
    ordering = ('-started_at',)
    date_hierarchy = 'started_at'

    def status_colored(self, obj):
        from django.utils.html import format_html
        colors = {
            'success': '#22c55e',
            'error':   '#ef4444',
            'partial': '#f59e0b',
            'running': '#3b82f6',
        }
        icons = {
            'success': '✅',
            'error':   '❌',
            'partial': '⚠️',
            'running': '🔄',
        }
        color = colors.get(obj.status, '#6b7280')
        icon  = icons.get(obj.status, '')
        label = obj.get_status_display()
        return format_html(
            '<span style="color: {}; font-weight: 600;">{} {}</span>',
            color, icon, label
        )
    status_colored.short_description = 'Status'
    status_colored.admin_order_field = 'status'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_module_perms(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
