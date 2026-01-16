from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Sum, Avg, Q
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.utils import timezone
from django.db import transaction
from datetime import datetime
import json
from orders.models import Order
from decimal import Decimal

# Tente importar o modelo Checkout, se existir
try:
    from checkouts.models import Checkout
except ImportError:
    Checkout = None


class CheckoutOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    View para listagem de comandas no sistema de checkout
    """
    permission_required = 'checkouts.view_checkout'
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


class CheckoutOrderPrintView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    View para impressão de comanda
    """
    permission_required = 'checkouts.view_checkout'
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


class CheckoutFinalizeView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para finalizar comanda e processar pagamento
    """
    permission_required = 'checkouts.add_checkout'
    
    def post(self, request, code):
        try:
            # Buscar comanda
            order = get_object_or_404(Order, code=code)
            
            # Validar se comanda pode ser finalizada
            if order.status in ['entregue', 'cancelada']:
                return JsonResponse({
                    'success': False,
                    'message': f'Comanda já está {order.status}!'
                }, status=400)
            
            # Pegar dados do pagamento
            data = json.loads(request.body)
            payment_method = data.get('payment_method')
            received_amount = float(data.get('received_amount', 0))
            change_amount = float(data.get('change_amount', 0))
            
            # Validar método de pagamento
            if payment_method not in ['dinheiro', 'cartao_debito', 'cartao_credito', 'pix']:
                return JsonResponse({
                    'success': False,
                    'message': 'Método de pagamento inválido!'
                }, status=400)
            
            # Validar valores para dinheiro
            if payment_method == 'dinheiro':
                if received_amount < float(order.total_amount):
                    return JsonResponse({
                        'success': False,
                        'message': 'Valor recebido é insuficiente!'
                    }, status=400)
            
            # Processar finalização em transação
            with transaction.atomic():
                # Atualizar status da comanda
                order.status = 'entregue'
                order.delivered_at = timezone.now()
                order.updated_by = request.user
                order.save()
                
                # Criar registro de checkout (se o modelo existir)
                if Checkout:
                    try:
                        checkout = Checkout.objects.create(
                            order=order,
                            subtotal=order.total_amount,
                            desconto=Decimal('0.00'),
                            taxa_servico=Decimal('0.00'),
                            total=order.total_amount,
                            payment_method=payment_method,
                            status='aprovado',
                            processed_by=request.user,
                            processed_at=timezone.now(),
                            notes=f'Pagamento em {payment_method}' + (
                                f' - Recebido: R$ {received_amount:.2f} - Troco: R$ {change_amount:.2f}' 
                                if payment_method == 'dinheiro' else ''
                            )
                        )
                    except Exception as e:
                        print(f"Erro ao criar registro de checkout: {e}")
                
                return JsonResponse({
                    'success': True,
                    'message': f'Comanda #{code} finalizada com sucesso!',
                    'order_code': code,
                    'payment_method': payment_method,
                    'total': float(order.total_amount),
                    'received_amount': received_amount if payment_method == 'dinheiro' else float(order.total_amount),
                    'change_amount': change_amount if payment_method == 'dinheiro' else 0
                })
                
        except Order.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': f'Comanda #{code} não encontrada!'
            }, status=404)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Dados inválidos!'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro interno: {str(e)}'
            }, status=500)