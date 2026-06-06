from django.contrib import admin
from .models import Comanda, Pedido, PedidoItem, ComandaPartialPayment


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
    readonly_fields = ('total_amount', 'campo_created_at', 'campo_updated_at')
    ordering = ('-created_at',)
    inlines = [PedidoInline]
    fieldsets = (
        ('Dados da Comanda', {
            'fields': ('numero', 'cliente_nome', 'status', 'total_amount', 'motivo_cancelamento')
        }),
        ('Datas (editáveis para ajuste de fluxo de caixa)', {
            'fields': ('campo_created_at', 'campo_updated_at'),
            'description': '⚠️ Altere apenas para corrigir o fluxo de caixa. "Fechamento" define o dia no relatório.',
        }),
    )

    def campo_created_at(self, obj):
        from django.utils import timezone as _tz
        from django.utils.html import format_html
        val = _tz.localtime(obj.created_at).strftime('%d/%m/%Y %H:%M') if obj and obj.pk else ''
        return format_html(
            '<input type="text" name="campo_created_at" value="{}" '
            'placeholder="DD/MM/AAAA HH:MM" '
            'style="width:200px;font-family:monospace;padding:4px 8px;border:1px solid #ccc;border-radius:4px;" />'
            '<span style="margin-left:8px;color:#666;font-size:11px;">Formato: DD/MM/AAAA HH:MM</span>',
            val
        )
    campo_created_at.short_description = 'Abertura'

    def campo_updated_at(self, obj):
        from django.utils import timezone as _tz
        from django.utils.html import format_html
        val = _tz.localtime(obj.updated_at).strftime('%d/%m/%Y %H:%M') if obj and obj.pk else ''
        return format_html(
            '<input type="text" name="campo_updated_at" value="{}" '
            'placeholder="DD/MM/AAAA HH:MM" '
            'style="width:200px;font-family:monospace;padding:4px 8px;border:1px solid #ccc;border-radius:4px;" />'
            '<span style="margin-left:8px;color:#666;font-size:11px;">Formato: DD/MM/AAAA HH:MM — define o dia no fluxo de caixa</span>',
            val
        )
    campo_updated_at.short_description = 'Fechamento'

    def save_model(self, request, obj, form, change):
        from datetime import datetime as _dt
        from django.utils import timezone as _tz

        # Bloqueia mudança de status que "reabre" comanda já finalizada
        IMUTAVEIS = ('fechada', 'cancelada', 'cortesia')
        if change and obj.pk:
            original = Comanda.objects.filter(pk=obj.pk).values('status').first()
            if original and original['status'] in IMUTAVEIS and obj.status != original['status']:
                from django.contrib import messages as _msgs
                _msgs.error(request, f'Comanda #{obj.numero} já finalizada — status não pode ser alterado via admin.')
                # Reverte para o status original sem salvar a mudança
                obj.status = original['status']

        super().save_model(request, obj, form, change)
        updates = {}
        field_map = {
            'campo_created_at': 'created_at',
            'campo_updated_at': 'updated_at',
        }
        for post_key, db_field in field_map.items():
            raw = request.POST.get(post_key, '').strip()
            if not raw:
                continue
            parsed = None
            for fmt in ('%d/%m/%Y %H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y', '%Y-%m-%d'):
                try:
                    parsed = _dt.strptime(raw, fmt)
                    break
                except ValueError:
                    continue
            if parsed:
                if _tz.is_naive(parsed):
                    parsed = _tz.make_aware(parsed)
                updates[db_field] = parsed
        if updates:
            type(obj).objects.filter(pk=obj.pk).update(**updates)


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


@admin.register(ComandaPartialPayment)
class ComandaPartialPaymentAdmin(admin.ModelAdmin):
    list_display = ('comanda', 'payment_method', 'amount', 'processed_by', 'created_at')
    list_filter = ('payment_method', 'created_at')
    search_fields = ('comanda__numero', 'processed_by__username')
    ordering = ('-created_at',)
