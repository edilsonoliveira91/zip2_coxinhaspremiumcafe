from datetime import datetime
from django.shortcuts import redirect
from django.views.generic import DetailView
from products.models import Product
from django.http import JsonResponse, Http404
import json
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum, Case, When, IntegerField
from django.db import transaction
import json
from .models import Comanda, Pedido, PedidoItem
from .forms import PedidoForm, PedidoItemFormSet, ScannerForm, OrderStatusForm
from products.models import Product, Adicional, OpcionalObrigatorio


def _get_saldo_estoque(product_id, exclude_pedido_id=None):
    """
    Retorna o saldo atual em estoque do produto.
    saldo = entradas - saidas_permanentes - pedidos_em_andamento
    Retorna 0 se não houver entradas de estoque (produto bloqueado para venda).
    """
    from products.models import StockEntry, StockExit
    from django.db.models import Sum as _Sum
    entradas = StockEntry.objects.filter(product_id=product_id).aggregate(t=_Sum('quantity'))['t'] or 0
    # Saídas permanentes: pedidos já entregues (registrados via signal)
    saidas_permanentes = StockExit.objects.filter(product_id=product_id).aggregate(t=_Sum('quantity'))['t'] or 0
    # Saídas temporárias: pedidos em andamento (ainda não entregues)
    qs = PedidoItem.objects.filter(
        product_id=product_id,
        pedido__status__in=['aguardando', 'preparando', 'pronta']
    )
    if exclude_pedido_id:
        qs = qs.exclude(pedido_id=exclude_pedido_id)
    saidas_em_andamento = qs.aggregate(t=_Sum('quantity'))['t'] or 0
    return entradas - saidas_permanentes - saidas_em_andamento
import base64
from decimal import Decimal

import urllib.parse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect


class OrderDashboardView(LoginRequiredMixin, View):
    """
    Redireciona para o dashboard principal de accounts.
    """
    login_url = reverse_lazy('accounts:login')

    def get(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        return redirect('accounts:dashboard')


class OrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Lista todas as comandas
    """
    permission_required = 'orders.view_order'
    model = Comanda
    template_name = 'orders/list.html'
    context_object_name = 'orders'
    paginate_by = 20
    login_url = reverse_lazy('accounts:login')
    
    def get_queryset(self):
        queryset = Comanda.objects.all().order_by('-created_at')
        
        # Filtros opcionais
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) |
                Q(name__icontains=search)
            )
        
        return queryset


class OrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detalhes de uma comanda específica
    """
    permission_required = 'orders.view_order'
    model = Comanda
    template_name = 'orders/detail.html'
    context_object_name = 'order'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    login_url = reverse_lazy('accounts:login')


class OrderCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Criar nova comanda (página completa)
    """
    permission_required = 'orders.add_order'
    model = Comanda
    form_class = PedidoForm
    template_name = 'orders/create.html'
    login_url = reverse_lazy('accounts:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['formset'] = PedidoItemFormSet(self.request.POST)
        else:
            context['formset'] = PedidoItemFormSet()
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        
        # Definir usuário que criou
        form.instance.created_by = self.request.user
        
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            
            messages.success(
                self.request,
                f'Comanda #{self.object.code} criada com sucesso!'
            )
            
            return redirect('orders:detail', code=self.object.code)
        else:
            return self.form_invalid(form)


class OrderCreateAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para criar comanda via AJAX (do modal)
    """
    permission_required = 'orders.add_order'
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Validar se há itens
            items = data.get('items', [])
            if not items:
                return JsonResponse({
                    'success': False,
                    'message': 'É necessário adicionar pelo menos um item à comanda!'
                }, status=400)
            
            # Validar se há nome
            name = data.get('name', '').strip()
            if not name:
                return JsonResponse({
                    'success': False,
                    'message': 'Número da comanda é obrigatório!'
                }, status=400)

            # Validar se é apenas números
            if not name.isdigit():
                return JsonResponse({
                    'success': False,
                    'message': 'Número da comanda deve conter apenas dígitos!'
                }, status=400)

            # Verificar se já existe comanda ABERTA com esse número
            comandas_abertas = Comanda.objects.filter(
                name=name,
                status__in=['aguardando', 'preparando', 'pronta']
            )
            if comandas_abertas.exists():
                return JsonResponse({
                    'success': False,
                    'message': f'Já existe uma comanda aberta com o número {name}!'
                }, status=400)
            
            # Criar comanda
            comanda = Comanda.objects.create(
                name=name,
                observations=data.get('observations', ''),
                created_by=request.user
            )
            
            # Adicionar itens
            for item_data in items:
                try:
                    product = Product.objects.get(id=item_data['id'])
                    PedidoItem.objects.create(
                        order=order,
                        product=product,
                        quantity=item_data['quantity'],
                        unit_price=product.price,
                        created_by=request.user
                    )
                except Product.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'message': f'Produto com ID {item_data["id"]} não encontrado!'
                    }, status=400)
            
            return JsonResponse({
                'success': True,
                'message': f'Comanda #{order.code} criada com sucesso!',
                'order_code': order.code,
                'order_total': float(order.total_amount)
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Dados JSON inválidos!'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro interno: {str(e)}'
            }, status=500)


class OrderUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Editar comanda existente
    """
    permission_required = 'orders.change_order'
    model = Comanda
    form_class = PedidoForm
    template_name = 'orders/edit.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    login_url = reverse_lazy('accounts:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['formset'] = PedidoItemFormSet(
                self.request.POST,
                instance=self.object
            )
        else:
            context['formset'] = PedidoItemFormSet(instance=self.object)
        
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        formset = context['formset']
        
        # Definir usuário que atualizou
        form.instance.updated_by = self.request.user
        
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            
            messages.success(
                self.request,
                f'Comanda #{self.object.code} atualizada com sucesso!'
            )
            
            return redirect('orders:detail', code=self.object.code)
        else:
            return self.form_invalid(form)


class OrderDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Deletar comanda
    """
    permission_required = 'orders.delete_order'
    model = Comanda
    template_name = 'orders/delete.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    success_url = reverse_lazy('orders:list')
    login_url = reverse_lazy('accounts:login')
    
    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        messages.success(
            request,
            f'Comanda #{self.object.code} deletada com sucesso!'
        )
        return super().delete(request, *args, **kwargs)


class OrderStatusUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Atualizar apenas o status da comanda
    """
    permission_required = 'orders.change_order'
    model = Comanda
    form_class = OrderStatusForm
    template_name = 'orders/status_update.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    login_url = reverse_lazy('accounts:login')
    
    def form_valid(self, form):
        old_status = self.object.status
        new_status = form.cleaned_data['status']
        
        # Atualizar timestamps baseado no status
        if new_status == 'preparando' and old_status == 'aguardando':
            form.instance.started_at = timezone.now()
        elif new_status == 'pronta' and old_status == 'preparando':
            form.instance.finished_at = timezone.now()
        elif new_status == 'entregue':
            form.instance.delivered_at = timezone.now()
        
        form.instance.updated_by = self.request.user
        
        messages.success(
            self.request,
            f'Status da comanda #{self.object.code} alterado para {new_status}!'
        )
        
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('orders:detail', kwargs={'code': self.object.code})


class ScannerView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Tela do scanner de código de barras
    """
    permission_required = 'orders.view_order'
    template_name = 'orders/scanner.html'
    login_url = reverse_lazy('accounts:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ScannerForm()
        return context
    
    def post(self, request):
        form = ScannerForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['barcode']
            return redirect('orders:scan_result', code=code)
        
        return render(request, self.template_name, {'form': form})


class ScanResultView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Resultado do scan - mostra comanda e opções de ação
    """
    permission_required = 'orders.view_order'
    model = Comanda
    template_name = 'orders/scan_result.html'
    context_object_name = 'order'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    login_url = reverse_lazy('accounts:login')


# Views para ações rápidas de status
class OrderStartView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Marcar como Em Preparo"""
    permission_required = 'orders.change_order'

    def post(self, request, code):
        comanda = get_object_or_404(Comanda, code=code)
        order.status = 'preparando'
        order.started_at = timezone.now()
        order.updated_by = request.user
        order.save()
        
        messages.success(request, f'Comanda #{code} marcada como Em Preparo!')
        return redirect('orders:detail', code=code)


class OrderFinishView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Marcar como Pronta"""
    permission_required = 'orders.change_order'

    def post(self, request, code):
        comanda = get_object_or_404(Comanda, code=code)
        order.status = 'pronta'
        order.finished_at = timezone.now()
        order.updated_by = request.user
        order.save()
        
        messages.success(request, f'Comanda #{code} marcada como Pronta!')
        return redirect('orders:detail', code=code)


class OrderDeliverView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Marcar como Entregue"""
    
    def post(self, request, code):
        comanda = get_object_or_404(Comanda, code=code)
        order.status = 'entregue'
        order.delivered_at = timezone.now()
        order.updated_by = request.user
        order.save()
        
        messages.success(request, f'Comanda #{code} marcada como Entregue!')
        return redirect('orders:detail', code=code)


class OrderCancelView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Cancelar comanda"""
    
    def post(self, request, code):
        comanda = get_object_or_404(Comanda, code=code)
        order.status = 'cancelada'
        order.updated_by = request.user
        order.save()
        
        messages.warning(request, f'Comanda #{code} foi cancelada!')
        return redirect('orders:detail', code=code)


# Views de filtro
class OrdersByStatusView(OrderListView):
    """Comandas filtradas por status"""
    
    def get_queryset(self):
        status = self.kwargs['status']
        return Comanda.objects.filter(status=status).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_status'] = self.kwargs['status']
        return context


class TodayOrdersView(OrderListView):
    """Comandas de hoje"""
    
    def get_queryset(self):
        today = timezone.now().date()
        return Comanda.objects.filter(created_at__date=today).order_by('-created_at')


class ActiveOrdersView(OrderListView):
    """Comandas ativas (não entregues nem canceladas)"""
    
    def get_queryset(self):
        return Comanda.objects.exclude(
            status__in=['entregue', 'cancelada']
        ).order_by('-created_at')


# API Views
class OrderStatusAPIView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """API para atualizar status via AJAX"""

    permission_required = 'orders.change_order'

    def post(self, request, code):
        try:
            comanda = get_object_or_404(Comanda, code=code)
            data = json.loads(request.body)
            new_status = data.get('status')
            
            old_status = order.status
            order.status = new_status
            
            # Atualizar timestamps
            if new_status == 'preparando' and old_status == 'aguardando':
                order.started_at = timezone.now()
            elif new_status == 'pronta' and old_status == 'preparando':
                order.finished_at = timezone.now()
            elif new_status == 'entregue':
                order.delivered_at = timezone.now()
            
            order.updated_by = request.user
            order.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Status atualizado para {new_status}!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)


# Views de relatório (básicas)
class OrderReportsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Dashboard de relatórios"""
    permission_required = 'orders.view_order'
    template_name = 'orders/reports.html'
    login_url = reverse_lazy('accounts:login')


class DailyReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Relatório diário"""
    permission_required = 'orders.view_order'
    template_name = 'orders/daily_report.html'
    login_url = reverse_lazy('accounts:login')


# Views de impressão (básicas)
class OrderPrintView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Versão para impressão da comanda"""
    permission_required = 'orders.view_order'
    model = Comanda
    template_name = 'orders/print.html'
    context_object_name = 'order'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    login_url = reverse_lazy('accounts:login')
    
    def get_context_data(self, **kwargs):
        from django.utils import timezone
        context = super().get_context_data(**kwargs)
        
        # Detectar se é impressão fiscal
        is_fiscal = self.request.GET.get('fiscal') == 'true'
        
        # Calcular subtotal para cada item
        comanda = context['order']
        for item in order.items.all():
            item.subtotal = item.quantity * item.unit_price
        
        context.update({
            'is_fiscal': is_fiscal,
            'tem_nfce': order.tem_nfce,
            'print_time': timezone.now()
        })
        
        return context

class OrderBarcodeView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Gerar código de barras para impressão"""
    permission_required = 'orders.view_order'
    model = Comanda
    template_name = 'orders/barcode.html'
    context_object_name = 'order'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    login_url = reverse_lazy('accounts:login')


class OrderDetailAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para buscar detalhes de uma comanda específica
    """
    permission_required = 'orders.view_order'

    def get(self, request, code):
        try:
            comanda = get_object_or_404(Comanda, code=code)
            
            # Serializar dados da comanda
            order_data = {
                'id': order.id,
                'code': order.code,
                'name': order.name,
                'status': order.status,
                'observations': order.observations or '',
                'total_amount': float(order.total_amount),
                'created_at': order.created_at.isoformat(),
                'items': []
            }
            
            # Adicionar itens da comanda
            for item in order.items.all():
                order_data['items'].append({
                    'id': item.id,
                    'product': {
                        'id': item.product.id,
                        'name': item.product.name,
                        'price': float(item.product.price)
                    },
                    'quantity': item.quantity,
                    'unit_price': float(item.unit_price),
                    'total_price': float(item.total_price)
                })
            
            return JsonResponse({
                'success': True,
                'order': order_data
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro ao buscar comanda: {str(e)}'
            }, status=500)


class OrderUpdateAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para atualizar itens de uma comanda
    """
    
    permission_required = 'orders.change_order'

    def put(self, request, code):
        try:
            comanda = get_object_or_404(Comanda, code=code)
            data = json.loads(request.body)
            
            # Limpar itens existentes
            order.items.all().delete()
            
            # Adicionar novos itens
            total_amount = 0
            for item_data in data.get('items', []):
                product = Product.objects.get(id=item_data['product_id'])
                
                PedidoItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price'],
                    created_by=request.user
                )
                
                total_amount += item_data['quantity'] * item_data['unit_price']
            
            # Atualizar total da comanda
            order.total_amount = total_amount
            order.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Comanda atualizada com sucesso!',
                'total_amount': float(total_amount)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro ao atualizar comanda: {str(e)}'
            }, status=500)


class OrderStatusUpdateAPIView(LoginRequiredMixin, View):
    """
    API para alterar status de uma comanda
    """
    
    def patch(self, request, code):
        try:
            comanda = get_object_or_404(Comanda, code=code)
            data = json.loads(request.body)
            
            new_status = data.get('status')
            if new_status not in dict(Comanda.STATUS_CHOICES):
                return JsonResponse({
                    'success': False,
                    'message': 'Status inválido!'
                }, status=400)
            
            order.status = new_status
            
            # Atualizar timestamps baseado no status
            now = timezone.now()
            if new_status == 'preparando' and not order.started_at:
                order.started_at = now
            elif new_status == 'pronta' and not order.finished_at:
                order.finished_at = now
            elif new_status == 'entregue' and not order.delivered_at:
                order.delivered_at = now
            
            order.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Status alterado para {new_status}!',
                'status': new_status
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro ao alterar status: {str(e)}'
            }, status=500)


class OrderFinalizeAPIView(LoginRequiredMixin, View):
    """
    API para finalizar uma comanda
    """
    
    def post(self, request, code):
        try:
            comanda = get_object_or_404(Comanda, code=code)
            
            # Finalizar comanda
            order.status = 'entregue'
            order.delivered_at = timezone.now()
            order.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Comanda #{code} finalizada com sucesso!',
                'status': 'entregue'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro ao finalizar comanda: {str(e)}'
            }, status=500)
        
# COMANDAS FINALIZADAS
class ClosedOrdersListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Lista de comandas finalizadas
    """
    permission_required = 'orders.view_order'
    model = Comanda
    template_name = 'orders/closed_orders_list.html'
    context_object_name = 'orders'
    def get_queryset(self):
        """Retorna comandas finalizadas e canceladas, filtradas por data (default hoje)"""
        today = timezone.localtime().date()
        raw_from = self.request.GET.get('date_from', '')
        raw_to   = self.request.GET.get('date_to', '')
        try:
            date_from = datetime.strptime(raw_from, '%Y-%m-%d').date() if raw_from else today
        except ValueError:
            date_from = today
        try:
            date_to = datetime.strptime(raw_to, '%Y-%m-%d').date() if raw_to else today
        except ValueError:
            date_to = today
        self._date_from = date_from
        self._date_to   = date_to
        self._metodo    = self.request.GET.get('metodo', '')

        VALID_METHODS = ['dinheiro', 'cartao_debito', 'cartao_credito', 'pix', 'parcial', 'cancelada', 'cortesia']
        metodo = self._metodo if self._metodo in VALID_METHODS else ''

        qs = Comanda.objects.filter(
            status__in=['fechada', 'cancelada', 'cortesia'],
            updated_at__date__gte=date_from,
            updated_at__date__lte=date_to,
        ).select_related('checkout', 'created_by').prefetch_related(
            'pedidos__items__product',
            'checkout__payments',
        ).order_by('-updated_at')

        if metodo == 'cancelada':
            qs = qs.filter(status='cancelada')
        elif metodo == 'cortesia':
            qs = qs.filter(status='cortesia')
        elif metodo in ['dinheiro', 'cartao_debito', 'cartao_credito', 'pix', 'parcial']:
            qs = qs.filter(checkout__payment_method=metodo, status='fechada')

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from django.db.models import Sum
        from checkouts.models import Checkout, CheckoutPayment
        from decimal import Decimal

        date_from = getattr(self, '_date_from', timezone.localtime().date())
        date_to   = getattr(self, '_date_to',   timezone.localtime().date())

        # Estatísticas filtradas pelo mesmo período
        total_finalizadas = Comanda.objects.filter(
            status__in=['fechada', 'cancelada', 'cortesia'],
            updated_at__date__gte=date_from,
            updated_at__date__lte=date_to,
        ).count()

        total_receita = (
            Checkout.objects.filter(
                comanda__status='fechada',
                comanda__updated_at__date__gte=date_from,
                comanda__updated_at__date__lte=date_to,
                status='aprovado',
            ).aggregate(total=Sum('total'))['total'] or 0
        )

        # Troco inicial (SystemConfig)
        from config.models import ConfigTrocoInicial
        troco_inicial = ConfigTrocoInicial.get_settings().troco_inicial

        # Totais por método de pagamento (para impressão do relatório)
        approved_qs = Checkout.objects.filter(
            comanda__status='fechada',
            comanda__updated_at__date__gte=date_from,
            comanda__updated_at__date__lte=date_to,
            status='aprovado',
        )
        parcial_qs = approved_qs.filter(payment_method='parcial')

        def _soma_metodo(method):
            simples  = (approved_qs.filter(payment_method=method)
                        .aggregate(t=Sum('total'))['t'] or Decimal('0'))
            parciais = (CheckoutPayment.objects.filter(
                            checkout__in=parcial_qs, payment_method=method)
                        .aggregate(t=Sum('amount'))['t'] or Decimal('0'))
            return simples + parciais

        total_dinheiro_print = _soma_metodo('dinheiro')
        total_debito_print   = _soma_metodo('cartao_debito')
        total_credito_print  = _soma_metodo('cartao_credito')
        total_pix_print      = _soma_metodo('pix')
        total_geral_print    = total_dinheiro_print + total_debito_print + total_credito_print + total_pix_print

        context.update({
            'total_finalizadas': total_finalizadas,
            'total_receita': total_receita,
            'date_from': date_from.strftime('%Y-%m-%d'),
            'date_to':   date_to.strftime('%Y-%m-%d'),
            'date_from_fmt': date_from.strftime('%d/%m/%Y'),
            'date_to_fmt':   date_to.strftime('%d/%m/%Y'),
            'metodo_filter': getattr(self, '_metodo', ''),
            # print totals
            'print_troco':    troco_inicial,
            'print_dinheiro': total_dinheiro_print,
            'print_debito':   total_debito_print,
            'print_credito':  total_credito_print,
            'print_pix':      total_pix_print,
            'print_total':    total_geral_print,
            'print_total_cmd': total_finalizadas,
        })

        return context


class ClosedOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detalhes de uma comanda finalizada específica (fechada, cancelada ou cortesia).
    Aceita tanto pk (inteiro) quanto numero (string) como lookup.
    """
    permission_required = 'orders.view_order'
    model = Comanda
    template_name = 'orders/closed_order_detail.html'
    context_object_name = 'order'
    login_url = reverse_lazy('accounts:login')

    def get_object(self, queryset=None):
        lookup = self.kwargs.get('lookup', '')
        qs = Comanda.objects.filter(
            status__in=['fechada', 'cancelada', 'cortesia']
        ).select_related('checkout', 'created_by').prefetch_related(
            'checkout__payments',
            'pedidos__items__product',
        )
        # Tenta por pk primeiro (somente se for inteiro puro sem zeros à esquerda)
        if lookup.isdigit() and not (len(lookup) > 1 and lookup[0] == '0'):
            try:
                return qs.get(pk=int(lookup))
            except Comanda.DoesNotExist:
                pass
        # Fallback: busca pelo numero (o mais recente)
        obj = qs.filter(numero=lookup).order_by('-created_at').first()
        if obj is None:
            raise Http404("Comanda não encontrada.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        comanda = self.object

        # Checkout e pagamentos
        checkout = getattr(comanda, 'checkout', None)
        payments = checkout.payments.all() if checkout else []

        # Pedidos agrupados (ativos + cancelados separados)
        pedidos_ativos = [p for p in comanda.pedidos.all() if p.status != 'cancelado']
        pedidos_cancelados = [p for p in comanda.pedidos.all() if p.status == 'cancelado']

        context.update({
            'checkout': checkout,
            'payments': payments,
            'pedidos_ativos': pedidos_ativos,
            'pedidos_cancelados': pedidos_cancelados,
        })
        return context


# Adicione estes imports no início do arquivo (se não existirem):
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.clickjacking import xframe_options_exempt
from django.conf import settings
import logging

class CancelarComandaFinalizadaView(LoginRequiredMixin, View):
    """
    Cancela uma comanda que já está finalizada (fechada/cortesia).
    Requer permissão 'orders.cancel_closed_comanda' ou superusuário.
    """
    def post(self, request, pk):
        if not (request.user.is_superuser or request.user.has_perm('orders.cancel_closed_comanda')):
            return JsonResponse({'success': False, 'error': 'Sem permissão para cancelar comanda finalizada.'}, status=403)

        try:
            comanda = Comanda.objects.get(pk=pk, status__in=['fechada', 'cortesia'])
        except Comanda.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Comanda não encontrada ou não está finalizada.'}, status=404)

        motivo = request.POST.get('motivo', '').strip()
        if not motivo:
            return JsonResponse({'success': False, 'error': 'Observação é obrigatória.'}, status=400)

        with transaction.atomic():
            comanda.status = 'cancelada'
            comanda.motivo_cancelamento = f'[CANCELAMENTO PÓS-FECHAMENTO] {motivo}'
            comanda.save(update_fields=['status', 'motivo_cancelamento'])

            # Cancela pedidos que ainda não foram cancelados
            comanda.pedidos.exclude(status='cancelado').update(
                status='cancelado',
                motivo_cancelamento=f'Comanda cancelada pós-fechamento. Motivo: {motivo}',
            )

        return JsonResponse({
            'success': True,
            'message': f'Comanda #{comanda.numero} cancelada com sucesso.',
            'comanda_id': comanda.pk,
        })


# Adicione no final do arquivo views.py:

class EmitirNFCeView(LoginRequiredMixin, View):
    """
    View para emissão de NFCe de uma comanda finalizada
    """
    
    def post(self, request, code=None, pk=None):
        """
        Processa a emissão de NFCe para uma comanda
        """
        try:
            # Quando chamado por pk (id único), usa id direto para evitar ambiguidade
            if pk:
                comanda = Comanda.objects.filter(
                    id=pk,
                    status__in=['fechada', 'cortesia']
                ).first()
            else:
                # Fallback pelo numero (não-único — mantido para compatibilidade)
                comanda = Comanda.objects.filter(
                    numero=code,
                    status__in=['fechada', 'cortesia']
                ).order_by('-created_at').first()
            if not comanda:
                # Debug: mostra o status real da comanda para diagnóstico
                todas = list(Comanda.objects.filter(numero=code).values('id', 'status', 'nfce_numero', 'created_at').order_by('-created_at')) if code else []
                detalhe = f'pk={pk} code={repr(code)} | comandas encontradas: {todas}'
                import logging
                logging.getLogger(__name__).error(f'[NFCE] Comanda não encontrada para emissão. {detalhe}')
                return JsonResponse({'success': False, 'message': 'Comanda não encontrada ou não está em status válido para emissão.', 'detalhe': detalhe})
            
            # Verifica se já foi emitida NFCe
            if comanda.tem_nfce:
                return JsonResponse({
                    'success': False,
                    'message': f'NFCe já foi emitida para esta comanda. Número: {comanda.nfce_numero}'
                })
            
            # Busca empresa ativa para emissão
            from companys.models import Company
            try:
                empresa = Company.objects.filter(ativa=True).first()
                if not empresa:
                    return JsonResponse({
                        'success': False,
                        'message': 'Nenhuma empresa ativa encontrada para emissão de NFCe'
                    })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': 'Erro ao buscar configuração da empresa'
                })
            
            # Valida se empresa tem configurações necessárias
            validacao_result = self._validar_configuracao_empresa_detalhada(empresa)
            if not validacao_result['valida']:
                return JsonResponse({
                    'success': False,
                    'message': f'Empresa incompleta. Campos obrigatórios faltando: {", ".join(validacao_result["campos_faltando"])}'
                })
            
            # Emite a NFCe
            resultado = self._processar_emissao_nfce(comanda, empresa)
            
            if resultado['sucesso']:
                # Salva dados da NFCe na comanda
                self._salvar_nfce_na_comanda(comanda, resultado)
                
                from django.urls import reverse
                cupom_url = reverse('orders:cupom_nfce_id', kwargs={'pk': comanda.id})
                return JsonResponse({
                    'success': True,
                    'message': 'NFCe emitida com sucesso!',
                    'numero_nfce': resultado['numero_nfce'],
                    'chave_acesso': resultado['chave_acesso'],
                    'cupom_url': cupom_url,
                    'comanda_numero': comanda.numero,
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f"Erro na emissão: {resultado.get('erro', 'Erro desconhecido')}",
                    'detalhe': resultado.get('detalhe', ''),
                })
                
        except Comanda.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Comanda não encontrada ou não está finalizada'
            })
        except Exception as e:
            # Log do erro para debugging
            logging.error(f"Erro ao emitir NFCe para comanda {code}: {str(e)}")
            
            return JsonResponse({
                'success': False,
                'message': f'Erro interno do servidor: {str(e)}'
            })
    
    def _validar_configuracao_empresa(self, empresa):
        """
        Valida se a empresa tem todas as configurações necessárias
        """
        campos_obrigatorios = [
            'cnpj', 'razao_social', 'logradouro', 'numero',
            'bairro', 'cidade', 'uf', 'cep', 'csc_id', 'csc_codigo'
        ]
        
        campos_faltando = []
        
        for campo in campos_obrigatorios:
            valor = getattr(empresa, campo, None)
            if not valor:
                campos_faltando.append(campo)
        
        if campos_faltando:
            print(f"DEBUG: Campos faltando na empresa: {campos_faltando}")
            return False
        
        return True

    def _validar_configuracao_empresa_detalhada(self, empresa):
        """
        Valida empresa e retorna detalhes dos campos faltando
        """
        campos_obrigatorios = {
            'cnpj': 'CNPJ',
            'razao_social': 'Razão Social', 
            'logradouro': 'Logradouro',
            'numero': 'Número',
            'bairro': 'Bairro',
            'cidade': 'Cidade',
            'uf': 'UF',
            'cep': 'CEP',
            'csc_id': 'CSC ID',
            'csc_codigo': 'CSC Código'
        }
        
        campos_faltando = []
        
        for campo, nome_amigavel in campos_obrigatorios.items():
            valor = getattr(empresa, campo, None)
            if not valor:
                campos_faltando.append(nome_amigavel)
        
        return {
            'valida': len(campos_faltando) == 0,
            'campos_faltando': campos_faltando
        }
    
    def _processar_emissao_nfce(self, order, empresa):
        """
        Processa a emissão da NFCe usando o NFCeService
        """
        try:
            from apps.utils.nfce_service import NFCeService
            
            # Pega CPF do cliente se foi fornecido (enviado como JSON)
            try:
                import json as _json
                body = _json.loads(self.request.body)
                cpf_cliente = body.get('cpf_cliente', '').strip() or None
            except Exception:
                cpf_cliente = None
            
            # Cria serviço de NFCe
            nfce_service = NFCeService(empresa)
            
            # Emite NFCe
            resultado = nfce_service.emitir_nfce(order, cpf_cliente)
            # Injeta cpf_cliente no resultado para ser salvo na comanda
            if isinstance(resultado, dict):
                resultado['cpf_cliente'] = cpf_cliente or ''
            
            return resultado
                    
        except Exception as e:
            return {
                'sucesso': False,  # CORRIGIDO: 'sucesso' em vez de 'success'
                'erro': str(e)
            }
    
    def _montar_dados_nfce(self, order, empresa, numero):
        """
        Monta estrutura de dados da NFCe
        """
        return {
            'empresa': {
                'cnpj': empresa.cnpj,
                'razao_social': empresa.razao_social,
                'nome_fantasia': empresa.nome_fantasia,
                'endereco': {
                    'logradouro': empresa.logradouro,
                    'numero': empresa.numero,
                    'complemento': empresa.complemento,
                    'bairro': empresa.bairro,
                    'cidade': empresa.cidade,
                    'uf': empresa.uf,
                    'cep': empresa.cep,
                }
            },
            'nfce': {
                'numero': numero,
                'serie': empresa.serie_nfce,
                'data_emissao': timezone.now(),
                'ambiente': empresa.ambiente_nfce,
            },
            'cliente': {
                'nome': order.name,  # Campo correto é 'name'
                'cpf': '',  # Por enquanto vazio, implementar depois se necessário
            },
            'itens': [
                {
                    'codigo': getattr(item.product, 'code', str(item.product.id)),
                    'descricao': item.product.name,
                    'quantidade': item.quantity,
                    'valor_unitario': item.unit_price,
                    'valor_total': item.total_price,
                    'cfop': '5102',  # CFOP padrão para venda
                    'ncm': getattr(item.product, 'ncm', ''),
                }
                for item in order.items.all()
            ],
            'totais': {
                'valor_produtos': order.total_amount,
                'valor_total': order.total_amount,
            }
        }
    
    def _simular_emissao_nfce(self, dados_nfce):
        """
        Simula a emissão da NFCe
        TODO: Substituir pela integração real com PyNFe
        """
        # Por enquanto sempre retorna sucesso para testar
        # Aqui será implementada a integração com PyNFe
        import time
        time.sleep(1)  # Simula tempo de processamento
        return True
    
    def _salvar_nfce_na_comanda(self, comanda, dados_nfce):
        """
        Salva os dados da NFCe na comanda
        TODO: Criar modelo NFCe relacionado com Comanda
        """
        # Por enquanto salva em campos simples na Comanda
        # Depois criar um modelo NFCe separado
        comanda.nfce_numero = dados_nfce['numero_nfce']
        comanda.nfce_chave = dados_nfce['chave_acesso']
        comanda.nfce_protocolo = dados_nfce['protocolo']
        comanda.nfce_emitida_em = timezone.now()
        comanda.nfce_xml_path = dados_nfce.get('xml_path')
        comanda.nfce_cpf_cliente = dados_nfce.get('cpf_cliente') or ''
        comanda.save(update_fields=['nfce_numero', 'nfce_chave', 'nfce_protocolo', 'nfce_emitida_em', 'nfce_xml_path', 'nfce_cpf_cliente'])


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

def gerar_cupom_texto(order, is_fiscal):
    """Gera o conteúdo do cupom normal com layout compacto (igual ao fiscal)"""
    width = 48

    def line(ch="-"):
        return ch * width

    def center(text):
        text = text[:width]
        return text.center(width)

    def cut(text):
        return text[:width]

    lines = []
    lines.append(line("="))
    lines.append(center("COXINHAS PREMIUM LTDA"))
    lines.append(center("R.Cel.F.Prestes,898-Centro"))
    lines.append(center("Itapetininga/SP CEP:18200-230"))
    lines.append(center("CNPJ:10.361.831/0001-23"))
    lines.append(center("IE:371.468.833.110"))
    lines.append(line("="))

    lines.append(center("CUPOM NAO FISCAL"))
    lines.append(f"COMANDA {order.code}  {order.created_at.strftime('%d/%m/%y %H:%M')}")
    lines.append("CONSUMIDOR NAO IDENTIFICADO")
    lines.append(line("-"))

    total_geral = 0
    for i, item in enumerate(order.items.all(), 1):
        subtotal = float(item.quantity) * float(item.unit_price)
        total_geral += subtotal

        import re as _re_obs
        nome = item.product.name[:25]
        lines.append(f"{i:03d} {nome}")
        _adics = _re_obs.findall(r'\+([^(]+)\(R\$([\d.]+)\)', item.observations or '')
        _extra = sum(float(p) for _, p in _adics)
        _base = float(item.unit_price) - _extra
        lines.append(f"{item.quantity:.0f}x{_base:.2f}     {_base * float(item.quantity):>8.2f}")
        for _aname, _aprice in _adics:
            lines.append(f"  {int(item.quantity)}x +{_aname.strip()[:22]}  {float(_aprice) * float(item.quantity):>8.2f}")
        _obs_clean = _re_obs.sub(r'\+[^(]+\(R\$[\d.]+\),?\s*', '', item.observations or '').strip(' |,').strip()
        if _obs_clean:
            lines.append(f"   Obs: {_obs_clean[:40]}")

    lines.append(line("-"))
    lines.append(f"TOTAL          R$ {total_geral:>10.2f}")
    lines.append(f"Dinheiro       R$ {total_geral:>10.2f}")
    lines.append(f"Troco          R$ {'0.00':>10}")
    lines.append(line("-"))

    lines.append(center("*** OBRIGADO! ***"))
    lines.append(center("Volte sempre!"))
    lines.append("")
    return "\n".join(lines)

# Substituir a CheckoutDirectPrintView completa (linha ~1035-1135)
@method_decorator(csrf_exempt, name='dispatch')
class CheckoutDirectPrintView(LoginRequiredMixin, View):
    """
    View para impressão direta automática na Epson TM-T20X II
    """
    
    def post(self, request, *args, **kwargs):
        code = self.kwargs.get('code')
        
        try:
            # Buscar a comanda
            comanda = get_object_or_404(
                Comanda.objects.prefetch_related('pedidos__items__product'),
                code=code
            )
            
            # Usar serviço Epson para impressão direta
            from apps.utils.epson_service import EpsonTMT20XService
            
            epson = EpsonTMT20XService(
                printer_name="EPSON_TM_T20X_II",
                connection_type="usb"
            )
            
            # Imprimir cupom normal diretamente
            resultado = epson.imprimir_cupom_normal_direto(order)
            
            if resultado['sucesso']:
                return JsonResponse({
                    'success': True,
                    'message': f'✅ Cupom impresso na {resultado["impressora"]}!',
                    'tipo': resultado['tipo']
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'❌ Erro: {resultado["erro"]}'
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'❌ Erro interno: {str(e)}'
            })

    
    def _enviar_para_impressora(self, content):
        """
        Enviar conteúdo para impressora Epson TM-T20X II
        """
        try:
            from apps.utils.epson_service import EpsonTMT20XService
            
            # Configurar impressora  
            epson = EpsonTMT20XService(
                printer_name="TM-T20X",  # Ajuste conforme sua instalação
                connection_type="usb"    # ou "network"
            )
            
            # Testar conexão
            if not epson.testar_conexao():
                print("[EPSON] Impressora não encontrada")
                return False
            
            # Enviar conteúdo direto (adaptar para cupom normal)
            return epson._enviar_para_epson(content)
            
        except Exception as e:
            print(f"[EPSON] Erro: {e}")
            return False


class OrderCupomContentView(LoginRequiredMixin, View):
    def get(self, request, code):
        comanda = get_object_or_404(
            Comanda.objects.prefetch_related('pedidos__items__product'),
            code=code
        )

        is_fiscal = request.GET.get('fiscal') in ['1', 'true', 'True']
        if is_fiscal and not order.tem_nfce:
            return JsonResponse({
                'success': False,
                'message': 'Esta comanda não possui NFCe emitida'
            })

        if is_fiscal:
            from apps.utils.epson_service import EpsonTMT20XService

            dados_nfce = {
                'numero': order.nfce_numero,
                'chave_acesso': order.nfce_chave,
                'order': order,
                'qr_code': f"{order.nfce_chave}|2|2|1|HASH_AQUI"
            }
            resultado_emissao = {
                'sucesso': True,
                'protocolo': order.nfce_protocolo,
                'modo': 'autorizada'
            }

            epson = EpsonTMT20XService(printer_name="EPSON_TM_T20X_II")
            escpos_text = epson._gerar_escpos_cupom_fiscal(dados_nfce, resultado_emissao)

            raw_bytes = escpos_text.encode('latin-1', errors='replace')
            raw_base64 = base64.b64encode(raw_bytes).decode('ascii')

            return JsonResponse({
                'success': True,
                'raw_base64': raw_base64,
                'is_raw': True,
                'tipo': 'cupom_fiscal'
            })

        content = gerar_cupom_texto(order, is_fiscal)
        return JsonResponse({
            'success': True,
            'content': content,
            'tipo': 'cupom_normal'
        })

@method_decorator(xframe_options_exempt, name='dispatch')
class CupomFiscalPrintView(LoginRequiredMixin, View):
    """
    View para impressão do cupom fiscal NFCe
    """
    
    def get(self, request, code=None, pk=None):
        """
        Gera e exibe o cupom fiscal para impressão
        """
        try:
            from companys.models import Company

            # Quando chamado por pk (id único), usa id direto para garantir comanda correta
            if pk:
                comanda = Comanda.objects.select_related().prefetch_related(
                    'pedidos__items__product'
                ).filter(
                    id=pk,
                    status__in=['fechada', 'cortesia'],
                    nfce_numero__isnull=False,
                ).first()
            else:
                # Fallback pelo numero (não-único — mantido para compatibilidade)
                comanda = Comanda.objects.select_related().prefetch_related(
                    'pedidos__items__product'
                ).filter(
                    numero=code,
                    status__in=['fechada', 'cortesia'],
                    nfce_numero__isnull=False,
                ).order_by('-nfce_emitida_em').first()
            if not comanda:
                return HttpResponse("Comanda não encontrada ou NFCe não emitida.", status=404)

            # Verifica se tem NFCe emitida (segurança extra)
            if not comanda.tem_nfce:
                return HttpResponse("NFCe não emitida para esta comanda.", status=404)

            # Busca empresa ativa
            empresa = Company.objects.filter(ativa=True).first()
            if not empresa:
                return HttpResponse("Empresa não configurada.", status=404)

            # Criar dados para o cupom — QR code recalculado via serviço
            from apps.utils.nfce_service import NFCeService
            nfce_service = NFCeService(empresa)
            qr_code_url = nfce_service._gerar_qr_code(comanda.nfce_chave, comanda.total_amount)

            dados_nfce = {
                'numero': comanda.nfce_numero,
                'chave_acesso': comanda.nfce_chave,
                'order': comanda,
                'qr_code': qr_code_url,
                'cpf_cliente': comanda.nfce_cpf_cliente or '',
            }

            resultado_emissao = {
                'sucesso': True,
                'protocolo': comanda.nfce_protocolo,
                'modo': 'autorizada',
            }

            cupom_html = nfce_service.gerar_cupom_fiscal_html(dados_nfce, resultado_emissao)

            return HttpResponse(cupom_html, content_type='text/html')

        except Exception as e:
            return HttpResponse(f'Erro ao gerar cupom: {str(e)}', status=500)


class CancelarNFCeView(LoginRequiredMixin, View):
    """
    Cancela uma NFC-e já emitida enviando evento de cancelamento para a SEFAZ.
    Prazo: 30 minutos após autorização (NFC-e SP).
    """

    def post(self, request, code=None, pk=None):
        import json as _json
        try:
            body = _json.loads(request.body)
        except Exception:
            body = {}

        justificativa = (body.get('justificativa') or '').strip()
        if len(justificativa) < 15:
            return JsonResponse({'success': False, 'message': 'Justificativa deve ter no mínimo 15 caracteres.'})

        if pk:
            comanda = Comanda.objects.filter(
                id=pk,
                nfce_numero__isnull=False,
            ).first()
        else:
            comanda = Comanda.objects.filter(
                numero=code,
                nfce_numero__isnull=False,
            ).order_by('-nfce_emitida_em').first()

        if not comanda:
            return JsonResponse({'success': False, 'message': 'Comanda não encontrada ou NFC-e não emitida.'})

        if comanda.nfce_cancelada:
            return JsonResponse({'success': False, 'message': 'Esta NFC-e já foi cancelada.'})

        if not comanda.nfce_chave or not comanda.nfce_protocolo:
            return JsonResponse({'success': False, 'message': 'Chave de acesso ou protocolo de autorização não encontrados.'})

        try:
            from companys.models import Company
            empresa = Company.objects.filter(ativa=True).first()
            if not empresa:
                return JsonResponse({'success': False, 'message': 'Empresa não configurada.'})

            from apps.utils.nfce_service import NFCeService
            nfce_service = NFCeService(empresa)
            resultado = nfce_service.cancelar_nfce(
                chave_acesso=comanda.nfce_chave,
                protocolo=comanda.nfce_protocolo,
                justificativa=justificativa,
            )

            if resultado['sucesso']:
                comanda.nfce_cancelada = True
                comanda.nfce_cancelada_em = timezone.now()
                comanda.nfce_protocolo_cancelamento = resultado.get('protocolo_cancelamento', '')
                comanda.save(update_fields=['nfce_cancelada', 'nfce_cancelada_em', 'nfce_protocolo_cancelamento'])
                return JsonResponse({
                    'success': True,
                    'message': f'NFC-e cancelada com sucesso. {resultado.get("mensagem", "")}',
                    'protocolo_cancelamento': resultado.get('protocolo_cancelamento', ''),
                })
            else:
                return JsonResponse({'success': False, 'message': resultado.get('erro', 'Erro desconhecido')})

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Erro ao cancelar: {str(e)}'})


class CupomFiscalDirectPrintView(LoginRequiredMixin, View):
    """
    View para impressão DIRETA do cupom fiscal na Epson TM-T20X II
    """
    
    def post(self, request, code):
        """
        Imprime cupom fiscal direto na impressora
        """
        try:
            # Busca a comanda
            comanda = get_object_or_404(
                Comanda.objects.select_related().prefetch_related('pedidos__items__product'),
                code=code,
                status='entregue'
            )
            
            # Verifica se tem NFCe emitida
            if not comanda.tem_nfce:
                return JsonResponse({
                    'success': False,
                    'message': 'Esta comanda não possui NFCe emitida'
                })
            
            # Configurar impressora (IGUAL À QUE FUNCIONA)
            from apps.utils.epson_service import EpsonTMT20XService
            epson = EpsonTMT20XService(
                printer_name="EPSON_TM_T20X_II",  # NOME CORRETO
                connection_type="usb"
            )
            
            # Preparar dados NFCe
            dados_nfce = {
                'numero': order.nfce_numero,
                'chave_acesso': order.nfce_chave,
                'order': order,
                'qr_code': f"{order.nfce_chave}|2|2|1|HASH_AQUI"
            }
            
            resultado_emissao = {
                'sucesso': True,  
                'protocolo': order.nfce_protocolo,
                'modo': 'autorizada'
            }
            
            # IMPRIMIR DIRETO (SEM TESTE DE CONEXÃO)
            resultado_impressao = epson.imprimir_cupom_fiscal_direto(dados_nfce, resultado_emissao)
            
            if resultado_impressao['sucesso']:
                return JsonResponse({
                    'success': True,
                    'message': f'✅ Cupom fiscal impresso na {resultado_impressao["impressora"]}!',
                    'impressora': resultado_impressao['impressora']
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f'❌ Erro: {resultado_impressao["erro"]}'
                })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'❌ Erro interno: {str(e)}'
            })


class TesteImpressaoAutomaticaView(LoginRequiredMixin, View):
    """
    View de teste para impressão automática
    """
    
    def get(self, request):
        # Buscar uma comanda para teste
        try:
            # Comanda com NFCe
            comanda_fiscal = Comanda.objects.filter(
                status='entregue',
                nfce_numero__isnull=False
            ).first()
            
            # Comanda sem NFCe  
            comanda_normal = Comanda.objects.filter(
                status='entregue',
                nfce_numero__isnull=True
            ).first()
            
            # Botões condicionais
            btn_normal = ""
            btn_fiscal = ""
            
            if comanda_normal:
                btn_normal = f'<button onclick="testarNormal(\'{comanda_normal.code}\')" style="padding:10px; margin:10px; background:blue; color:white;">📄 Testar Cupom Normal - {comanda_normal.code}</button>'
            else:
                btn_normal = '<p>❌ Nenhuma comanda normal encontrada</p>'
                
            if comanda_fiscal:
                btn_fiscal = f'<button onclick="testarFiscal(\'{comanda_fiscal.code}\')" style="padding:10px; margin:10px; background:green; color:white;">🧾 Testar Cupom Fiscal - {comanda_fiscal.code}</button>'
            else:
                btn_fiscal = '<p>❌ Nenhuma comanda com NFCe encontrada</p>'
            
            html = f'''<!DOCTYPE html>
<html><head><title>Teste Impressão Automática</title></head><body>
<h1>🖨️ Teste Impressão Automática Epson</h1>

<div style="margin: 20px 0;">
    <h3>Comandas Disponíveis para Teste:</h3>
    
    {btn_normal}
    
    {btn_fiscal}
</div>

<div id="resultado" style="margin-top:20px; padding:10px; border:1px solid #ccc; background:#f9f9f9;"></div>

<script>
function testarNormal(code) {{
    mostrarResultado('⏳ Testando impressão normal...');
    
    fetch('/orders/' + code + '/print-direct/', {{
        method: 'POST',
        headers: {{
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }}
    }})
    .then(response => response.json())
    .then(data => {{
        mostrarResultado('📄 CUPOM NORMAL: ' + (data.success ? '✅' : '❌') + ' ' + data.message);
    }})
    .catch(error => {{
        mostrarResultado('❌ Erro: ' + error);
    }});
}}

function testarFiscal(code) {{
    mostrarResultado('⏳ Testando impressão fiscal...');
    
    fetch('/orders/' + code + '/cupom-fiscal-direto/', {{
        method: 'POST',
        headers: {{
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }}
    }})
    .then(response => response.json())
    .then(data => {{
        mostrarResultado('🧾 CUPOM FISCAL: ' + (data.success ? '✅' : '❌') + ' ' + data.message);
    }})
    .catch(error => {{
        mostrarResultado('❌ Erro: ' + error);
    }});
}}

function mostrarResultado(msg) {{
    document.getElementById('resultado').innerHTML = '<strong>' + new Date().toLocaleTimeString() + '</strong> - ' + msg;
}}

function getCookie(name) {{
    let v = null; 
    if (document.cookie !== '') {{
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {{
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {{
                v = decodeURIComponent(cookie.substring(name.length + 1)); 
                break;
            }}
        }} 
    }} 
    return v;
}}
</script>
</body></html>'''
            
            return HttpResponse(html)
            
        except Exception as e:
            return HttpResponse(f"<h1>Erro: {e}</h1>")
# =====================================================================
# NOVAS VIEWS PARA O FLUXO DE MÚLTIPLOS PEDIDOS POR COMANDA
# =====================================================================


from django.http import JsonResponse

class ApiCheckComandaView(View):
    def get(self, request, numero):
        # Retorna a comanda ativa (em_uso ou livre); ignora fechadas/canceladas
        comanda = Comanda.objects.filter(
            numero=numero, status__in=['em_uso', 'livre']
        ).order_by('-created_at').first()
        if comanda:
            return JsonResponse({'exists': True, 'status': comanda.status})
        return JsonResponse({'exists': False, 'status': None})

class NovaComandaView(LoginRequiredMixin, View):
    template_name = 'orders/nova_comanda.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        numero = request.POST.get('numero')
        cliente_nome = request.POST.get('cliente_nome')

        if not numero or not str(numero).strip().isdigit():
            return render(request, self.template_name, {'error': 'O número da comanda é obrigatório e deve conter apenas dígitos.'})
        try:
            num_int = int(numero.strip())
            if num_int < 0 or num_int > 999:
                return render(request, self.template_name, {'error': 'O número da comanda deve ser entre 000 e 999.'})
        except ValueError:
            return render(request, self.template_name, {'error': 'Número inválido.'})
        numero = str(num_int).zfill(3)

        # Busca comanda ativa (em_uso ou livre) com esse número
        comanda = Comanda.objects.filter(
            numero=numero, status__in=['em_uso', 'livre']
        ).order_by('-created_at').first()

        if comanda and comanda.status == 'livre':
            comanda.status = 'em_uso'
            comanda.cliente_nome = cliente_nome
            comanda.save()
        elif not comanda:
            # Não há comanda ativa com esse número — cria nova (histórico anterior preservado)
            comanda = Comanda.objects.create(
                numero=numero,
                cliente_nome=cliente_nome,
                status='em_uso',
            )

        # Redireciona para a página de detalhes da comanda
        auto_open = request.POST.get('auto_open_modal')
        from django.urls import reverse
        url = reverse('orders:comanda_detail', kwargs={'numero': comanda.numero})
        if auto_open == 'true':
            url += '?modal=open'
        return redirect(url)

class ComandaDetailView(LoginRequiredMixin, DetailView):
    model = Comanda
    template_name = 'orders/comanda_detail.html'
    context_object_name = 'comanda'

    def get_object(self):
        numero = self.kwargs.get('numero')
        # Pega a comanda ativa (em uso ou aguardando caixa) com esse número
        comanda = Comanda.objects.filter(
            numero=numero, status__in=['em_uso', 'aguardando_caixa']
        ).order_by('-created_at').first()
        if comanda is None:
            # Fallback: comanda mais recente com esse número
            comanda = Comanda.objects.filter(numero=numero).order_by('-created_at').first()
            if comanda is None:
                from django.http import Http404
                raise Http404("Comanda não encontrada")
        return comanda

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Buscar Categorias ativas a partir do CATEGORY_CHOICES
        categories = [{'id': k, 'name': v} for k, v in Product.CATEGORY_CHOICES]
        
        # Buscar Todos os Produtos ativos e visíveis no cardápio
        products = Product.objects.filter(is_active=True, show_in_menu=True)
        
        adicionais = Adicional.objects.filter(is_active=True)
        context['categories'] = categories
        context['products'] = products
        context['adicionais'] = adicionais
        return context



class ApiUpdatePedidoView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            pedido = get_object_or_404(Pedido, pk=pk)
            data = json.loads(request.body)
            items = data.get('items', [])
            
            if not items:
                return JsonResponse({'success': False, 'message': 'O pedido não pode ficar vazio.'})

            # Remove itens antigos
            pedido.items.all().delete()
            
            total_amount = 0
            # Adicionar novos items e calcular o total
            for item_data in items:
                product = get_object_or_404(Product, id=item_data['product_id'])
                quantity = int(item_data['quantity'])
                obs = item_data.get('observation') or '' 
                
                unit_price = product.price
                # Opcional obrigatório
                opcional_id = item_data.get('opcional_id')
                if opcional_id:
                    try:
                        opcional = OpcionalObrigatorio.objects.get(id=opcional_id, is_active=True)
                        unit_price += opcional.price
                        obs = (opcional.name + (' | ' + obs if obs else '')) if obs else opcional.name
                    except OpcionalObrigatorio.DoesNotExist:
                        pass
                adicional_ids = item_data.get('adicional_ids', [])
                if adicional_ids:
                    adicionais_qs = Adicional.objects.filter(id__in=adicional_ids, is_active=True)
                    extra = sum(a.price for a in adicionais_qs)
                    unit_price += extra
                    labels = ', '.join(f'+{a.name} (R${float(a.price):.2f})' for a in adicionais_qs)
                    obs = (obs + ' | ' if obs else '') + labels
                subtotal = unit_price * quantity
                total_amount += subtotal
                
                PedidoItem.objects.create(
                    pedido=pedido,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    observations=obs 
                )
            
            pedido.total_amount = total_amount
            pedido.save()
            pedido.comanda.update_total()
            
            return JsonResponse({'success': True, 'message': 'Pedido atualizado com sucesso!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


class ApiCreatePedidoView(LoginRequiredMixin, View):
    def post(self, request, numero):
        try:
            data = json.loads(request.body)
            items = data.get('items', [])
            
            if not items:
                return JsonResponse({'success': False, 'message': 'Nenhum item selecionado.'})

            comanda = get_object_or_404(Comanda, numero=numero, status='em_uso')

            # Criar um novo Pedido na comanda
            pedido = Pedido.objects.create(
                comanda=comanda,
                status='preparando'
            )
            
            total_amount = 0
            # Adicionar itens
            for item in items:
                product = get_object_or_404(Product, id=item['product_id'])
                quantity = int(item['quantity'])
                obs = item.get('observation') or ''
                
                unit_price = product.price
                # Opcional obrigatório
                opcional_id = item.get('opcional_id')
                if opcional_id:
                    try:
                        opcional = OpcionalObrigatorio.objects.get(id=opcional_id, is_active=True)
                        unit_price += opcional.price
                        obs = (opcional.name + (' | ' + obs if obs else '')) if obs else opcional.name
                    except OpcionalObrigatorio.DoesNotExist:
                        pass
                adicional_ids = item.get('adicional_ids', [])
                if adicional_ids:
                    adicionais_qs = Adicional.objects.filter(id__in=adicional_ids, is_active=True)
                    extra = sum(a.price for a in adicionais_qs)
                    unit_price += extra
                    labels = ', '.join(f'+{a.name} (R${float(a.price):.2f})' for a in adicionais_qs)
                    obs = (obs + ' | ' if obs else '') + labels
                subtotal = unit_price * quantity
                total_amount += subtotal
                
                PedidoItem.objects.create(
                    pedido=pedido,
                    product=product,
                    quantity=quantity,
                    unit_price=unit_price,
                    observations=obs 
                )
            
            # Atualizar total do pedido
            pedido.total_amount = total_amount
            pedido.save()
            pedido.comanda.update_total()
            
            return JsonResponse({
                'success': True, 
                'message': 'Pedido adicionado com sucesso!'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


class NovoPedidoView(LoginRequiredMixin, View):
    # Em breve podemos usar o mesmo modal ou formulário
    def get(self, request, numero):
        comanda = get_object_or_404(Comanda, numero=numero)
        # TODO: renderizar form de pedido ou redirecionar para a interface de frente de caixa
        auto_open = request.POST.get('auto_open_modal')
        from django.urls import reverse
        url = reverse('orders:comanda_detail', kwargs={'numero': comanda.numero})
        if auto_open == 'true':
            url += '?modal=open'
        return redirect(url)



class FechaMesaCaixaView(LoginRequiredMixin, View):
    """Caixa/superuser fecha a mesa do cliente (aguardando_caixa), acessível pelo dashboard."""
    def post(self, request, numero):
        if not (getattr(request.user, 'is_caixa', False) or request.user.has_perm('checkouts.change_checkout')):
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'erro': 'Sem permissão'}, status=403)
        comanda = Comanda.objects.filter(
            numero=numero, status__in=['em_uso', 'aguardando_caixa']
        ).order_by('-created_at').first()
        if not comanda:
            from django.http import JsonResponse
            return JsonResponse({'ok': False, 'erro': 'Comanda não encontrada'}, status=404)
        comanda.status = 'aguardando_caixa'
        comanda.save(update_fields=['status'])
        from django.http import JsonResponse
        return JsonResponse({'ok': True})


class CancelarComandaView(LoginRequiredMixin, View):
    """
    Cancela uma comanda inteira, registrando motivo e finalizando todos os pedidos ativos.
    """
    def post(self, request, numero):
        if not request.user.has_perm('orders.change_order'):
            messages.error(request, 'Sem permissão para cancelar comandas.')
            return redirect('orders:comanda_detail', numero=numero)

        comanda = Comanda.objects.filter(
            numero=numero, status__in=['em_uso', 'aguardando_caixa']
        ).order_by('-created_at').first()
        if not comanda:
            from django.http import Http404
            raise Http404("Comanda não encontrada ou já cancelada")
        motivo = request.POST.get('motivo_cancelamento', '').strip() or 'Sem motivo informado.'

        with transaction.atomic():
            comanda.status = 'cancelada'
            comanda.motivo_cancelamento = motivo
            comanda.save()

            # Cancela todos os pedidos que ainda não foram entregues/cancelados
            for pedido in comanda.pedidos.filter(
                status__in=['aguardando', 'preparando', 'pronta']
            ):
                pedido.status = 'cancelado'
                pedido.observations = f"[COMANDA CANCELADA - Motivo: {motivo}] {pedido.observations or ''}"
                pedido.save()

        # Registra no checkout fora do atomic para não reverter o cancelamento
        try:
            from checkouts.models import Checkout
            Checkout.objects.update_or_create(
                comanda=comanda,
                defaults=dict(
                    subtotal=comanda.total_amount,
                    desconto=Decimal('0.00'),
                    taxa_servico=Decimal('0.00'),
                    total=comanda.total_amount,
                    payment_method='cancelado',
                    status='cancelado',
                    processed_by=request.user,
                    processed_at=timezone.now(),
                    notes=f'COMANDA CANCELADA - Motivo: {motivo}',
                )
            )
        except Exception as e:
            print(f"Erro ao registrar checkout de cancelamento: {e}")

        messages.warning(request, f'Comanda #{numero} foi cancelada.')
        return redirect('accounts:dashboard')


class CortesiaComandaView(LoginRequiredMixin, View):
    """
    Finaliza uma comanda como cortesia: registra observação, cancela pedidos ativos,
    mas NÃO gera fluxo de caixa nem registra no financeiro.
    """
    def post(self, request, numero):
        if not request.user.has_perm('orders.change_order'):
            messages.error(request, 'Sem permissão para registrar cortesia.')
            return redirect('orders:comanda_detail', numero=numero)

        comanda = Comanda.objects.filter(numero=numero, status='em_uso').order_by('-created_at').first()
        if not comanda:
            messages.error(request, 'Comanda não encontrada ou não está em uso.')
            return redirect('accounts:dashboard')

        observacao = request.POST.get('observacao_cortesia', '').strip()
        if not observacao:
            messages.error(request, 'A observação é obrigatória para registrar cortesia.')
            return redirect('orders:comanda_detail', numero=numero)

        with transaction.atomic():
            comanda.status = 'cortesia'
            comanda.motivo_cancelamento = observacao
            comanda.save()

            # Cancela todos os pedidos ativos
            for pedido in comanda.pedidos.filter(
                status__in=['aguardando', 'preparando', 'pronta']
            ):
                pedido.status = 'cancelado'
                pedido.observations = f"[CORTESIA - {observacao}] {pedido.observations or ''}"
                pedido.save()

        messages.success(request, f'Comanda #{numero} registrada como cortesia.')
        return redirect('accounts:dashboard')


class CancelarPedidoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Cancela especificamente 1 pedido (Order/Pedido) de dentro de uma comanda
    preenchendo a justificativa do cancelamento.
    """
    permission_required = 'orders.change_order'

    def post(self, request, pk):
        # 1. Pega o Pedido exato ou retorna 404
        pedido = get_object_or_404(Pedido, id=pk)
        
        # 2. Pega o motivo que o usuário digitou naquele modal
        motivo = request.POST.get('motivo_cancelamento', 'Sem motivo informado.')
        
        # 3. Muda o status e salva a o motivo nas observações do pedido
        pedido.status = 'cancelado'
        pedido.observations = f"[CANCELADO MOTIVO: {motivo}] - {pedido.observations or ''}"
        pedido.save()
        
        # 4. (Opcional) Você pode querer diminuir o valor da Comanda total aqui
        comanda = pedido.comanda
        if comanda.total_amount >= pedido.total_amount:
            comanda.total_amount -= pedido.total_amount
            comanda.save()

        messages.success(request, f'Pedido #{pedido.pedido_seq} cancelado com sucesso!')
        
        # 5. Redireciona de volta para a mesma tela da comanda onde ele estava
        return redirect('orders:comanda_detail', numero=comanda.numero)


class MarcarPedidoEntregueView(LoginRequiredMixin, View):
    def post(self, request, pk):
        pedido = get_object_or_404(Pedido, pk=pk)
        pedido.status = 'entregue'
        pedido.delivered_at = timezone.now()
        pedido.save()
        messages.success(request, f"Pedido #{pedido.pedido_seq} entregue com sucesso!")
        return redirect('orders:comanda_detail', numero=pedido.comanda.numero)

class RemoverItemPedidoView(LoginRequiredMixin, View):
    """
    Remove um item de um pedido já entregue e atualiza os totais.
    Requer superuser ou permissão change_order.
    """
    def post(self, request, item_pk):
        if not request.user.has_perm('orders.change_order'):
            return JsonResponse({'success': False, 'message': 'Sem permissão.'}, status=403)
        item = get_object_or_404(PedidoItem, pk=item_pk)
        pedido = item.pedido
        comanda = pedido.comanda
        item.delete()
        pedido.update_total()
        return JsonResponse({
            'success': True,
            'novo_total_pedido': str(pedido.total_amount),
            'novo_total_comanda': str(comanda.total_amount),
        })


class ImprimirPedidoView(LoginRequiredMixin, View):
    def get(self, request, pk):
        pedido = get_object_or_404(Pedido, pk=pk)
        # Registrar hora de início (sem marcar impresso — só a cozinha faz isso)
        if not pedido.started_at:
            pedido.started_at = timezone.now()
            pedido.save(update_fields=['started_at'])

        # Filtro por destino de produção (ex: ?destino=cozinha)
        destino = request.GET.get('destino')
        if destino:
            itens_filtrados = pedido.items.select_related('product').filter(product__destino_producao=destino)
        else:
            itens_filtrados = pedido.items.select_related('product').all()

        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        is_mobile = 'android' in ua or 'iphone' in ua or 'ipad' in ua

        if is_mobile:
            # Android/tablet: usar RawBT
            linhas = []
            linhas.append(str(" COPA / COZINHA ").center(48, "-"))
            linhas.append(str(" Ticket de Preparo ").center(48, " "))
            linhas.append("-" * 48)
            linhas.append(f"COMANDA: {pedido.comanda.numero}")
            linhas.append(f"PEDIDO ID: {pedido.pedido_seq}")
            data_formatada = timezone.localtime(pedido.created_at).strftime("%d/%m/%Y %H:%M")
            linhas.append(f"DATA: {data_formatada}")
            linhas.append("-" * 48)
            linhas.append("ITENS PARA PREPARAR:\n")
            for item in itens_filtrados:
                linhas.append(f"{item.quantity}x {item.product.name}")
                if item.observations:
                    linhas.append(f"   Obs: {item.observations}")
            if pedido.observations:
                linhas.append("-" * 48)
                linhas.append("OBSERVACOES GERAIS:")
                linhas.append(pedido.observations)
            linhas.append("-" * 48)
            linhas.append(str("Fim do Pedido").center(48, " "))
            linhas.append("\n\n\n\n\n")
            linhas.append("\x1d\x56\x00")

            texto_cupom = "\n".join(linhas)
            texto_encoded = urllib.parse.quote(texto_cupom)
            rawbt_intent = f"intent:{texto_encoded}#Intent;scheme=rawbt;package=ru.a402d.rawbtprinter;end;"

            return JsonResponse({"type": "rawbt", "intent_url": rawbt_intent})

        else:
            # Windows/Desktop: enviar via Flask bridge local
            linhas = []
            linhas.append(str(" COPA / COZINHA ").center(42, "-"))
            linhas.append("Ticket de Preparo".center(42))
            linhas.append("-" * 42)
            linhas.append(f"COMANDA: {pedido.comanda.numero}")
            linhas.append(f"PEDIDO: #{pedido.pedido_seq}")
            data_formatada = timezone.localtime(pedido.created_at).strftime("%d/%m/%Y %H:%M")
            linhas.append(f"DATA: {data_formatada}")
            linhas.append("-" * 42)
            linhas.append("ITENS PARA PREPARAR:")
            linhas.append("")
            for item in itens_filtrados:
                linhas.append(f"  {item.quantity}x {item.product.name}")
                if hasattr(item, 'observations') and item.observations:
                    linhas.append(f"     Obs: {item.observations}")
            if pedido.observations:
                linhas.append("-" * 42)
                linhas.append("OBS GERAIS:")
                linhas.append(pedido.observations)
            linhas.append("-" * 42)
            linhas.append("Fim do Pedido".center(42))
            linhas.append("")
            linhas.append("")
            linhas.append("")
            linhas.append("\x1d\x56\x41")
            content_text = "\n".join(linhas)
            return JsonResponse({"type": "bridge", "content_text": content_text})



class ImprimirPedidosNaoImpressosView(LoginRequiredMixin, View):
    """
    Combina todos os pedidos ativos da comanda em um unico job de impressao.
    Garante que mobile (RawBT) e desktop (Flask bridge) imprimam tudo de uma vez.
    """
    def get(self, request, pk):
        comanda = get_object_or_404(Comanda, pk=pk)
        pedidos = list(
            comanda.pedidos
            .filter(status__in=['aguardando', 'preparando', 'pronta'])
            .prefetch_related('items__product')
            .order_by('id')
        )
        if not pedidos:
            return JsonResponse({'type': 'none'})

        Pedido.objects.filter(id__in=[p.id for p in pedidos], started_at__isnull=True).update(started_at=timezone.now())

        mob_all = []
        desk_all = []

        for pedido in pedidos:
            data_fmt = timezone.localtime(pedido.created_at).strftime("%d/%m/%Y %H:%M")

            # Mobile (RawBT 48 cols)
            mob = []
            mob.append(str(" COPA / COZINHA ").center(48, "-"))
            mob.append(str(" Ticket de Preparo ").center(48, " "))
            mob.append("-" * 48)
            mob.append(f"COMANDA: {pedido.comanda.numero}")
            mob.append(f"PEDIDO: #{pedido.pedido_seq}")
            mob.append(f"DATA: {data_fmt}")
            mob.append("-" * 48)
            mob.append("ITENS PARA PREPARAR:")
            mob.append("")
            for item in pedido.items.all():
                mob.append(f"{item.quantity}x {item.product.name}")
                if item.observations:
                    mob.append(f"   Obs: {item.observations}")
            if pedido.observations:
                mob.append("-" * 48)
                mob.append("OBSERVACOES GERAIS:")
                mob.append(pedido.observations)
            mob.append("-" * 48)
            mob.append(str("Fim do Pedido").center(48, " "))
            mob.append("")
            mob.append("")
            mob.append("")
            mob_all.extend(mob)

            # Desktop (Flask bridge 42 cols)
            desk = []
            desk.append(str(" COPA / COZINHA ").center(42, "-"))
            desk.append("Ticket de Preparo".center(42))
            desk.append("-" * 42)
            desk.append(f"COMANDA: {pedido.comanda.numero}")
            desk.append(f"PEDIDO: #{pedido.pedido_seq}")
            desk.append(f"DATA: {data_fmt}")
            desk.append("-" * 42)
            desk.append("ITENS PARA PREPARAR:")
            desk.append("")
            for item in pedido.items.all():
                desk.append(f"  {item.quantity}x {item.product.name}")
                if item.observations:
                    desk.append(f"     Obs: {item.observations}")
            if pedido.observations:
                desk.append("-" * 42)
                desk.append("OBS GERAIS:")
                desk.append(pedido.observations)
            desk.append("-" * 42)
            desk.append("Fim do Pedido".center(42))
            desk.append("")
            desk.append("")
            desk_all.extend(desk)

        # Mobile: unico intent com todo o conteudo + corte no final
        mob_all.append("")
        mob_all.append("")
        mob_all.append("")
        cut = chr(0x1d) + chr(0x56) + chr(0x00)
        encoded = urllib.parse.quote("\n".join(mob_all) + cut)
        single_intent = f"intent:{encoded}#Intent;scheme=rawbt;package=ru.a402d.rawbtprinter;end;"

        # Desktop: unico conteudo com corte no final
        desk_all.append("")
        desk_all.append("VA")
        single_content = "\n".join(desk_all)

        return JsonResponse({
            "type": "rawbt_multi",
            "intent_urls": [single_intent],
            "contents": [single_content],
        })

class ImprimirComandaView(LoginRequiredMixin, UserPassesTestMixin, View):
    """
    Imprime cupom completo da comanda (todos os pedidos/itens) via RawBT para Epson
    Requer is_caixa ou is_superuser.
    """
    login_url = '/accounts/login/'

    def test_func(self):
        return self.request.user.is_caixa or self.request.user.has_perm('checkouts.view_checkout')

    def get(self, request, numero=None, pk=None):
        # Quando chamado por PK (reimpressão da lista de finalizadas), busca pelo ID exato
        # para evitar pegar a comanda ativa quando o número foi reutilizado.
        if pk:
            from django.shortcuts import get_object_or_404
            comanda = get_object_or_404(
                Comanda.objects.prefetch_related('pedidos__items__product'),
                pk=pk,
            )
        else:
            # Chamado da tela da comanda: prioriza em_uso, depois fechada mais recente
            comanda = (
                Comanda.objects.prefetch_related('pedidos__items__product')
                .filter(numero=numero)
                .order_by(
                    Case(
                        When(status='em_uso', then=0),
                        When(status='fechada', then=1),
                        default=2,
                        output_field=IntegerField(),
                    ),
                    '-updated_at',
                )
                .first()
            )
            if comanda is None:
                from django.http import Http404
                raise Http404

        ua = request.META.get('HTTP_USER_AGENT', '').lower()
        is_mobile = 'android' in ua or 'iphone' in ua or 'ipad' in ua

        if is_mobile:
            # Android/tablet: usar RawBT
            linhas = []
            linhas.append(str(" CAIXA / COMANDA ").center(48, "-"))
            linhas.append(str("COXINHAS PREMIUM CAFE").center(48, " "))
            linhas.append("-" * 48)
            linhas.append(f"COMANDA: {comanda.numero}")
            linhas.append(f"Cliente: {comanda.cliente_nome or 'Sem nome'}")
            data_formatada = timezone.localtime(comanda.created_at).strftime("%d/%m/%Y %H:%M")
            linhas.append(f"Abertura: {data_formatada}")
            linhas.append("-" * 48)
            linhas.append("ITENS PEDIDOS:")
            linhas.append("")

            for pedido in comanda.pedidos.filter(
                status__in=['aguardando', 'preparando', 'pronta', 'entregue']
            ).prefetch_related('items__product'):
                for item in pedido.items.all():
                    linhas.append(f"  {item.quantity}x {item.product.name}")
                    linhas.append(f"     R$ {float(item.unit_price):.2f} = R$ {float(item.quantity * item.unit_price):.2f}")
                    if hasattr(item, 'observations') and item.observations:
                        linhas.append(f"     Obs: {item.observations}")

            linhas.append("-" * 48)
            linhas.append(f"TOTAL: R$ {float(comanda.total_amount):.2f}")
            linhas.append("=" * 48)
            linhas.append(str("OBRIGADO!").center(48, " "))
            linhas.append("\n\n\n\n\n")
            linhas.append("\x1d\x56\x00")

            # Se tem NFC-e emitida e não cancelada, usa cupom fiscal ESC/POS
            if comanda.tem_nfce and not comanda.nfce_cancelada:
                texto_cupom = self._gerar_cupom_fiscal_escpos(comanda)
            else:
                texto_cupom = "\n".join(linhas)
            texto_encoded = urllib.parse.quote(texto_cupom)
            rawbt_intent = f"intent:{texto_encoded}#Intent;scheme=rawbt;package=ru.a402d.rawbtprinter;end;"

            html_response = f"""
            <!DOCTYPE html>
            <html>
            <body style="background-color: #f3f4f6; text-align: center; padding-top: 50px; font-family: sans-serif;">
                <h3>Enviando para a impressora...</h3>
                <script>
                    window.location.replace("{rawbt_intent}");
                    setTimeout(function() {{
                        window.history.back();
                    }}, 1000);
                </script>
            </body>
            </html>
            """
            from django.http import HttpResponse
            return HttpResponse(html_response)

        else:
            # Windows/Desktop: enviar via Flask bridge local
            linhas = []
            linhas.append("=" * 42)
            linhas.append("COXINHAS PREMIUM CAFE".center(42))
            linhas.append("Rua Coronel Fernando Prestes, 898".center(42))
            linhas.append("Centro - Itapetininga/SP".center(42))
            linhas.append("Tel: (15) 3272-1234".center(42))
            linhas.append("=" * 42)
            linhas.append(f"COMANDA: {comanda.numero}")
            linhas.append(f"Cliente: {comanda.cliente_nome or 'Sem nome'}")
            data_formatada = timezone.localtime(comanda.created_at).strftime("%d/%m/%Y %H:%M")
            linhas.append(f"Abertura: {data_formatada}")
            linhas.append("-" * 42)
            linhas.append("ITENS PEDIDOS:")
            linhas.append("")
            for pedido in comanda.pedidos.filter(
                status__in=['aguardando', 'preparando', 'pronta', 'entregue']
            ).prefetch_related('items__product'):
                for item in pedido.items.all():
                    linhas.append(f"  {item.quantity}x {item.product.name}")
                    linhas.append(f"     R$ {float(item.unit_price):.2f} = R$ {float(item.quantity * item.unit_price):.2f}")
                    if hasattr(item, 'observations') and item.observations:
                        linhas.append(f"     Obs: {item.observations}")
            linhas.append("-" * 42)
            linhas.append(f"TOTAL: R$ {float(comanda.total_amount):.2f}")
            linhas.append("=" * 42)
            linhas.append("OBRIGADO PELA PREFERENCIA!".center(42))
            linhas.append("")
            linhas.append("")
            linhas.append("")
            linhas.append("\x1d\x56\x41")
            content_text = "\n".join(linhas)

            # Se tem NFC-e emitida e não cancelada, usa cupom fiscal ESC/POS
            if comanda.tem_nfce and not comanda.nfce_cancelada:
                content_text = self._gerar_cupom_fiscal_escpos(comanda)

            return JsonResponse({"type": "bridge", "content_text": content_text})

    def _gerar_cupom_fiscal_escpos(self, comanda):
        """Gera cupom fiscal NFC-e em formato ESC/POS para impressão térmica."""
        import re as _re
        from companys.models import Company

        W = 42
        empresa = Company.objects.filter(ativa=True).first()

        def centro(txt): return txt.center(W)
        def linha(ch='-'): return ch * W

        # Coletar itens de todos os pedidos ativos
        all_items = []
        for pedido in comanda.pedidos.filter(
            status__in=['aguardando', 'preparando', 'pronta', 'entregue']
        ).prefetch_related('items__product'):
            for item in pedido.items.all():
                all_items.append(item)

        # Formas de pagamento
        _pm_label = {
            'dinheiro': 'Dinheiro', 'cartao_debito': 'Debito',
            'cartao_credito': 'Credito', 'pix': 'PIX', 'voucher': 'Voucher',
        }
        _pagamentos = []
        _total_pago = Decimal('0.00')
        try:
            co = comanda.checkout
            if co.is_parcial:
                for cp in co.payments.all():
                    _pagamentos.append((_pm_label.get(cp.payment_method, cp.payment_method), Decimal(str(cp.amount))))
                    _total_pago += Decimal(str(cp.amount))
            else:
                _pagamentos.append((_pm_label.get(co.payment_method, co.payment_method), Decimal(str(comanda.total_amount))))
                _total_pago = Decimal(str(comanda.total_amount))
        except Exception:
            _pagamentos.append(('Dinheiro', Decimal(str(comanda.total_amount))))
            _total_pago = Decimal(str(comanda.total_amount))

        _troco = max(Decimal('0.00'), _total_pago - Decimal(str(comanda.total_amount)))
        dt_emissao = timezone.localtime(comanda.nfce_emitida_em or timezone.now())

        linhas = []
        linhas.append("\x1B\x40")  # ESC @ reset

        # Cabeçalho empresa
        if empresa:
            linhas.append(centro(empresa.nome_fantasia or empresa.razao_social))
            linhas.append(centro(f"{empresa.logradouro}, {empresa.numero}"))
            linhas.append(centro(f"{empresa.bairro} - {empresa.cidade}/{empresa.uf}"))
            cnpj_fmt = _re.sub(r'(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})', r'\1.\2.\3/\4-\5',
                                _re.sub(r'\D', '', empresa.cnpj))
            linhas.append(centro(f"CNPJ: {cnpj_fmt}"))
        else:
            linhas.append(centro("COXINHAS PREMIUM LTDA"))
            linhas.append(centro("CNPJ: 10.361.831/0001-23"))

        linhas.append(linha('='))
        linhas.append(centro("NOTA FISCAL DE CONSUMIDOR"))
        linhas.append(centro("ELETRONICO - NFC-e"))
        linhas.append(centro(f"Nr: {comanda.nfce_numero:09d}  Serie: 001"))
        linhas.append(centro(dt_emissao.strftime('%d/%m/%Y  %H:%M:%S')))

        # CPF/CNPJ do consumidor
        cpf_digits = _re.sub(r'\D', '', comanda.nfce_cpf_cliente or '')
        if len(cpf_digits) == 11:
            cpf_fmt = f"{cpf_digits[:3]}.{cpf_digits[3:6]}.{cpf_digits[6:9]}-{cpf_digits[9:]}"
            linhas.append(centro(f"CPF: {cpf_fmt}"))
        elif len(cpf_digits) == 14:
            linhas.append(centro(f"CNPJ: {cpf_digits}"))
        else:
            linhas.append(centro("CONSUMIDOR NAO IDENTIFICADO"))

        linhas.append(linha('-'))
        linhas.append(f"{'#':<3} {'DESCRICAO':<22} {'QTD':>3} {'VLR':>5} {'TOT':>7}")
        linhas.append(linha('-'))

        total_geral = Decimal('0.00')
        for i, item in enumerate(all_items, 1):
            subtotal = Decimal(str(item.unit_price)) * Decimal(str(item.quantity))
            total_geral += subtotal
            nome = (item.product.name or '')[:20]
            _adics = _re.findall(r'\+([^(]+)\(R\$([\d.]+)\)', item.observations or '')
            _extra = sum(float(p) for _, p in _adics)
            _base = float(item.unit_price) - _extra
            linhas.append(f"{i:<3} {nome:<20} {int(item.quantity):>3} {_base:>5.2f} {_base * float(item.quantity):>7.2f}")
            for _aname, _aprice in _adics:
                linhas.append(f"    {int(item.quantity)}x +{_aname.strip():<26}  {float(_aprice) * float(item.quantity):>6.2f}")
            _obs_clean = _re.sub(r'\+[^(]+\(R\$[\d.]+\),?\s*', '', item.observations or '').strip(' |,').strip()
            if _obs_clean:
                linhas.append(f"    Obs: {_obs_clean[:33]}")

        linhas.append(linha('-'))
        linhas.append(f"{'TOTAL':.<34} R${float(total_geral):>7.2f}")
        linhas.append(linha('-'))

        for label, valor in _pagamentos:
            linhas.append(f"{label:<30} R${float(valor):>7.2f}")
        if _troco > Decimal('0.00'):
            linhas.append(f"{'Troco':<30} R${float(_troco):>7.2f}")

        linhas.append(linha('-'))

        # Tributos
        tributos = float(total_geral) * 0.20
        linhas.append(f"Trib.aprox: R${tributos:.2f} ({tributos/float(total_geral)*100:.1f}%) Fonte:IBPT")

        # Chave de acesso (quebrada em 2 linhas de 22 chars)
        linhas.append("")
        linhas.append(centro("Consulte pelo QR Code ou:"))
        chave = comanda.nfce_chave or ''
        linhas.append(chave[:22])
        linhas.append(chave[22:44])

        # Protocolo
        if comanda.nfce_protocolo:
            linhas.append("")
            linhas.append(centro(f"Prot: {comanda.nfce_protocolo}"))
            linhas.append(centro(dt_emissao.strftime('%d/%m/%Y %H:%M:%S')))

        linhas.append(linha('='))
        linhas.append(centro("OBRIGADO PELA PREFERENCIA!"))
        linhas.append("")
        linhas.append("")
        linhas.append("")
        linhas.append("\x1d\x56\x41")  # corte

        return "\n".join(linhas)


# ─────────────────────────────────────────────
#  PAINEL DA COZINHA
# ─────────────────────────────────────────────

class CozinhaPainelView(LoginRequiredMixin, View):
    """Renderiza a tela do painel de cozinha."""
    login_url = reverse_lazy('accounts:login')

    def get(self, request):
        return render(request, 'orders/cozinha_painel.html')


class CozinhaApiPedidosView(LoginRequiredMixin, View):
    """
    JSON polling: retorna todos os pedidos de cozinha ativos.
    Pedidos com impresso=False → novos (vermelho piscando)
    Pedidos com impresso=True  → em produção (amarelo)
    Desaparece quando status = 'entregue' ou 'cancelado'
    """
    login_url = reverse_lazy('accounts:login')

    def get(self, request):
        pedidos = (
            Pedido.objects
            .filter(
                status__in=['aguardando', 'preparando', 'pronta'],
                items__product__destino_producao='cozinha',
            )
            .distinct()
            .select_related('comanda')
            .prefetch_related('items__product')
            .order_by('-created_at')
        )

        data = []
        for p in pedidos:
            itens_cozinha = [
                {
                    'qty': item.quantity,
                    'nome': item.product.name,
                    'obs': item.observations or '',
                }
                for item in p.items.all()
                if item.product.destino_producao == 'cozinha'
            ]
            data.append({
                'id': p.id,
                'pedido_seq': p.pedido_seq,
                'comanda_numero': p.comanda.numero,
                'cliente_nome': p.comanda.cliente_nome or '',
                'created_at': timezone.localtime(p.created_at).strftime('%d/%m/%Y %H:%M'),
                'created_at_ts': int(p.created_at.timestamp()),
                'impresso': p.impresso,
                'status': p.status,
                'observations': p.observations or '',
                'itens_cozinha': itens_cozinha,
                'imprimir_url': f'/orders/pedido/{p.id}/imprimir/?destino=cozinha',
            })

        return JsonResponse({'pedidos': data})


class CozinhaMarcarImpressoView(LoginRequiredMixin, View):
    """
    POST: marca pedido como impresso e coloca em 'preparando'.
    Chamado após o clique em Imprimir no painel da cozinha.
    """
    login_url = reverse_lazy('accounts:login')

    def post(self, request, pk):
        pedido = get_object_or_404(Pedido, pk=pk)
        pedido.impresso = True
        if pedido.status == 'aguardando':
            pedido.status = 'preparando'
            pedido.started_at = timezone.now()
        pedido.save(update_fields=['impresso', 'status', 'started_at'])
        return JsonResponse({'ok': True, 'status': pedido.status})
