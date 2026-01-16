from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum
import json
from .models import Order, OrderItem
from .forms import OrderForm, OrderItemFormSet, ScannerForm, OrderStatusForm
from products.models import Product


class OrderDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Dashboard principal das comandas - substitui o dashboard da home
    """
    permission_required = 'orders.view_order'
    template_name = 'orders/dashboard.html'
    login_url = reverse_lazy('accounts:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        today = timezone.now().date()
        
        # Estatísticas do dia
        orders_today = Order.objects.filter(created_at__date=today)
        
        context.update({
            # Comandas por status
            'aguardando': orders_today.filter(status='aguardando').count(),
            'preparando': orders_today.filter(status='preparando').count(),
            'prontas': orders_today.filter(status='pronta').count(),
            'entregues': orders_today.filter(status='entregue').count(),
            
            # Comandas ativas para exibir no dashboard
            'comandas_ativas': orders_today.exclude(
                status__in=['entregue', 'cancelada']
            ).order_by('-created_at')[:10],
            
            # Produtos para o modal (mantendo compatibilidade)
            'products': Product.objects.filter(
                is_active=True,
                show_in_menu=True
            ).order_by('category', 'name'),
            
            # Estatísticas
            'total_vendas': orders_today.aggregate(
                total=Sum('total_amount')
            )['total'] or 0,
            
            'total_comandas': orders_today.count(),
        })
        
        return context


class OrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Lista todas as comandas
    """
    permission_required = 'orders.view_order'
    model = Order
    template_name = 'orders/list.html'
    context_object_name = 'orders'
    paginate_by = 20
    login_url = reverse_lazy('accounts:login')
    
    def get_queryset(self):
        queryset = Order.objects.all().order_by('-created_at')
        
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
    model = Order
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
    model = Order
    form_class = OrderForm
    template_name = 'orders/create.html'
    login_url = reverse_lazy('accounts:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['formset'] = OrderItemFormSet(self.request.POST)
        else:
            context['formset'] = OrderItemFormSet()
        
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
            comandas_abertas = Order.objects.filter(
                name=name,
                status__in=['aguardando', 'preparando', 'pronta']
            )
            if comandas_abertas.exists():
                return JsonResponse({
                    'success': False,
                    'message': f'Já existe uma comanda aberta com o número {name}!'
                }, status=400)
            
            # Criar comanda
            order = Order.objects.create(
                name=name,
                observations=data.get('observations', ''),
                created_by=request.user
            )
            
            # Adicionar itens
            for item_data in items:
                try:
                    product = Product.objects.get(id=item_data['id'])
                    OrderItem.objects.create(
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
    model = Order
    form_class = OrderForm
    template_name = 'orders/edit.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    login_url = reverse_lazy('accounts:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.request.POST:
            context['formset'] = OrderItemFormSet(
                self.request.POST,
                instance=self.object
            )
        else:
            context['formset'] = OrderItemFormSet(instance=self.object)
        
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
    model = Order
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
    model = Order
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
    model = Order
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
        order = get_object_or_404(Order, code=code)
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
        order = get_object_or_404(Order, code=code)
        order.status = 'pronta'
        order.finished_at = timezone.now()
        order.updated_by = request.user
        order.save()
        
        messages.success(request, f'Comanda #{code} marcada como Pronta!')
        return redirect('orders:detail', code=code)


class OrderDeliverView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Marcar como Entregue"""
    
    def post(self, request, code):
        order = get_object_or_404(Order, code=code)
        order.status = 'entregue'
        order.delivered_at = timezone.now()
        order.updated_by = request.user
        order.save()
        
        messages.success(request, f'Comanda #{code} marcada como Entregue!')
        return redirect('orders:detail', code=code)


class OrderCancelView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Cancelar comanda"""
    
    def post(self, request, code):
        order = get_object_or_404(Order, code=code)
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
        return Order.objects.filter(status=status).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_status'] = self.kwargs['status']
        return context


class TodayOrdersView(OrderListView):
    """Comandas de hoje"""
    
    def get_queryset(self):
        today = timezone.now().date()
        return Order.objects.filter(created_at__date=today).order_by('-created_at')


class ActiveOrdersView(OrderListView):
    """Comandas ativas (não entregues nem canceladas)"""
    
    def get_queryset(self):
        return Order.objects.exclude(
            status__in=['entregue', 'cancelada']
        ).order_by('-created_at')


# API Views
class OrderStatusAPIView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """API para atualizar status via AJAX"""

    permission_required = 'orders.change_order'

    def post(self, request, code):
        try:
            order = get_object_or_404(Order, code=code)
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
    model = Order
    template_name = 'orders/print.html'
    context_object_name = 'order'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    login_url = reverse_lazy('accounts:login')


class OrderBarcodeView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """Gerar código de barras para impressão"""
    permission_required = 'orders.view_order'
    model = Order
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
            order = get_object_or_404(Order, code=code)
            
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
            order = get_object_or_404(Order, code=code)
            data = json.loads(request.body)
            
            # Limpar itens existentes
            order.items.all().delete()
            
            # Adicionar novos itens
            total_amount = 0
            for item_data in data.get('items', []):
                product = Product.objects.get(id=item_data['product_id'])
                
                OrderItem.objects.create(
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
            order = get_object_or_404(Order, code=code)
            data = json.loads(request.body)
            
            new_status = data.get('status')
            if new_status not in dict(Order.STATUS_CHOICES):
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
            order = get_object_or_404(Order, code=code)
            
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
    model = Order
    template_name = 'orders/closed_orders_list.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        """Retorna apenas comandas finalizadas"""
        return Order.objects.filter(
            status='entregue'
        ).select_related().prefetch_related('items__product').order_by('-delivered_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estatísticas das comandas finalizadas
        finalized_orders = self.get_queryset()
        
        context.update({
            'total_finalizadas': finalized_orders.count(),
            'total_receita': finalized_orders.aggregate(
                total=Sum('total_amount')
            )['total'] or 0,
        })
        
        return context


class ClosedOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detalhes de uma comanda finalizada específica
    """
    permission_required = 'orders.view_order'
    model = Order
    template_name = 'orders/closed_order_detail.html'
    context_object_name = 'order'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    login_url = reverse_lazy('accounts:login')
    
    def get_queryset(self):
        """Garante que só comandas finalizadas sejam acessadas"""
        return Order.objects.filter(status='entregue')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estatísticas da comanda
        order = self.get_object()
        
        # Tempo total de atendimento
        if order.created_at and order.delivered_at:
            duration = order.delivered_at - order.created_at
            context['duration_minutes'] = duration.total_seconds() // 60
        
        # Próxima e anterior comanda finalizada (para navegação)
        context['next_order'] = Order.objects.filter(
            status='entregue',
            delivered_at__gt=order.delivered_at
        ).order_by('delivered_at').first()
        
        context['prev_order'] = Order.objects.filter(
            status='entregue',
            delivered_at__lt=order.delivered_at
        ).order_by('-delivered_at').first()
        
        return context