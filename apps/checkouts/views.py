from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Avg, Q
from django.http import HttpResponse
from datetime import datetime
from orders.models import Order
from decimal import Decimal


class CheckoutOrderListView(LoginRequiredMixin, ListView):
    """
    View para listagem de comandas no sistema de checkout
    """
    model = Order
    template_name = 'checkout_orderlist.html'
    context_object_name = 'orders'
    paginate_by = 50
    
    def get_queryset(self):
        """
        Retorna apenas comandas abertas (não entregues e não canceladas)
        Ordena por status (pronta primeiro, depois preparando, depois aguardando)
        """
        queryset = Order.objects.filter(
            ~Q(status='entregue') & ~Q(status='cancelada')
        ).select_related().prefetch_related('items')
        
        # Ordenação personalizada: pronta > preparando > aguardando
        return queryset.extra(
            select={
                'status_priority': """
                    CASE status 
                        WHEN 'pronta' THEN 1 
                        WHEN 'preparando' THEN 2 
                        WHEN 'aguardando' THEN 3 
                        ELSE 4 
                    END
                """
            }
        ).order_by('status_priority', 'created_at')
    
    def get_context_data(self, **kwargs):
        """
        Adiciona estatísticas e dados extras ao contexto
        """
        context = super().get_context_data(**kwargs)
        
        # Comandas abertas (não entregues e não canceladas)
        open_orders = Order.objects.filter(
            ~Q(status='entregue') & ~Q(status='cancelada')
        )
        
        # Estatísticas
        stats = open_orders.aggregate(
            total_orders=Count('id'),
            total_value=Sum('total_amount'),
            avg_ticket=Avg('total_amount')
        )
        
        # Adicionar total de itens para cada comanda
        orders = context['orders']
        for order in orders:
            order.total_items = order.items.aggregate(
                total=Sum('quantity')
            )['total'] or 0
        
        # Adicionar ao contexto
        context.update({
            'total_orders': stats['total_orders'] or 0,
            'total_value': stats['total_value'] or 0,
            'avg_ticket': stats['avg_ticket'] or 0,
            'page_title': 'Sistema de Checkout - Comandas Abertas'
        })
        
        return context


class CheckoutOrderPrintView(TemplateView):
    """
    View para impressão de comanda
    """
    template_name = 'checkout_printitens.html'
    
    def get(self, request, *args, **kwargs):
        code = self.kwargs.get('code')
        
        try:
            order = Order.objects.prefetch_related('items__product').get(code=code)
            
            # Calcular subtotal para cada item
            for item in order.items.all():
                item.subtotal = item.quantity * item.unit_price
            
            context = {
                'order': order,
                'print_time': datetime.now()
            }
            
            return render(request, self.template_name, context)
            
        except Order.DoesNotExist:
            return HttpResponse(f"<h1>Comanda #{code} não encontrada</h1><p>Verifique se o código está correto.</p>")
        except Exception as e:
            return HttpResponse(f"<h1>Erro ao carregar comanda</h1><p>Erro: {str(e)}</p>")