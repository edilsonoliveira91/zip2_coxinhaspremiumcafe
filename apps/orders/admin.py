from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    """
    Inline para editar itens da comanda junto com a comanda
    """
    model = OrderItem
    extra = 0
    readonly_fields = ('total_price',)
    fields = ('product', 'quantity', 'unit_price', 'observations', 'total_price')
    
    def total_price(self, obj):
        if obj.pk:
            return f"R$ {obj.total_price:.2f}"
        return "-"
    total_price.short_description = "Total do Item"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Admin para comandas
    """
    list_display = [
        'code', 'name', 'status', 'total_amount', 
        'created_at', 'preparation_time_display', 'created_by'
    ]
    list_filter = [
        'status', 'created_at', 'created_by'
    ]
    search_fields = ['code', 'name']
    readonly_fields = [
        'code', 'total_amount', 'preparation_time_display',
        'total_time_display', 'created_at', 'updated_at'
    ]
    
    fieldsets = [
        ('Informações da Comanda', {
            'fields': ('code', 'name', 'observations', 'status')
        }),
        ('Valores', {
            'fields': ('total_amount',)
        }),
        ('Controle de Tempo', {
            'fields': (
                'created_at', 'started_at', 'finished_at', 'delivered_at',
                'preparation_time_display', 'total_time_display'
            ),
            'classes': ('collapse',)
        }),
        ('Auditoria', {
            'fields': ('created_by', 'updated_by', 'updated_at'),
            'classes': ('collapse',)
        })
    ]
    
    inlines = [OrderItemInline]
    
    # Ordenação padrão
    ordering = ['-created_at']
    
    # Filtros laterais
    list_per_page = 25
    
    def preparation_time_display(self, obj):
        """Exibir tempo de preparo formatado"""
        if obj.preparation_time:
            return f"{obj.preparation_time:.1f} minutos"
        return "-"
    preparation_time_display.short_description = "Tempo de Preparo"
    
    def total_time_display(self, obj):
        """Exibir tempo total formatado"""
        if obj.total_time:
            return f"{obj.total_time:.1f} minutos"
        return "-"
    total_time_display.short_description = "Tempo Total"
    
    def save_model(self, request, obj, form, change):
        """Definir usuário criador/atualizador"""
        if not change:  # Novo objeto
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    def save_formset(self, request, form, formset, change):
        """Definir usuário nos itens da comanda"""
        instances = formset.save(commit=False)
        for instance in instances:
            if not instance.pk:  # Novo item
                instance.created_by = request.user
            instance.updated_by = request.user
            instance.save()
        formset.save_m2m()


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """
    Admin para itens da comanda (view separada se necessário)
    """
    list_display = [
        'order_code', 'product', 'quantity', 
        'unit_price', 'total_price', 'order_status'
    ]
    list_filter = [
        'product__category', 'order__status', 'created_at'
    ]
    search_fields = [
        'order__code', 'order__name', 'product__name'
    ]
    readonly_fields = ['total_price']
    
    def order_code(self, obj):
        return obj.order.code
    order_code.short_description = "Código da Comanda"
    order_code.admin_order_field = 'order__code'
    
    def order_status(self, obj):
        return obj.order.get_status_display()
    order_status.short_description = "Status da Comanda"
    order_status.admin_order_field = 'order__status'
    
    def total_price(self, obj):
        return f"R$ {obj.total_price:.2f}"
    total_price.short_description = "Total do Item"
    
    def save_model(self, request, obj, form, change):
        """Definir usuário criador/atualizador"""
        if not change:  # Novo objeto
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Configurações adicionais do admin
admin.site.site_header = "Cafeteria Premium - Comandas"
admin.site.site_title = "Comandas"
admin.site.index_title = "Gerenciamento de Comandas"