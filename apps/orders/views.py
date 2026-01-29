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
    
    def get_context_data(self, **kwargs):
        from django.utils import timezone
        context = super().get_context_data(**kwargs)
        
        # Detectar se é impressão fiscal
        is_fiscal = self.request.GET.get('fiscal') == 'true'
        
        # Calcular subtotal para cada item
        order = context['order']
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


# Adicione estes imports no início do arquivo (se não existirem):
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import logging

# Adicione no final do arquivo views.py:

class EmitirNFCeView(LoginRequiredMixin, View):
    """
    View para emissão de NFCe de uma comanda finalizada
    """
    
    def post(self, request, code):
        """
        Processa a emissão de NFCe para uma comanda
        """
        try:
            # Busca a comanda
            order = get_object_or_404(
                Order,
                code=code,
                status='entregue'  # Só permite NFCe de comandas entregues
            )
            
            # Verifica se já foi emitida NFCe
            if hasattr(order, 'nfce') and order.nfce:
                return JsonResponse({
                    'success': False,
                    'message': f'NFCe já foi emitida para esta comanda. Número: {order.nfce.numero}'
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
            resultado = self._processar_emissao_nfce(order, empresa)
            
            if resultado['success']:
                # Salva dados da NFCe na comanda
                self._salvar_nfce_na_comanda(order, resultado['dados_nfce'])
                
                return JsonResponse({
                    'success': True,
                    'message': 'NFCe emitida com sucesso!',
                    'numero_nfce': resultado['dados_nfce']['numero'],
                    'chave_acesso': resultado['dados_nfce']['chave_acesso']
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': f"Erro na emissão: {resultado['erro']}"
                })
                
        except Order.DoesNotExist:
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
        Processa a emissão da NFCe usando a biblioteca PyNFe
        """
        try:
            # Importa a biblioteca de NFCe (PyNFe será implementada depois)
            # Por enquanto, simula a emissão
            
            # Gera próximo número da NFCe
            proximo_numero = empresa.proximo_numero_nfce
            
            # Monta dados da NFCe
            dados_nfce = self._montar_dados_nfce(order, empresa, proximo_numero)
            
            # Simula emissão (substituir pela integração real com PyNFe)
            if self._simular_emissao_nfce(dados_nfce):
                # Incrementa número da empresa
                empresa.proximo_numero_nfce = proximo_numero + 1
                empresa.save()
                
                return {
                    'success': True,
                    'dados_nfce': {
                        'numero': proximo_numero,
                        'serie': empresa.serie_nfce,
                        'chave_acesso': f"2026{empresa.cnpj.replace('.', '').replace('/', '').replace('-', '')}{proximo_numero:09d}",
                        'protocolo': f"PRO{timezone.now().strftime('%Y%m%d%H%M%S')}",
                        'data_emissao': timezone.now(),
                        'valor_total': order.total_amount
                    }
                }
            else:
                return {
                    'success': False,
                    'erro': 'Falha na comunicação com a SEFAZ'
                }
                
        except Exception as e:
            return {
                'success': False,
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
    
    def _salvar_nfce_na_comanda(self, order, dados_nfce):
        """
        Salva os dados da NFCe na comanda
        TODO: Criar modelo NFCe relacionado com Order
        """
        # Por enquanto salva em campos simples na Order
        # Depois criar um modelo NFCe separado
        order.nfce_numero = dados_nfce['numero']
        order.nfce_chave = dados_nfce['chave_acesso']
        order.nfce_protocolo = dados_nfce['protocolo']
        order.nfce_emitida_em = dados_nfce['data_emissao']
        order.save()


import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

@method_decorator(csrf_exempt, name='dispatch')
class CheckoutDirectPrintView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    View para impressão direta na impressora
    """
    permission_required = 'checkouts.view_checkout'
    
    def post(self, request, *args, **kwargs):
        code = self.kwargs.get('code')
        is_fiscal = request.POST.get('fiscal') == 'true'
        
        try:
            order = Order.objects.prefetch_related('items__product').get(code=code)
            
            # Gerar conteúdo do cupom
            cupom_content = self._gerar_cupom_content(order, is_fiscal)
            
            # Enviar para impressora (implementar conforme sua impressora)
            success = self._enviar_para_impressora(cupom_content)
            
            if success:
                return JsonResponse({
                    'success': True,
                    'message': 'Cupom impresso com sucesso!'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Falha ao enviar para impressora'
                })
                
        except Order.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': f'Comanda #{code} não encontrada'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro: {str(e)}'
            })
    
    def _gerar_cupom_content(self, order, is_fiscal):
        """Gera o conteúdo do cupom em formato texto"""
        
        lines = []
        lines.append("=" * 40)
        lines.append("      COXINHAS PREMIUM CAFÉ")
        lines.append("       Cafeteria & Salgados")
        lines.append("       Tel: (11) 9999-9999")
        lines.append("=" * 40)
        
        if is_fiscal and order.tem_nfce:
            lines.append("")
            lines.append("      ** CUPOM FISCAL **")
            lines.append(f"      NFCe N° {order.nfce_numero}")
            lines.append("")
        
        lines.append(f"COMANDA #{order.code}")
        lines.append(f"Cliente: {order.name}")
        lines.append(f"Data: {order.created_at.strftime('%d/%m/%Y %H:%M')}")
        lines.append("-" * 40)
        lines.append("ITENS:")
        
        for item in order.items.all():
            subtotal = item.quantity * item.unit_price
            lines.append(f"{item.quantity}x {item.product.name}")
            lines.append(f"   R$ {item.unit_price:.2f} = R$ {subtotal:.2f}")
        
        lines.append("-" * 40)
        lines.append(f"TOTAL: R$ {order.total_amount:.2f}")
        lines.append("=" * 40)
        lines.append("   Obrigado pela preferência!")
        lines.append("     ★★★ Volte sempre! ★★★")
        lines.append("")
        
        return "\n".join(lines)
    
    def _enviar_para_impressora(self, content):
        """
        Enviar conteúdo para impressora
        Implementar conforme o tipo de impressora que você tem
        """
        
        try:
            # OPÇÃO 1: Para impressora de rede/IP
            # import socket
            # printer_ip = "192.168.1.100"  # IP da sua impressora
            # printer_port = 9100
            # sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # sock.connect((printer_ip, printer_port))
            # sock.send(content.encode('utf-8'))
            # sock.close()
            
            # OPÇÃO 2: Para impressora USB/Serial no Windows
            # import win32print
            # printer_name = win32print.GetDefaultPrinter()
            # win32print.StartDocPrinter(printer_name, 1, ("Cupom", None, "RAW"))
            # win32print.WritePrinter(printer_name, content.encode('utf-8'))
            # win32print.EndDocPrinter(printer_name)
            
            # OPÇÃO 3: Para Linux (lp command)
            # import subprocess
            # subprocess.run(['lp', '-d', 'nome_impressora'], input=content.encode('utf-8'))
            
            # TEMPORÁRIO: Apenas log para teste
            print("CUPOM PARA IMPRESSÃO:")
            print(content)
            print("=" * 50)
            
            return True
            
        except Exception as e:
            print(f"Erro ao imprimir: {e}")
            return False