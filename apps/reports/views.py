from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q
from orders.models import Comanda, Pedido, PedidoItem
from products.models import Product


class BaseReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Base para todas as views de relatórios"""
    permission_required = 'orders.view_order'


class NFCeReportView(BaseReportView):
    """Relatório de NFCe emitidas (Cupons Fiscais)"""
    template_name = 'reports/nfce_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filtros de data
        data_inicio = self.request.GET.get('data_inicio')
        data_fim = self.request.GET.get('data_fim')
        numero_comanda = self.request.GET.get('numero_comanda', '').strip()
        
        # Se não informado, últimos 30 dias
        if not data_inicio:
            data_inicio = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not data_fim:
            data_fim = timezone.now().strftime('%Y-%m-%d')
        
        # Busca comandas com NFCe
        queryset = Comanda.objects.filter(
            status='entregue',
            nfce_numero__isnull=False,
            created_at__date__gte=data_inicio,
            created_at__date__lte=data_fim
        )
        
        # Filtro por número da comanda se informado
        if numero_comanda:
            queryset = queryset.filter(code__icontains=numero_comanda)
        
        queryset = queryset.order_by('-created_at')
        
        # Estatísticas
        total_cupons = queryset.count()
        total_valor = queryset.aggregate(total=Sum('total_amount'))['total'] or 0
        valor_medio = total_valor / total_cupons if total_cupons > 0 else 0
        
        # Cupons por dia no período
        cupons_periodo = queryset.extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            qtd_cupons=Count('id'),
            valor_dia=Sum('total_amount')
        ).order_by('-day')[:7]  # Últimos 7 dias com movimento
        
        context.update({
            'nfce_list': queryset,
            'total_cupons': total_cupons,
            'total_valor': total_valor,
            'valor_medio': valor_medio,
            'cupons_periodo': cupons_periodo,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'numero_comanda': numero_comanda,
        })
        
        return context


class SalesReportView(BaseReportView):
    """Relatório de Vendas"""
    template_name = 'reports/sales_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filtros de data
        data_inicio = self.request.GET.get('data_inicio')
        data_fim = self.request.GET.get('data_fim')
        
        # Se não informado, últimos 30 dias
        if not data_inicio:
            data_inicio = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not data_fim:
            data_fim = timezone.now().strftime('%Y-%m-%d')
        
        # Busca vendas
        vendas_queryset = Comanda.objects.filter(
            status='DELIVERED',
            created_at__date__gte=data_inicio,
            created_at__date__lte=data_fim
        ).order_by('-created_at')
        
        # Produtos mais vendidos
        produtos_vendidos = PedidoItem.objects.filter(
            order__in=vendas_queryset
        ).values(
            'product__name'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('quantity') * Sum('unit_price')
        ).order_by('-total_quantity')[:10]
        
        # Estatísticas
        total_vendas = vendas_queryset.count()
        total_faturamento = vendas_queryset.aggregate(total=Sum('total_amount'))['total'] or 0
        ticket_medio = total_faturamento / total_vendas if total_vendas > 0 else 0
        
        # Vendas por dia
        vendas_por_dia = vendas_queryset.extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            total_vendas=Count('id'),
            total_valor=Sum('total_amount')
        ).order_by('day')
        
        context.update({
            'vendas_list': vendas_queryset,
            'produtos_vendidos': produtos_vendidos,
            'vendas_por_dia': vendas_por_dia,
            'total_vendas': total_vendas,
            'total_faturamento': total_faturamento,
            'ticket_medio': ticket_medio,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        })
        
        return context