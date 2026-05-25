from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from checkouts.models import Checkout, CheckoutPayment
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json
from .models import Sangria, FechamentoCaixaDiario, CaixaAdm, DespesaMalote
from django.views import View
from config.models import ConfigTrocoInicial
from products.models import Product


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
        
        # Filtrar checkouts por período (usa data de fechamento da comanda)
        checkouts = Checkout.objects.filter(
            status='aprovado',
            comanda__updated_at__date__gte=start_date,
            comanda__updated_at__date__lte=end_date
        ).select_related('comanda')
        
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
        # Lógica correta e consistente com o Relatório de Impressão:
        #   - Checkouts não-parciais: usa Checkout.payment_method (reflete alterações feitas pelo operador)
        #   - Checkouts parciais: usa CheckoutPayment para separar cada método
        #   - Fallback legado: checkouts antigos sem CheckoutPayment usam Checkout diretamente

        parcial_ids = list(checkouts.filter(payment_method='parcial').values_list('id', flat=True))

        def _sum_method(method):
            # 1. Checkouts simples com o método (não-parcial e não-legado sem payment records)
            simples = checkouts.exclude(payment_method='parcial').filter(
                payment_method=method
            ).aggregate(total=Sum('total'), count=Count('id'))
            # 2. Porção do método dentro de checkouts parciais (via CheckoutPayment)
            parcial = (CheckoutPayment.objects
                       .filter(checkout_id__in=parcial_ids, payment_method=method)
                       .aggregate(total=Sum('amount'), count=Count('id')))
            total = (simples['total'] or Decimal('0.00')) + (parcial['total'] or Decimal('0.00'))
            count = (simples['count'] or 0) + (parcial['count'] or 0)
            return total, count

        payment_stats = {}

        # Sangria (retiradas do caixa)
        payment_stats['sangria'] = {
            'total': total_sangrias,
            'count': sangrias_periodo['count'] or 0,
            'label': 'Sangria',
            'icon': '💸',
            'color': 'red'
        }

        # Valor inicial vindo das configurações do sistema
        valor_inicial = ConfigTrocoInicial.get_settings().troco_inicial
        payment_stats['valor_inicial'] = {
            'total': valor_inicial,
            'count': 1,
            'label': 'Valor Inicial',
            'icon': '💰',
            'color': 'yellow'
        }

        d_total, d_count = _sum_method('dinheiro')
        payment_stats['dinheiro'] = {'total': d_total, 'count': d_count, 'label': 'Dinheiro', 'icon': '💵', 'color': 'green'}

        cr_total, cr_count = _sum_method('cartao_credito')
        payment_stats['cartao_credito'] = {'total': cr_total, 'count': cr_count, 'label': 'Cartão de Crédito', 'icon': '💳', 'color': 'blue'}

        db_total, db_count = _sum_method('cartao_debito')
        payment_stats['cartao_debito'] = {'total': db_total, 'count': db_count, 'label': 'Cartão de Débito', 'icon': '💳', 'color': 'purple'}

        px_total, px_count = _sum_method('pix')
        payment_stats['pix'] = {'total': px_total, 'count': px_count, 'label': 'PIX', 'icon': '📱', 'color': 'orange'}

        # Total geral
        total_receita = (checkouts.aggregate(total=Sum('total'))['total'] or Decimal('0.00')) - total_sangrias
        total_comandas = checkouts.count()
        
        # ===== LISTA COMBINADA DE COMANDAS E SANGRIAS =====
        checkouts_list = checkouts.order_by('-comanda__updated_at')
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
                'id': checkout.comanda.id,
                'code': checkout.comanda.numero,
                'cliente': checkout.comanda.cliente_nome or f'Comanda #{checkout.comanda.numero}',
                'pagamento': (
                    ' + '.join(
                        f'{p.get_payment_method_display()} R${p.amount:.2f}'
                        for p in checkout.payments.all()
                    ) if checkout.payments.exists() else checkout.get_payment_method_display()
                ),
                'valor': checkout.total,
                'data': checkout.comanda.updated_at,
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
            comanda__updated_at__date=timezone.localtime().date()
        )

        yesterday = timezone.localtime().date() - timedelta(days=1)
        yesterday_stats = Checkout.objects.filter(
            status='aprovado',
            comanda__updated_at__date=yesterday
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
    permission_required = 'financials.add_sangria'
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
            comanda__updated_at__date=hoje
        )
        
        # VALOR INICIAL (mesmo valor fixo do dashboard)
        valor_inicial = ConfigTrocoInicial.get_settings().troco_inicial
        
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
    permission_required = 'financials.view_sangria'
    
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
            
            # Verificar permissão de exclusão
            if not request.user.has_perm('financials.delete_sangria'):
                return JsonResponse({
                    'success': False,
                    'message': 'Sem permissão para excluir sangrias.'
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

class ExtratoView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Extrato do caixa por período — resumo por forma de pagamento para impressão.
    """
    permission_required = 'financials.view_financial'
    template_name = 'reports/report_list.html'
    login_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        date_str = self.request.GET.get('date')

        if not date_str:
            selected_date = timezone.localtime().date()
        else:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Checkouts aprovados do dia (filtra por data de fechamento da comanda)
        checkouts = Checkout.objects.filter(
            status='aprovado',
            comanda__status='fechada',
            comanda__updated_at__date=selected_date,
        )
        parcial_ids = list(checkouts.filter(payment_method='parcial').values_list('id', flat=True))

        def _soma(method):
            simples = (checkouts.exclude(payment_method='parcial')
                       .filter(payment_method=method)
                       .aggregate(t=Sum('total'))['t'] or Decimal('0.00'))
            parcial = (CheckoutPayment.objects
                       .filter(checkout_id__in=parcial_ids, payment_method=method)
                       .aggregate(t=Sum('amount'))['t'] or Decimal('0.00'))
            return simples + parcial

        total_dinheiro  = _soma('dinheiro')
        total_debito    = _soma('cartao_debito')
        total_credito   = _soma('cartao_credito')
        total_pix       = _soma('pix')

        sangrias = Sangria.objects.filter(
            created_at__date=selected_date,
        )
        total_sangrias = sangrias.aggregate(t=Sum('valor'))['t'] or Decimal('0.00')

        valor_inicial = ConfigTrocoInicial.get_settings().troco_inicial

        total_entradas = total_dinheiro + total_debito + total_credito + total_pix
        total_final    = total_entradas - total_sangrias

        from orders.models import Comanda
        canceladas_qs = Comanda.objects.filter(status='cancelada', updated_at__date=selected_date)
        cortesias_qs  = Comanda.objects.filter(status='cortesia',  updated_at__date=selected_date)
        total_canceladas = canceladas_qs.aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        qtd_canceladas   = canceladas_qs.count()
        total_cortesias  = cortesias_qs.aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        qtd_cortesias    = cortesias_qs.count()

        context.update({
            'selected_date':     selected_date.strftime('%Y-%m-%d'),
            'selected_date_fmt': selected_date.strftime('%d/%m/%Y'),
            'valor_inicial':     valor_inicial,
            'total_dinheiro':    total_dinheiro,
            'total_debito':      total_debito,
            'total_credito':     total_credito,
            'total_pix':         total_pix,
            'total_sangrias':    total_sangrias,
            'total_entradas':    total_entradas,
            'total_final':       total_final,
            'total_comandas':    checkouts.count(),
            'total_canceladas':  total_canceladas,
            'qtd_canceladas':    qtd_canceladas,
            'total_cortesias':   total_cortesias,
            'qtd_cortesias':     qtd_cortesias,
        })
        return context


# ─────────────────────────────────────────────────────────────────────────────
#  FECHAMENTO DIÁRIO DE CAIXA
# ─────────────────────────────────────────────────────────────────────────────

class FechamentoCaixaDiarioView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Tela de fechamento diário: mostra o extrato do dia atual e lista
    os fechamentos anteriores já arquivados.
    """
    permission_required = 'financials.view_financial'
    template_name = 'financials/fechamento_diario.html'
    login_url = reverse_lazy('accounts:login')

    def _calcular_extrato(self, date):
        """Retorna dict com os totais do dia."""
        checkouts = Checkout.objects.filter(
            status='aprovado',
            comanda__status='fechada',
            processed_at__date=date,
        )
        # Mesma lógica do FinancialDashboardView:
        #  - não-parciais: usa Checkout.payment_method (reflete alterações do operador)
        #  - parciais: usa CheckoutPayment para quebrar por método
        parcial_ids = list(checkouts.filter(payment_method='parcial').values_list('id', flat=True))

        def _soma(method):
            simples = (checkouts.exclude(payment_method='parcial')
                       .filter(payment_method=method)
                       .aggregate(t=Sum('total'))['t'] or Decimal('0.00'))
            parcial = (CheckoutPayment.objects
                       .filter(checkout_id__in=parcial_ids, payment_method=method)
                       .aggregate(t=Sum('amount'))['t'] or Decimal('0.00'))
            return simples + parcial

        sangrias_qs = Sangria.objects.filter(created_at__date=date)
        valor_inicial  = ConfigTrocoInicial.get_settings().troco_inicial
        total_dinheiro = _soma('dinheiro')
        total_debito   = _soma('cartao_debito')
        total_credito  = _soma('cartao_credito')
        total_pix      = _soma('pix')
        total_sangrias = sangrias_qs.aggregate(t=Sum('valor'))['t'] or Decimal('0.00')
        total_entradas = total_dinheiro + total_debito + total_credito + total_pix
        total_final    = total_entradas - total_sangrias

        from orders.models import Comanda
        canceladas_qs = Comanda.objects.filter(status='cancelada', updated_at__date=date)
        cortesias_qs  = Comanda.objects.filter(status='cortesia',  updated_at__date=date)
        total_canceladas = canceladas_qs.aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        qtd_canceladas   = canceladas_qs.count()
        total_cortesias  = cortesias_qs.aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        qtd_cortesias    = cortesias_qs.count()

        return {
            'valor_inicial':    valor_inicial,
            'total_dinheiro':   total_dinheiro,
            'total_debito':     total_debito,
            'total_credito':    total_credito,
            'total_pix':        total_pix,
            'total_sangrias':   total_sangrias,
            'total_entradas':   total_entradas,
            'total_final':      total_final,
            'total_comandas':   checkouts.count(),
            'total_canceladas': total_canceladas,
            'qtd_canceladas':   qtd_canceladas,
            'total_cortesias':  total_cortesias,
            'qtd_cortesias':    qtd_cortesias,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localtime().date()
        data_inicio = today - timedelta(days=60)

        # Datas que têm checkouts aprovados nos últimos 60 dias
        datas_com_checkout = set(
            Checkout.objects
            .filter(status='aprovado', processed_at__date__gte=data_inicio)
            .values_list('processed_at__date', flat=True)
            .distinct()
        )

        # Mapa data → fechamento existente
        fechamentos_map = {
            f.data: f
            for f in FechamentoCaixaDiario.objects.filter(data__gte=data_inicio).select_related('fechado_por')
        }

        # Um dia aparece como card aberto se:
        #   - Não tem fechamento E tem checkouts, OU
        #   - Tem fechamento MAS existe algum checkout processado DEPOIS do fechamento
        datas_abertas = []
        for data in sorted(datas_com_checkout, reverse=True):
            if data not in fechamentos_map:
                datas_abertas.append(data)
            else:
                fech = fechamentos_map[data]
                tem_novo = Checkout.objects.filter(
                    status='aprovado',
                    processed_at__date=data,
                    processed_at__gt=fech.updated_at,
                ).exists()
                if tem_novo:
                    datas_abertas.append(data)

        dias_abertos = []
        for data in datas_abertas:
            extrato = self._calcular_extrato(data)
            dias_abertos.append({
                'data': data,
                'data_fmt': data.strftime('%d/%m/%Y'),
                'data_iso': data.strftime('%Y-%m-%d'),
                'eh_hoje': data == today,
                'extrato': extrato,
            })

        historico = FechamentoCaixaDiario.objects.select_related('fechado_por').order_by('-data')[:30]

        # Totais de malotes
        agg_aberto = CaixaAdm.objects.filter(concluido=False).aggregate(
            total=Sum('fechamento__total_final')
        )
        agg_enviado = CaixaAdm.objects.filter(concluido=True).aggregate(
            total=Sum('fechamento__total_final')
        )

        context.update({
            'dias_abertos': dias_abertos,
            'historico': historico,
            'total_malote_aberto': agg_aberto['total'] or Decimal('0.00'),
            'total_malote_enviado': agg_enviado['total'] or Decimal('0.00'),
        })
        return context


class RealizarFechamentoCaixaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST: arquiva o extrato do dia como FechamentoCaixaDiario.
    Se já existe um fechamento para o dia, atualiza.
    """
    permission_required = 'financials.view_financial'
    login_url = reverse_lazy('accounts:login')

    def post(self, request):
        from datetime import date as date_type
        from django.shortcuts import redirect
        from django.contrib import messages as django_messages

        # Aceita data do POST (YYYY-MM-DD), senão usa hoje
        data_str = request.POST.get('data', '').strip()
        try:
            target_date = date_type.fromisoformat(data_str)
        except (ValueError, TypeError):
            target_date = timezone.localtime().date()

        checkouts = Checkout.objects.filter(status='aprovado', comanda__status='fechada', comanda__updated_at__date=target_date)
        parcial_ids = list(checkouts.filter(payment_method='parcial').values_list('id', flat=True))

        def _soma(method):
            simples = (checkouts.exclude(payment_method='parcial')
                       .filter(payment_method=method)
                       .aggregate(t=Sum('total'))['t'] or Decimal('0.00'))
            parcial = (CheckoutPayment.objects
                       .filter(checkout_id__in=parcial_ids, payment_method=method)
                       .aggregate(t=Sum('amount'))['t'] or Decimal('0.00'))
            return simples + parcial

        sangrias_qs = Sangria.objects.filter(created_at__date=target_date)
        valor_inicial  = ConfigTrocoInicial.get_settings().troco_inicial
        total_dinheiro = _soma('dinheiro')
        total_debito   = _soma('cartao_debito')
        total_credito  = _soma('cartao_credito')
        total_pix      = _soma('pix')
        total_sangrias = sangrias_qs.aggregate(t=Sum('valor'))['t'] or Decimal('0.00')
        total_entradas = total_dinheiro + total_debito + total_credito + total_pix
        total_final    = total_entradas - total_sangrias

        observacao = request.POST.get('observacao', '').strip()

        fechamento, created = FechamentoCaixaDiario.objects.update_or_create(
            data=target_date,
            defaults={
                'fechado_por':    request.user,
                'valor_inicial':  valor_inicial,
                'total_dinheiro': total_dinheiro,
                'total_debito':   total_debito,
                'total_credito':  total_credito,
                'total_pix':      total_pix,
                'total_sangrias': total_sangrias,
                'total_entradas': total_entradas,
                'total_final':    total_final,
                'total_comandas': checkouts.count(),
                'observacao':     observacao,
            }
        )

        data_fmt = target_date.strftime('%d/%m/%Y')
        if created:
            django_messages.success(request, f'Caixa do dia {data_fmt} fechado com sucesso!')
        else:
            django_messages.success(request, f'Fechamento do dia {data_fmt} atualizado.')

        return redirect('financials:fechamento_diario')



class ExtratoAbertosAPIView(LoginRequiredMixin, View):
    """
    GET: retorna JSON com extrato de todos os dias abertos (sem fechamento formal).
    Usado pelo polling JS do template fechamento_diario.html.
    """
    login_url = reverse_lazy('accounts:login')

    def get(self, request):
        from datetime import timedelta as _td
        today = timezone.localtime().date()
        data_inicio = today - _td(days=60)

        datas_com_checkout = (
            Checkout.objects
            .filter(status='aprovado', processed_at__date__gte=data_inicio)
            .values_list('processed_at__date', flat=True)
            .distinct()
        )
        # Mapa data → fechamento existente
        fechamentos_map = {
            f.data: f
            for f in FechamentoCaixaDiario.objects.filter(data__gte=data_inicio)
        }

        datas_abertas = []
        for data in sorted(set(datas_com_checkout), reverse=True):
            if data not in fechamentos_map:
                datas_abertas.append(data)
            else:
                fech = fechamentos_map[data]
                tem_novo = Checkout.objects.filter(
                    status='aprovado',
                    processed_at__date=data,
                    processed_at__gt=fech.updated_at,
                ).exists()
                if tem_novo:
                    datas_abertas.append(data)

        # Reutiliza a mesma lógica de _calcular_extrato inline
        from orders.models import Comanda as _Comanda
        dias = []
        for data in datas_abertas:
            checkouts = Checkout.objects.filter(status='aprovado', comanda__status='fechada', processed_at__date=data)
            parcial_ids = list(checkouts.filter(payment_method='parcial').values_list('id', flat=True))

            def _soma(method, _ckts=checkouts, _pids=parcial_ids):
                simples = (_ckts.exclude(payment_method='parcial')
                           .filter(payment_method=method)
                           .aggregate(t=Sum('total'))['t'] or Decimal('0.00'))
                parcial = (CheckoutPayment.objects
                           .filter(checkout_id__in=_pids, payment_method=method)
                           .aggregate(t=Sum('amount'))['t'] or Decimal('0.00'))
                return simples + parcial

            sangrias_qs = Sangria.objects.filter(created_at__date=data)
            valor_inicial  = ConfigTrocoInicial.get_settings().troco_inicial
            total_dinheiro = _soma('dinheiro')
            total_debito   = _soma('cartao_debito')
            total_credito  = _soma('cartao_credito')
            total_pix      = _soma('pix')
            total_sangrias = sangrias_qs.aggregate(t=Sum('valor'))['t'] or Decimal('0.00')
            total_entradas = total_dinheiro + total_debito + total_credito + total_pix
            total_final    = total_entradas - total_sangrias

            canceladas_qs = _Comanda.objects.filter(status='cancelada', updated_at__date=data)
            cortesias_qs  = _Comanda.objects.filter(status='cortesia',  updated_at__date=data)
            qtd_canceladas = canceladas_qs.count()
            qtd_cortesias  = cortesias_qs.count()

            dias.append({
                'data_iso': data.isoformat(),
                'data_fmt': data.strftime('%d/%m/%Y'),
                'eh_hoje': data == today,
                'total_comandas': checkouts.count(),
                'total_final':    str(total_final),
                'total_dinheiro': str(total_dinheiro),
                'total_debito':   str(total_debito),
                'total_credito':  str(total_credito),
                'total_pix':      str(total_pix),
                'total_sangrias': str(total_sangrias),
                'valor_inicial':  str(valor_inicial),
                'qtd_canceladas': qtd_canceladas,
                'qtd_cortesias':  qtd_cortesias,
            })

        return JsonResponse({'dias': dias})

class CommissionView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Tela de configuração e visualização de comissões sobre vendas.
    Permite definir o percentual de comissão e consultar o valor por período.
    """
    permission_required = 'checkouts.view_checkout'
    template_name = 'commissions/commission.html'
    login_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        start_date = self.request.GET.get('start_date')
        end_date   = self.request.GET.get('end_date')
        if not start_date:
            start_date = timezone.localtime().date()
        else:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            except ValueError:
                start_date = timezone.localtime().date()
        if not end_date:
            end_date = timezone.localtime().date()
        else:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                end_date = timezone.localtime().date()

        config = SystemConfig.get_settings()
        comissao_pct = config.comissao_percentual

        checkouts = Checkout.objects.filter(
            status='aprovado',
            comanda__updated_at__date__gte=start_date,
            comanda__updated_at__date__lte=end_date,
        )
        total_vendas   = checkouts.aggregate(t=Sum('total'))['t'] or Decimal('0.00')
        total_comandas = checkouts.count()
        valor_comissao = (total_vendas * comissao_pct / Decimal('100')).quantize(Decimal('0.01'))

        parcial_ids = list(checkouts.filter(payment_method='parcial').values_list('id', flat=True))

        def _soma(method):
            simples = (checkouts.exclude(payment_method='parcial')
                       .filter(payment_method=method)
                       .aggregate(t=Sum('total'))['t'] or Decimal('0.00'))
            parcial_v = (CheckoutPayment.objects
                         .filter(checkout_id__in=parcial_ids, payment_method=method)
                         .aggregate(t=Sum('amount'))['t'] or Decimal('0.00'))
            return simples + parcial_v

        # Products with tax calculation
        produtos_com_imposto = []
        for p in Product.objects.order_by('category', 'name'):
            base_icms = p.price * (p.base_calculo_icms / Decimal('100'))
            icms = (base_icms * (p.aliq_icms / Decimal('100'))).quantize(Decimal('0.01'))
            pis = (p.price * (p.aliq_pis / Decimal('100'))).quantize(Decimal('0.01'))
            cofins = (p.price * (p.aliq_cofins / Decimal('100'))).quantize(Decimal('0.01'))
            total_tax = icms + pis + cofins
            produtos_com_imposto.append({
                'name': p.name,
                'category': p.get_category_display(),
                'price': p.price,
                'icms': icms,
                'pis': pis,
                'cofins': cofins,
                'total_tax': total_tax,
            })

        context.update({
            'start_date':     start_date.strftime('%Y-%m-%d'),
            'end_date':       end_date.strftime('%Y-%m-%d'),
            'start_date_fmt': start_date.strftime('%d/%m/%Y'),
            'end_date_fmt':   end_date.strftime('%d/%m/%Y'),
            'comissao_pct':   comissao_pct,
            'total_vendas':   total_vendas,
            'total_comandas': total_comandas,
            'valor_comissao': valor_comissao,
            'total_dinheiro': _soma('dinheiro'),
            'total_debito':   _soma('cartao_debito'),
            'total_credito':  _soma('cartao_credito'),
            'total_pix':      _soma('pix'),
            'produtos_com_imposto': produtos_com_imposto,
        })
        return context


class SalvarComissaoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST: salva o percentual de comissão em SystemConfig.
    Apenas superusuários ou staff podem alterar.
    """
    permission_required = 'checkouts.view_checkout'
    login_url = reverse_lazy('accounts:login')

    def post(self, request):
        if not request.user.has_perm('config.change_configcomissao'):
            return JsonResponse({'success': False, 'message': 'Sem permissão para alterar a comissão.'}, status=403)
        try:
            data = json.loads(request.body)
            pct_str = str(data.get('percentual', '')).replace(',', '.').strip()
            pct = Decimal(pct_str)
            if pct < 0 or pct > 100:
                return JsonResponse({'success': False, 'message': 'Percentual deve estar entre 0 e 100.'}, status=400)
        except Exception:
            return JsonResponse({'success': False, 'message': 'Valor inválido.'}, status=400)

        config = SystemConfig.get_settings()
        config.comissao_percentual = pct
        config.save()
        return JsonResponse({'success': True, 'message': f'Comissão atualizada para {pct}%.'})


class EnviarMaloteView(LoginRequiredMixin, View):
    """
    POST: cria um registro CaixaAdm (malote) para o fechamento informado.
    Retorna JSON { ok, malote_id, enviado_em }.
    """
    login_url = reverse_lazy('accounts:login')

    def post(self, request):
        from django.shortcuts import get_object_or_404
        fechamento_id = request.POST.get('fechamento_id')
        fechamento = get_object_or_404(FechamentoCaixaDiario, pk=fechamento_id)

        malote, created = CaixaAdm.objects.get_or_create(
            fechamento=fechamento,
            defaults={'enviado_por': request.user},
        )
        return JsonResponse({
            'ok': True,
            'created': created,
            'malote_id': malote.pk,
            'enviado_em': malote.enviado_em.strftime('%d/%m/%Y %H:%M'),
        })


class CaixaAdmView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Lista todos os malotes enviados em cards, para conferência administrativa.
    """
    permission_required = 'financials.view_caixaadm'
    template_name = 'financials/caixa_adm.html'
    login_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = (
            CaixaAdm.objects
            .select_related('fechamento', 'enviado_por', 'concluido_por')
            .prefetch_related('despesas', 'despesas__registrado_por')
            .order_by('-fechamento__data')
        )
        pendentes = qs.filter(concluido=False)
        concluidos = qs.filter(concluido=True)
        context['malotes'] = pendentes
        context['malotes_concluidos'] = concluidos
        context['total_a_receber'] = pendentes.aggregate(
            total=Sum('fechamento__total_final')
        )['total'] or 0
        context['total_em_caixa'] = concluidos.aggregate(
            total=Sum('fechamento__total_final')
        )['total'] or 0
        context['total_a_receber_dinheiro'] = pendentes.aggregate(
            total=Sum('fechamento__total_dinheiro')
        )['total'] or 0

        # Despesas descontadas apenas do dinheiro dos malotes conferidos
        from .models import DespesaMalote
        total_despesas_concluidos = DespesaMalote.objects.filter(
            malote__in=concluidos
        ).aggregate(total=Sum('valor'))['total'] or 0

        total_dinheiro_bruto = concluidos.aggregate(
            total=Sum('fechamento__total_dinheiro')
        )['total'] or 0
        context['total_em_caixa_dinheiro'] = total_dinheiro_bruto - total_despesas_concluidos
        context['total_em_caixa'] = (concluidos.aggregate(
            total=Sum('fechamento__total_final')
        )['total'] or 0) - total_despesas_concluidos
        return context


class RegistrarDespesaMaloteView(LoginRequiredMixin, View):
    """
    POST: registra uma despesa vinculada a um malote.
    Aceita multipart/form-data (pode ter arquivo comprovante).
    """
    login_url = reverse_lazy('accounts:login')

    def post(self, request):
        from django.shortcuts import get_object_or_404
        malote_id = request.POST.get('malote_id')
        valor_raw = request.POST.get('valor', '').replace(',', '.').strip()
        descricao = request.POST.get('descricao', '').strip()
        comprovante = request.FILES.get('comprovante')

        if not malote_id or not valor_raw or not descricao:
            return JsonResponse({'ok': False, 'error': 'Campos obrigatórios faltando.'}, status=400)

        try:
            valor = Decimal(valor_raw)
        except Exception:
            return JsonResponse({'ok': False, 'error': 'Valor inválido.'}, status=400)

        malote = get_object_or_404(CaixaAdm, pk=malote_id)

        despesa = DespesaMalote.objects.create(
            malote=malote,
            valor=valor,
            descricao=descricao,
            comprovante=comprovante,
            registrado_por=request.user,
        )
        return JsonResponse({
            'ok': True,
            'despesa_id': despesa.pk,
            'valor': str(despesa.valor),
            'descricao': despesa.descricao,
            'registrado_em': despesa.registrado_em.strftime('%d/%m/%Y %H:%M'),
        })


class ConcluirMaloteView(LoginRequiredMixin, View):
    """
    POST: marca um malote como concluído/conferido.
    """
    login_url = reverse_lazy('accounts:login')

    def post(self, request):
        from django.shortcuts import get_object_or_404
        malote_id = request.POST.get('malote_id')
        malote = get_object_or_404(CaixaAdm, pk=malote_id)
        if not malote.concluido:
            malote.concluido = True
            malote.concluido_por = request.user
            malote.concluido_em = timezone.now()
            malote.save()
        return JsonResponse({
            'ok': True,
            'concluido_em': malote.concluido_em.strftime('%d/%m/%Y %H:%M'),
            'concluido_por': malote.concluido_por.get_full_name() or malote.concluido_por.username,
        })
