from django.contrib import admin
from .models import Sangria


@admin.register(Sangria)
class SangriaAdmin(admin.ModelAdmin):
    list_display = ('valor_formatado', 'usuario', 'created_at', 'observacao_truncada')
    list_filter = ('created_at', 'usuario')
    search_fields = ('observacao', 'usuario__username', 'usuario__first_name', 'usuario__last_name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    def observacao_truncada(self, obj):
        if obj.observacao:
            return obj.observacao[:50] + ('...' if len(obj.observacao) > 50 else '')
        return '-'
    observacao_truncada.short_description = 'Observação'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('usuario')