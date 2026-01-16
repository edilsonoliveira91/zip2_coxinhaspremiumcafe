from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.http import JsonResponse
from django.views import View
from django.core.paginator import Paginator
from .models import Pinpad
from .forms import PinpadForm
import time
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from .services import get_payment_service
import logging


logger = logging.getLogger(__name__)


class PointTestView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Página de teste para integração Point
    """
    permission_required = 'pinpads.view_pinpad'
    template_name = 'point_test.html'


class PinpadListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Lista de pinpads cadastrados
    """
    permission_required = 'pinpads.view_pinpad'
    model = Pinpad
    template_name = 'pinpad_list.html'
    context_object_name = 'pinpads'
    paginate_by = 12
    
    def get_queryset(self):
        """Filtros de busca"""
        queryset = Pinpad.objects.select_related('created_by', 'updated_by')
        
        # Filtro por busca
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search) |
                Q(provider__icontains=search) |
                Q(merchant_id__icontains=search) |
                Q(terminal_id__icontains=search)
            )
        
        # Filtro por provedor
        provider = self.request.GET.get('provider')
        if provider:
            queryset = queryset.filter(provider=provider)
            
        # Filtro por status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        # Filtro por ativo/inativo
        active = self.request.GET.get('active')
        if active == 'true':
            queryset = queryset.filter(is_active=True)
        elif active == 'false':
            queryset = queryset.filter(is_active=False)
        
        return queryset.order_by('-is_default', '-is_active', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Estatísticas gerais
        all_pinpads = Pinpad.objects.all()
        
        # Estatísticas por provedor
        provider_stats = all_pinpads.values('provider').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Taxas médias
        avg_credit_fee = all_pinpads.filter(
            is_active=True, supports_credit=True
        ).aggregate(avg_fee=Avg('credit_fee_percentage'))['avg_fee'] or 0
        
        avg_debit_fee = all_pinpads.filter(
            is_active=True, supports_debit=True
        ).aggregate(avg_fee=Avg('debit_fee_percentage'))['avg_fee'] or 0
        
        context.update({
            # Estatísticas básicas
            'total_pinpads': all_pinpads.count(),
            'active_pinpads': all_pinpads.filter(is_active=True).count(),
            'inactive_pinpads': all_pinpads.filter(is_active=False).count(),
            'default_pinpad': all_pinpads.filter(is_default=True).first(),
            
            # Estatísticas por status
            'status_stats': {
                'ativo': all_pinpads.filter(status='ativo').count(),
                'inativo': all_pinpads.filter(status='inativo').count(),
                'manutencao': all_pinpads.filter(status='manutencao').count(),
                'teste': all_pinpads.filter(status='teste').count(),
            },
            
            # Estatísticas por provedor
            'provider_stats': provider_stats,
            
            # Taxas médias
            'avg_credit_fee': round(avg_credit_fee, 2),
            'avg_debit_fee': round(avg_debit_fee, 2),
            
            # Opções para filtros
            'provider_choices': Pinpad.PROVIDER_CHOICES,
            'status_choices': Pinpad.STATUS_CHOICES,
            
            # Valores atuais dos filtros
            'current_search': self.request.GET.get('search', ''),
            'current_provider': self.request.GET.get('provider', ''),
            'current_status': self.request.GET.get('status', ''),
            'current_active': self.request.GET.get('active', ''),
            
            # Estatísticas de recursos
            'credit_support_count': all_pinpads.filter(supports_credit=True).count(),
            'debit_support_count': all_pinpads.filter(supports_debit=True).count(),
            'contactless_support_count': all_pinpads.filter(supports_contactless=True).count(),
        })
        
        return context


class PinpadCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Criar novo pinpad
    """
    permission_required = 'pinpads.add_pinpad'
    model = Pinpad
    form_class = PinpadForm
    template_name = 'pinpad_form.html'
    success_url = reverse_lazy('pinpads:pinpad_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(
            self.request, 
            f'Pinpad "{form.instance.name}" criado com sucesso!'
        )
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(
            self.request, 
            'Erro ao criar pinpad. Verifique os dados informados.'
        )
        return super().form_invalid(form)


class PinpadUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Editar pinpad existente
    """
    permission_required = 'pinpads.change_pinpad'
    model = Pinpad
    form_class = PinpadForm
    template_name = 'pinpad_form.html'
    success_url = reverse_lazy('pinpads:pinpad_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(
            self.request, 
            f'Pinpad "{form.instance.name}" atualizado com sucesso!'
        )
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(
            self.request, 
            'Erro ao atualizar pinpad. Verifique os dados informados.'
        )
        return super().form_invalid(form)


class PinpadDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    Excluir pinpad
    """
    permission_required = 'pinpads.delete_pinpad'
    model = Pinpad
    template_name = 'pinpads/pinpad_confirm_delete.html'
    success_url = reverse_lazy('pinpads:pinpad_list')
    
    def delete(self, request, *args, **kwargs):
        pinpad = self.get_object()
        if pinpad.is_default:
            messages.error(
                request, 
                'Não é possível excluir o pinpad padrão do sistema!'
            )
            return redirect('pinpads:pinpad_list')
        
        messages.success(
            request, 
            f'Pinpad "{pinpad.name}" excluído com sucesso!'
        )
        return super().delete(request, *args, **kwargs)


# =============================================================================
# VIEWS DE API/AJAX
# =============================================================================

class PinpadTestConnectionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para testar conexão com pinpad
    """
    permission_required = 'pinpads.view_pinpad'
    
    def post(self, request, pk):
        try:
            pinpad = get_object_or_404(Pinpad, pk=pk)
            
            # Executar teste de conexão
            result = pinpad.test_connection()
            
            return JsonResponse({
                'success': result['success'],
                'message': result['message'],
                'last_test_at': pinpad.last_test_at.strftime('%d/%m/%Y %H:%M') if pinpad.last_test_at else None,
                'last_test_success': pinpad.last_test_success,
            })
            
        except Pinpad.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Pinpad não encontrado!'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro interno: {str(e)}'
            }, status=500)


class PinpadSetDefaultView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para definir pinpad como padrão
    """
    permission_required = 'pinpads.change_pinpad'
    
    def post(self, request, pk):
        try:
            pinpad = get_object_or_404(Pinpad, pk=pk)
            
            if not pinpad.is_active:
                return JsonResponse({
                    'success': False,
                    'message': 'Apenas pinpads ativos podem ser definidos como padrão!'
                }, status=400)
            
            # Remover padrão de todos os outros
            Pinpad.objects.filter(is_default=True).update(is_default=False)
            
            # Definir este como padrão
            pinpad.is_default = True
            pinpad.updated_by = request.user
            pinpad.save()
            
            messages.success(
                request,
                f'Pinpad "{pinpad.name}" definido como padrão!'
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Pinpad "{pinpad.name}" definido como padrão!',
                'is_default': True,
            })
            
        except Pinpad.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Pinpad não encontrado!'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro interno: {str(e)}'
            }, status=500)


class PinpadToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para ativar/desativar pinpad
    """
    permission_required = 'pinpads.change_pinpad'
    
    def post(self, request, pk):
        try:
            pinpad = get_object_or_404(Pinpad, pk=pk)
            
            # Toggle do status ativo
            pinpad.is_active = not pinpad.is_active
            
            # Se desativando o pinpad padrão, remover como padrão
            if not pinpad.is_active and pinpad.is_default:
                pinpad.is_default = False
                
            pinpad.updated_by = request.user
            pinpad.save()
            
            status_text = "ativado" if pinpad.is_active else "desativado"
            
            return JsonResponse({
                'success': True,
                'message': f'Pinpad "{pinpad.name}" {status_text} com sucesso!',
                'is_active': pinpad.is_active,
                'is_default': pinpad.is_default,
            })
            
        except Pinpad.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Pinpad não encontrado!'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro interno: {str(e)}'
            }, status=500)


class PinpadStatsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para estatísticas dos pinpads
    """
    permission_required = 'pinpads.view_pinpad'
    
    def get(self, request):
        try:
            all_pinpads = Pinpad.objects.all()
            
            stats = {
                'total': all_pinpads.count(),
                'active': all_pinpads.filter(is_active=True).count(),
                'inactive': all_pinpads.filter(is_active=False).count(),
                'default': all_pinpads.filter(is_default=True).exists(),
                
                # Por provedor
                'by_provider': list(
                    all_pinpads.values('provider').annotate(
                        count=Count('id'),
                        active_count=Count('id', filter=Q(is_active=True))
                    ).order_by('-count')
                ),
                
                # Por status
                'by_status': {
                    status[0]: all_pinpads.filter(status=status[0]).count()
                    for status in Pinpad.STATUS_CHOICES
                },
                
                # Recursos suportados
                'features': {
                    'credit': all_pinpads.filter(supports_credit=True).count(),
                    'debit': all_pinpads.filter(supports_debit=True).count(),
                    'contactless': all_pinpads.filter(supports_contactless=True).count(),
                }
            }
            
            return JsonResponse({
                'success': True,
                'stats': stats
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro ao carregar estatísticas: {str(e)}'
            }, status=500)



# =============================================================================
# VIEWS DE MAQUININHA POINT MERCADO PAGO
# =============================================================================
class PointDevicesView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para listar dispositivos Point
    """
    permission_required = 'pinpads.view_pinpad'
    
    def get(self, request, pinpad_id):
        try:
            pinpad = get_object_or_404(Pinpad, pk=pinpad_id, is_active=True)
            
            if not pinpad.api_key:
                return JsonResponse({
                    'success': False,
                    'message': 'Pinpad sem credenciais configuradas'
                }, status=400)
            
            service = get_payment_service(pinpad)
            result = service.get_devices()
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro interno: {str(e)}'
            }, status=500)


class PointPaymentView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para criar pagamento no Point
    """
    permission_required = 'pinpads.change_pinpad'
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request, pinpad_id):
        try:
            pinpad = get_object_or_404(Pinpad, pk=pinpad_id, is_active=True)
            
            # Parse dados do request
            data = json.loads(request.body)
            device_id = data.get('device_id')
            amount = float(data.get('amount', 0))
            description = data.get('description', 'Venda')
            payment_type = data.get('payment_type', 'credit')  # credit, debit, pix
            
            if not device_id and payment_type != 'pix':
                return JsonResponse({
                    'success': False,
                    'message': 'ID do dispositivo é obrigatório'
                }, status=400)
            
            if amount <= 0:
                return JsonResponse({
                    'success': False,
                    'message': 'Valor deve ser maior que zero'
                }, status=400)
            
            service = get_payment_service(pinpad)
            
            # Processar baseado no tipo de pagamento
            if payment_type == 'pix':
                result = service.create_pix_payment(amount, description)
            else:
                result = service.create_payment_intent(device_id, amount, description, payment_type)
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Dados inválidos'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro interno: {str(e)}'
            }, status=500)


class PointPaymentStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para consultar status do pagamento Point
    """
    permission_required = 'pinpads.view_pinpad'
    
    def get(self, request, pinpad_id, payment_intent_id):
        try:
            pinpad = get_object_or_404(Pinpad, pk=pinpad_id, is_active=True)
            
            service = get_payment_service(pinpad)
            result = service.get_payment_intent(payment_intent_id)
            
            return JsonResponse(result)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Erro interno: {str(e)}'
            }, status=500)


@csrf_exempt
def mercadopago_webhook(request):
    """
    Webhook para receber notificações do Mercado Pago
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Log da notificação
            logger.info(f"Webhook recebido: {data}")
            
            # Processar notificação
            # Aqui você pode implementar a lógica para atualizar o status do pagamento
            # no seu sistema baseado na notificação recebida
            
            return JsonResponse({'status': 'ok'})
            
        except Exception as e:
            logger.error(f"Erro no webhook: {str(e)}")
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)