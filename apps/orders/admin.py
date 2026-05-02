from django.contrib import admin
from .models import Comanda, Pedido, PedidoItem


class StatusComandaFilter(admin.SimpleListFilter):
    title = 'Status'
    parameter_name = 'status_filtro'

    def lookups(self, request, model_admin):
        return [
            ('abertas', 'Abertas (em uso)'),
            ('livre', 'Livres'),
            ('fechada', 'Finalizadas'),
            ('todas', 'Todas'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'abertas' or self.value() is None:
            return queryset.filter(status='em_uso')
        if self.value() == 'livre':
            return queryset.filter(status='livre')
        if self.value() == 'fechada':
            return queryset.filter(status='fechada')
        return queryset  # 'todas'

    def choices(self, changelist):
        # Marca "Abertas" como selecionado por padrão
        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.value() == lookup or (self.value() is None and lookup == 'abertas'),
                'query_string': changelist.get_query_string({self.parameter_name: lookup}),
                'display': title,
            }


class PedidoItemInline(admin.TabularInline):
    model = PedidoItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'unit_price', 'observations')
    can_delete = False


class PedidoInline(admin.TabularInline):
    model = Pedido
    extra = 0
    readonly_fields = ('pedido_seq', 'status', 'total_amount', 'created_at')
    fields = ('pedido_seq', 'status', 'total_amount', 'created_at')
    can_delete = False
    show_change_link = True


@admin.register(Comanda)
class ComandaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'cliente_nome', 'status', 'total_amount', 'created_at')
    list_filter = (StatusComandaFilter,)
    search_fields = ('numero', 'cliente_nome')
    readonly_fields = ('total_amount', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    inlines = [PedidoInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Se não há filtro aplicado, mostra só as abertas
        if not request.GET.get('status_filtro'):
            return qs.filter(status='em_uso')
        return qs


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('pedido_seq', 'comanda', 'status', 'total_amount', 'created_at')
    list_filter = ('status',)
    search_fields = ('comanda__numero', 'comanda__cliente_nome')
    readonly_fields = ('pedido_seq', 'total_amount', 'created_at', 'updated_at', 'delivered_at')
    ordering = ('-created_at',)
    inlines = [PedidoItemInline]


@admin.register(PedidoItem)
class PedidoItemAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'unit_price', 'pedido')
    search_fields = ('product__name', 'pedido__comanda__numero')
    readonly_fields = ('unit_price',)
