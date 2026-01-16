from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from checkouts.models import Checkout
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from .models import Sangria
from django.views import View


class FinancialDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Dashboard financeiro com filtros e relatórios
    """
    permission_required = 'checkouts.view_checkout'
    template_name = 'financial_dashboard.html'
    login_url = reverse_lazy('accounts:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Pegar filtros da URL
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        # Definir período padrão (hoje)
        if not start_date:
            start_date = timezone.localtime().date()
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
        if not end_date:
            end_date = timezone.localtime().date()
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Filtrar checkouts por período
        checkouts = Checkout.objects.filter(
            status='aprovado',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).select_related('order')
        
        # Sangrias do período
        sangrias_periodo = Sangria.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).aggregate(
            total=Sum('valor'),
            count=Count('id')
        )
        total_sangrias = sangrias_periodo['total'] or Decimal('0.00')
        
        # Calcular valores por forma de pagamento
        payment_stats = {}
        
        # Sangria (retiradas do caixa)
        payment_stats['sangria'] = {
            'total': total_sangrias,
            'count': sangrias_periodo['count'] or 0,
            'label': 'Sangria',
            'icon': '💸',
            'color': 'red'
        }
        
        # Valor inicial (fixo)
        valor_inicial = Decimal('50.00')
        payment_stats['valor_inicial'] = {
            'total': valor_inicial,
            'count': 1,
            'label': 'Valor Inicial',
            'icon': '💰',
            'color': 'yellow'
        }

        # Dinheiro
        dinheiro = checkouts.filter(payment_method='dinheiro').aggregate(
            total=Sum('total'),
            count=Count('id')
        )
        payment_stats['dinheiro'] = {
            'total': dinheiro['total'] or Decimal('0.00'),
            'count': dinheiro['count'] or 0,
            'label': 'Dinheiro',
            'icon': '💵',
            'color': 'green'
        }
        
        # Cartão de Crédito
        credito = checkouts.filter(payment_method='cartao_credito').aggregate(
            total=Sum('total'),
            count=Count('id')
        )
        payment_stats['cartao_credito'] = {
            'total': credito['total'] or Decimal('0.00'),
            'count': credito['count'] or 0,
            'label': 'Cartão de Crédito',
            'icon': '💳',
            'color': 'blue'
        }
        
        # Cartão de Débito
        debito = checkouts.filter(payment_method='cartao_debito').aggregate(
            total=Sum('total'),
            count=Count('id')
        )
        payment_stats['cartao_debito'] = {
            'total': debito['total'] or Decimal('0.00'),
            'count': debito['count'] or 0,
            'label': 'Cartão de Débito',
            'icon': '💳',
            'color': 'purple'
        }
        
        # PIX
        pix = checkouts.filter(payment_method='pix').aggregate(
            total=Sum('total'),
            count=Count('id')
        )
        payment_stats['pix'] = {
            'total': pix['total'] or Decimal('0.00'),
            'count': pix['count'] or 0,
            'label': 'PIX',
            'icon': '📱',
            'color': 'orange'
        }
        
        # Total geral
        total_receita = (checkouts.aggregate(total=Sum('total'))['total'] or Decimal('0.00')) + valor_inicial - total_sangrias
        total_comandas = checkouts.count()
        
        # ===== LISTA COMBINADA DE COMANDAS E SANGRIAS =====
        checkouts_list = checkouts.order_by('-created_at')
        sangrias_list = Sangria.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).select_related('usuario').order_by('-created_at')

        # Criar lista combinada
        combined_list = []

        # Adicionar comandas
        for checkout in checkouts_list:
            combined_list.append({
                'type': 'comanda',
                'id': checkout.order.id,
                'code': checkout.order.code,
                'cliente': checkout.order.name,
                'pagamento': checkout.get_payment_method_display(),
                'valor': checkout.total,
                'data': checkout.created_at,
                'item': checkout
            })

        # Adicionar sangrias
        for sangria in sangrias_list:
            combined_list.append({
                'type': 'sangria',
                'id': sangria.id,
                'code': f'SGR-{sangria.id}',
                'cliente': sangria.usuario.get_full_name() or sangria.usuario.username,
                'pagamento': 'SANGRIA',
                'valor': sangria.valor,
                'data': sangria.created_at,
                'item': sangria
            })

        # Ordenar por data (mais recentes primeiro) e limitar a 50
        orders_list = sorted(combined_list, key=lambda x: x['data'], reverse=True)[:50]
        
        # Estatísticas de comparação
        today_stats = Checkout.objects.filter(
            status='aprovado',
            created_at__date=timezone.localtime().date()
        )

        yesterday = timezone.localtime().date() - timedelta(days=1)
        yesterday_stats = Checkout.objects.filter(
            status='aprovado',
            created_at__date=yesterday
        )
        
        context.update({
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'payment_stats': payment_stats,
            'total_receita': total_receita,
            'total_comandas': total_comandas,
            'orders_list': orders_list,
            
            # Estatísticas de comparação
            'today_total': today_stats.aggregate(total=Sum('total'))['total'] or 0,
            'today_count': today_stats.count(),
            'yesterday_total': yesterday_stats.aggregate(total=Sum('total'))['total'] or 0,
            'yesterday_count': yesterday_stats.count(),
            
            # Meta data para os filtros
            'date_range_days': (end_date - start_date).days + 1,
        })
        
        return context


class SangriaView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Página principal de sangrias
    """
    permission_required = 'financials.can_add_sangria'
    template_name = 'financial_sangria.html'
    login_url = reverse_lazy('accounts:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Pegar filtros da URL
        data_inicio = self.request.GET.get('data_inicio')
        data_fim = self.request.GET.get('data_fim')
        
        if not data_inicio:
            # Início do dia de hoje em horário local
            inicio_hoje = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
            data_inicio = timezone.localtime().date() 
        else:
            data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
            
        if not data_fim:
            # Fim do dia de hoje em horário local
            fim_hoje = timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=999999)
            data_fim = fim_hoje.date()
        else:
            data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
        
        # Filtrar sangrias para a LISTAGEM (usa o período filtrado)
        sangrias = Sangria.objects.filter(
            created_at__date__gte=data_inicio,
            created_at__date__lte=data_fim
        ).select_related('usuario').order_by('-created_at')
        
        # Calcular total de sangrias do PERÍODO (para a listagem)
        total_sangrias_periodo = sangrias.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        total_formatado = f"R$ {total_sangrias_periodo:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        # ===== CÁLCULO DO DINHEIRO DISPONÍVEL (APENAS DIA ATUAL) =====
        hoje = timezone.localtime().date()
        
        # Buscar dados do dashboard financeiro HOJE
        checkouts_hoje = Checkout.objects.filter(
            status='aprovado',
            created_at__date=hoje
        )
        
        # VALOR INICIAL (mesmo valor fixo do dashboard)
        valor_inicial = Decimal('50.00')  # Mesmo valor usado no dashboard
        
        # DINHEIRO recebido HOJE 
        dinheiro_recebido_hoje = checkouts_hoje.filter(
            payment_method='dinheiro'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

        # SANGRIAS já feitas HOJE
        sangrias_hoje = Sangria.objects.filter(
            created_at__date=hoje
        ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

        # VALOR DISPONÍVEL PARA SANGRIA = VALOR INICIAL + DINHEIRO - SANGRIAS HOJE
        dinheiro_disponivel = valor_inicial + dinheiro_recebido_hoje - sangrias_hoje
        dinheiro_disponivel_formatado = f"R$ {dinheiro_disponivel:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        context.update({
            'sangrias': sangrias,
            'data_inicio': data_inicio.strftime('%Y-%m-%d'),
            'data_fim': data_fim.strftime('%Y-%m-%d'),
            'total_periodo': total_formatado,  # Total do período filtrado
            'dinheiro_disponivel': dinheiro_disponivel,  # Disponível hoje
            'dinheiro_disponivel_formatado': dinheiro_disponivel_formatado,
        })
        
        return context
    

@method_decorator(csrf_exempt, name='dispatch')
class CriarSangriaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para criar nova sangria via AJAX
    """
    permission_required = 'financials.can_add_sangria'
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Pegar e validar o valor
            valor_str = data.get('valor', '').replace('R$', '').strip()
            valor_str = valor_str.replace('.', '').replace(',', '.')
            
            if not valor_str:
                return JsonResponse({
                    'success': False,
                    'message': 'Valor é obrigatório'
                }, status=400)
            
            try:
                valor = Decimal(valor_str)
                if valor <= 0:
                    return JsonResponse({
                        'success': False,
                        'message': 'Valor deve ser maior que zero'
                    }, status=400)
            except (InvalidOperation, ValueError):
                return JsonResponse({
                    'success': False,
                    'message': 'Valor inválido'
                }, status=400)
            
            # Criar sangria
            sangria = Sangria.objects.create(
                valor=valor,
                observacao=data.get('observacao', ''),
                usuario=request.user
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Sangria registrada com sucesso',
                'sangria': {
                    'id': sangria.id,
                    'valor': sangria.valor_formatado,
                    'observacao': sangria.observacao,
                    'usuario': sangria.usuario.get_full_name() or sangria.usuario.username,
                    'data': sangria.created_at.strftime('%d/%m/%Y %H:%M')
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Dados JSON inválidos'
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'Erro interno do servidor'
            }, status=500)


class ListarSangriasView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para listar sangrias com filtros via AJAX
    """
    permission_required = 'financials.can_view_sangria'
    
    def get(self, request):
        try:
            # Pegar filtros
            data_inicio = request.GET.get('data_inicio')
            data_fim = request.GET.get('data_fim')
            
            # Query base
            sangrias = Sangria.objects.select_related('usuario')
            
            # Aplicar filtros de data
            if data_inicio:
                try:
                    data_inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
                    sangrias = sangrias.filter(created_at__date__gte=data_inicio)
                except ValueError:
                    pass
            
            if data_fim:
                try:
                    data_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
                    sangrias = sangrias.filter(created_at__date__lte=data_fim)
                except ValueError:
                    pass
            
            # Limitar resultados e ordenar
            sangrias = sangrias.order_by('-created_at')[:100]
            
            # Serializar dados
            sangrias_data = []
            for sangria in sangrias:
                sangrias_data.append({
                    'id': sangria.id,
                    'valor': sangria.valor_formatado,
                    'observacao': sangria.observacao or '',
                    'usuario': sangria.usuario.get_full_name() or sangria.usuario.username,
                    'data': sangria.created_at.strftime('%d/%m/%Y %H:%M')
                })
            
            # Calcular totais
            total = sangrias.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
            total_formatado = f"R$ {total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            return JsonResponse({
                'success': True,
                'sangrias': sangrias_data,
                'total': total_formatado,
                'count': len(sangrias_data)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'Erro ao carregar sangrias'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class ExcluirSangriaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para excluir sangria via AJAX
    """
    permission_required = 'financials.can_add_sangria'
    
    def delete(self, request, sangria_id):
        try:
            sangria = Sangria.objects.get(id=sangria_id)
            
            # Verificar se é superusuário
            if not request.user.is_superuser:
                return JsonResponse({
                    'success': False,
                    'message': 'Acesso negado. Apenas superusuários podem excluir sangrias.'
                }, status=403)
            
            # Guardar dados para resposta antes de deletar
            valor_formatado = sangria.valor_formatado
            
            # Excluir sangria
            sangria.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Sangria de {valor_formatado} excluída com sucesso!'
            })
            
        except Sangria.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Sangria não encontrada'
            }, status=404)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': 'Erro interno do servidor'
            }, status=500)