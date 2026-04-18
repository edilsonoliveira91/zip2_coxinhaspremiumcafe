from django.contrib import admin
from .models import Checkout


@admin.register(Checkout)
class CheckoutAdmin(admin.ModelAdmin):
    list_display = (
        'comanda',
        'get_payment_method',
        'total',
        'status',
        'processed_by',
        'processed_at',
        'created_at',
    )
    list_filter = ('payment_method', 'status', 'processed_at', 'created_at')
    search_fields = ('comanda__numero', 'processed_by__username', 'notes')
    readonly_fields = (
        'comanda', 'subtotal', 'desconto', 'taxa_servico', 'total',
        'payment_method', 'status', 'processed_by', 'processed_at',
        'created_by', 'created_at', 'updated_at', 'notes',
    )
    date_hierarchy = 'processed_at'
    ordering = ('-processed_at',)

    fieldsets = (
        ('Comanda', {
            'fields': ('comanda',)
        }),
        ('Pagamento', {
            'fields': ('payment_method', 'status', 'subtotal', 'desconto', 'taxa_servico', 'total')
        }),
        ('Auditoria', {
            'fields': ('processed_by', 'processed_at', 'created_by', 'created_at', 'updated_at')
        }),
        ('Observações', {
            'fields': ('notes',)
        }),
    )

    def get_payment_method(self, obj):
        return obj.get_payment_method_display()
    get_payment_method.short_description = 'Forma de Pagamento'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
