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
from .models import Sangria, FechamentoCaixaDiario, CaixaAdm, DespesaMalote, CaixaAdmTransferencia, AjusteFechamentoCaixaDiario
from django.views import View
from config.models import ConfigTrocoInicial, SystemConfig
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
            processed_at__date__gte=start_date,
            processed_at__date__lte=end_date,
        ).exclude(
            comanda__status__in=['cancelada', 'cortesia']
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
        checkouts_list = checkouts.order_by('-processed_at', '-id')
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
                'data': checkout.processed_at or checkout.created_at,
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
            processed_at__date=timezone.localtime().date(),
        ).exclude(comanda__status__in=['cancelada', 'cortesia'])

        yesterday = timezone.localtime().date() - timedelta(days=1)
        yesterday_stats = Checkout.objects.filter(
            status='aprovado',
            processed_at__date=yesterday,
        ).exclude(comanda__status__in=['cancelada', 'cortesia'])
        
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
                    'data': timezone.localtime(sangria.created_at).strftime('%d/%m/%Y %H:%M')
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
                    'data': timezone.localtime(sangria.created_at).strftime('%d/%m/%Y %H:%M')
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

        # Checkouts aprovados do dia — usa processed_at (data do pagamento) como referência
        # para que cancelamentos posteriores não alterem retroativamente o total do dia.
        checkouts = Checkout.objects.filter(
            status='aprovado',
            processed_at__date=selected_date,
        ).exclude(comanda__status__in=['cancelada', 'cortesia'])
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
            processed_at__date=date,
        ).exclude(comanda__status__in=['cancelada', 'cortesia'])
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

        # Pré-carrega despesas por data para os dias abertos
        datas_abertas_set = set(datas_abertas)
        malotes_abertos = (
            CaixaAdm.objects
            .filter(fechamento__data__in=datas_abertas_set)
            .prefetch_related('despesas', 'despesas__registrado_por')
            .select_related('fechamento')
        )
        despesas_por_data = {}
        for malote in malotes_abertos:
            despesas_por_data[malote.fechamento.data] = list(malote.despesas.all())

        dias_abertos = []
        for data in datas_abertas:
            extrato = self._calcular_extrato(data)
            dias_abertos.append({
                'data': data,
                'data_fmt': data.strftime('%d/%m/%Y'),
                'data_iso': data.strftime('%Y-%m-%d'),
                'eh_hoje': data == today,
                'extrato': extrato,
                'despesas': despesas_por_data.get(data, []),
            })

        historico = (
            FechamentoCaixaDiario.objects
            .select_related('fechado_por', 'malote')
            .prefetch_related('malote__despesas', 'malote__despesas__registrado_por')
            .order_by('-data')[:30]
        )

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
        ).exclude(
            comanda__status__in=['cancelada', 'cortesia'],
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

        def _comissao(valor):
            return (valor * comissao_pct / Decimal('100')).quantize(Decimal('0.01'))

        total_dinheiro = _soma('dinheiro')
        total_debito   = _soma('cartao_debito')
        total_credito  = _soma('cartao_credito')
        total_pix      = _soma('pix')

        context.update({
            'start_date':          start_date.strftime('%Y-%m-%d'),
            'end_date':            end_date.strftime('%Y-%m-%d'),
            'start_date_fmt':      start_date.strftime('%d/%m/%Y'),
            'end_date_fmt':        end_date.strftime('%d/%m/%Y'),
            'comissao_pct':        comissao_pct,
            'total_vendas':        total_vendas,
            'total_comandas':      total_comandas,
            'valor_comissao':      valor_comissao,
            'total_dinheiro':      total_dinheiro,
            'total_debito':        total_debito,
            'total_credito':       total_credito,
            'total_pix':           total_pix,
            'comissao_dinheiro':   _comissao(total_dinheiro),
            'comissao_debito':     _comissao(total_debito),
            'comissao_credito':    _comissao(total_credito),
            'comissao_pix':        _comissao(total_pix),
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
            'enviado_em': timezone.localtime(malote.enviado_em).strftime('%d/%m/%Y %H:%M'),
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
        total_transferencias = CaixaAdmTransferencia.objects.aggregate(
            total=Sum('valor')
        )['total'] or Decimal('0.00')

        context['total_em_caixa'] = (concluidos.aggregate(
            total=Sum('fechamento__total_final')
        )['total'] or 0) - total_despesas_concluidos - total_transferencias
        context['total_em_caixa_transferencias'] = total_transferencias

        from banks.models import Bank
        context['banks'] = Bank.objects.order_by('nome')
        context['transferencias_recentes'] = CaixaAdmTransferencia.objects.select_related(
            'banco_destino', 'criado_por'
        )[:10]
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
            'registrado_em': timezone.localtime(despesa.registrado_em).strftime('%d/%m/%Y %H:%M'),
        })


class RegistrarDespesaFechamentoView(LoginRequiredMixin, View):
    """
    POST: registra uma despesa em um FechamentoCaixaDiario.
    Auto-cria o CaixaAdm (malote) se ainda não existir.
    """
    login_url = reverse_lazy('accounts:login')

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404
        fechamento = get_object_or_404(FechamentoCaixaDiario, pk=pk)
        valor_raw = request.POST.get('valor', '').replace(',', '.').strip()
        descricao = request.POST.get('descricao', '').strip()
        comprovante = request.FILES.get('comprovante')

        if not valor_raw or not descricao:
            return JsonResponse({'ok': False, 'error': 'Campos obrigatórios faltando.'}, status=400)

        try:
            valor = Decimal(valor_raw)
            if valor <= 0:
                raise ValueError
        except Exception:
            return JsonResponse({'ok': False, 'error': 'Valor inválido.'}, status=400)

        malote, _ = CaixaAdm.objects.get_or_create(
            fechamento=fechamento,
            defaults={'enviado_por': request.user},
        )

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
            'registrado_em': timezone.localtime(despesa.registrado_em).strftime('%d/%m/%Y %H:%M'),
        })


class RegistrarDespesaDiaView(LoginRequiredMixin, View):
    """
    POST: registra uma despesa via data_iso (para cards de dia aberto).
    Cria ou atualiza o FechamentoCaixaDiario stub e auto-cria o CaixaAdm.
    """
    login_url = reverse_lazy('accounts:login')

    def post(self, request):
        from datetime import datetime as dt_cls
        data_iso = request.POST.get('data_iso', '').strip()
        valor_raw = request.POST.get('valor', '').replace(',', '.').strip()
        descricao = request.POST.get('descricao', '').strip()
        comprovante = request.FILES.get('comprovante')

        if not data_iso or not valor_raw or not descricao:
            return JsonResponse({'ok': False, 'error': 'Campos obrigatórios faltando.'}, status=400)

        try:
            data = dt_cls.strptime(data_iso, '%Y-%m-%d').date()
        except ValueError:
            return JsonResponse({'ok': False, 'error': 'Data inválida.'}, status=400)

        try:
            valor = Decimal(valor_raw)
            if valor <= 0:
                raise ValueError
        except Exception:
            return JsonResponse({'ok': False, 'error': 'Valor inválido.'}, status=400)

        # Obtém o fechamento existente; se não existir, cria um stub com valores zerados
        fechamento, _ = FechamentoCaixaDiario.objects.get_or_create(
            data=data,
            defaults={'fechado_por': request.user},
        )

        malote, _ = CaixaAdm.objects.get_or_create(
            fechamento=fechamento,
            defaults={'enviado_por': request.user},
        )

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
            'registrado_em': timezone.localtime(despesa.registrado_em).strftime('%d/%m/%Y %H:%M'),
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
            'concluido_em': timezone.localtime(malote.concluido_em).strftime('%d/%m/%Y %H:%M'),
            'concluido_por': malote.concluido_por.get_full_name() or malote.concluido_por.username,
        })


@method_decorator(csrf_exempt, name='dispatch')
class TransferirCaixaAdmParaBancoView(LoginRequiredMixin, View):
    """
    POST: registra uma transferência do Caixa ADM para um banco.
    Cria um BankTransaction de depósito no banco destino.
    """
    login_url = reverse_lazy('accounts:login')

    def post(self, request):
        from banks.models import Bank, BankTransaction
        from django.shortcuts import get_object_or_404

        banco_id  = request.POST.get('banco_id', '').strip()
        valor_raw = request.POST.get('valor', '').replace(',', '.').strip()
        metodo    = request.POST.get('metodo_pagamento', 'dinheiro').strip()
        bandeira  = request.POST.get('bandeira', '').strip()
        observacao = request.POST.get('observacao', '').strip()
        data_caixa_raw = request.POST.get('data_caixa', '').strip()

        if not banco_id:
            return JsonResponse({'ok': False, 'error': 'Selecione um banco destino.'}, status=400)
        if not valor_raw:
            return JsonResponse({'ok': False, 'error': 'Informe o valor.'}, status=400)
        if not metodo:
            return JsonResponse({'ok': False, 'error': 'Selecione o método de pagamento.'}, status=400)

        try:
            valor = Decimal(valor_raw)
            if valor <= 0:
                raise ValueError
        except Exception:
            return JsonResponse({'ok': False, 'error': 'Valor inválido.'}, status=400)

        # data_caixa: vem como DD/MM/YYYY do template
        data_caixa = None
        if data_caixa_raw:
            from datetime import datetime, timedelta
            try:
                data_caixa = datetime.strptime(data_caixa_raw, '%d/%m/%Y').date()
            except ValueError:
                try:
                    data_caixa = datetime.strptime(data_caixa_raw, '%Y-%m-%d').date()
                except ValueError:
                    pass

        metodos_validos = {'dinheiro', 'debito', 'credito', 'pix'}
        if metodo not in metodos_validos:
            metodo = 'dinheiro'

        # Calcula data prevista de liquidação com base na pinpad ativa
        from pinpads.models import Pinpad
        from datetime import date as date_type, timedelta
        from django.utils import timezone

        pinpad = Pinpad.objects.filter(is_active=True).first()
        data_base = data_caixa or date_type.today()

        # Busca a taxa vigente no momento da criação e grava no registro
        taxa_aplicada = Decimal('0')
        if pinpad and metodo in ('credito', 'debito'):
            from pinpads.models import BandeiraPinpad
            bandeira_obj = BandeiraPinpad.objects.filter(
                pinpad=pinpad,
                nome__iexact=bandeira,
            ).first() if bandeira else None
            if bandeira_obj:
                if metodo == 'credito':
                    taxa_aplicada = bandeira_obj.taxa_credito or Decimal('0')
                else:
                    taxa_aplicada = bandeira_obj.taxa_debito or Decimal('0')

        if pinpad:
            dias_map = {
                'credito': pinpad.dias_credito,
                'debito':  pinpad.dias_debito,
                'pix':     pinpad.dias_pix,
                'dinheiro': 0,
            }
            dias = dias_map.get(metodo, 0)
        else:
            dias = 0

        data_prevista_liquidacao = data_base + timedelta(days=dias)

        # Data da BankTransaction = data de liquidação (futura se dias > 0)
        import datetime as _dt
        data_tx = timezone.make_aware(
            _dt.datetime.combine(data_prevista_liquidacao, _dt.time(23, 59))
        )

        banco = get_object_or_404(Bank, pk=banco_id)

        descricao = f"Caixa {data_caixa_raw} — {dict(CaixaAdmTransferencia.METODO_CHOICES).get(metodo, metodo)}"
        if bandeira:
            descricao += f" ({bandeira})"

        BankTransaction.objects.create(
            bank=banco,
            tipo='deposito',
            descricao=descricao,
            valor=valor,
            is_entrada=True,
            data=data_tx,
            observacao=observacao,
            metodo_pagamento=metodo,
            bandeira=bandeira,
            criado_por=request.user,
        )

        CaixaAdmTransferencia.objects.create(
            banco_destino=banco,
            valor=valor,
            metodo_pagamento=metodo,
            bandeira=bandeira,
            taxa_aplicada=taxa_aplicada,
            data_caixa=data_caixa,
            data_prevista_liquidacao=data_prevista_liquidacao,
            descricao=descricao,
            observacao=observacao,
            criado_por=request.user,
        )

        return JsonResponse({
            'ok': True,
            'banco': banco.nome,
            'valor': str(valor),
        })


class ConciliarTransferenciaView(LoginRequiredMixin, View):
    """
    POST: marca uma CaixaAdmTransferencia como conciliada.
    Aceita valor_parcial no body JSON para conciliação parcial — nesse caso
    divide o registro: parte conciliada agora, resto fica pendente.
    """
    login_url = reverse_lazy('accounts:login')

    def post(self, request, pk):
        import json
        from banks.models import BankTransaction
        from django.utils import timezone
        from django.shortcuts import get_object_or_404
        from decimal import Decimal, InvalidOperation

        transferencia = get_object_or_404(CaixaAdmTransferencia, pk=pk)

        if transferencia.conciliado:
            return JsonResponse({'ok': False, 'error': 'Já conciliada.'}, status=400)

        agora = timezone.now()

        # Lê valor_parcial e observacao do body (opcionais)
        valor_parcial = None
        observacao_nova = ''
        try:
            body = json.loads(request.body or '{}')
            raw = body.get('valor_parcial')
            if raw is not None:
                valor_parcial = Decimal(str(raw)).quantize(Decimal('0.01'))
            observacao_nova = str(body.get('observacao', '')).strip()
        except (json.JSONDecodeError, InvalidOperation):
            pass

        valor_original = transferencia.valor

        if valor_parcial is not None and valor_parcial != valor_original:
            if valor_parcial <= 0 or valor_parcial >= valor_original:
                return JsonResponse({'ok': False, 'error': 'Valor parcial inválido.'}, status=400)

            resto = valor_original - valor_parcial

            # 1. Ajusta a BankTransaction existente para o valor parcial
            update_fields_bt = dict(data=agora, valor=valor_parcial)
            if observacao_nova:
                update_fields_bt['observacao'] = observacao_nova
            BankTransaction.objects.filter(
                bank=transferencia.banco_destino,
                is_entrada=True,
                valor=valor_original,
                descricao=transferencia.descricao,
            ).update(**update_fields_bt)

            # 2. Cria nova BankTransaction pendente para o restante
            BankTransaction.objects.create(
                bank=transferencia.banco_destino,
                tipo='deposito',
                descricao=transferencia.descricao,
                valor=resto,
                is_entrada=True,
                data=agora,
                metodo_pagamento=transferencia.metodo_pagamento,
                bandeira=transferencia.bandeira,
                criado_por=request.user,
            )

            # 3. Concilia a transferência original com o valor parcial
            transferencia.valor = valor_parcial
            transferencia.conciliado = True
            transferencia.conciliado_em = agora
            transferencia.conciliado_por = request.user
            if observacao_nova:
                transferencia.observacao = observacao_nova
            transferencia.save(update_fields=[
                'valor', 'conciliado', 'conciliado_em', 'conciliado_por', 'observacao'
            ])

            # 4. Cria nova CaixaAdmTransferencia pendente para o restante
            CaixaAdmTransferencia.objects.create(
                banco_destino=transferencia.banco_destino,
                valor=resto,
                metodo_pagamento=transferencia.metodo_pagamento,
                bandeira=transferencia.bandeira,
                taxa_aplicada=transferencia.taxa_aplicada,
                data_caixa=transferencia.data_caixa,
                data_prevista_liquidacao=transferencia.data_prevista_liquidacao,
                descricao=transferencia.descricao,
                observacao=transferencia.observacao,
                criado_por=request.user,
            )

        else:
            # Conciliação total
            update_fields_bt = dict(data=agora)
            if observacao_nova:
                update_fields_bt['observacao'] = observacao_nova
            BankTransaction.objects.filter(
                bank=transferencia.banco_destino,
                is_entrada=True,
                valor=valor_original,
                descricao=transferencia.descricao,
            ).update(**update_fields_bt)

            transferencia.conciliado = True
            transferencia.conciliado_em = agora
            transferencia.conciliado_por = request.user
            if observacao_nova:
                transferencia.observacao = observacao_nova
            transferencia.save(update_fields=['conciliado', 'conciliado_em', 'conciliado_por', 'observacao'])

        return JsonResponse({'ok': True})


class CancelarFechamentoView(LoginRequiredMixin, View):
    """
    POST: cancela um FechamentoCaixaDiario pendente (sem transferência conciliada).
    O card some do grid e aparece na listagem de transferências como "Cancelado".
    """
    login_url = reverse_lazy('accounts:login')

    def post(self, request, pk):
        from django.shortcuts import get_object_or_404

        fechamento = get_object_or_404(FechamentoCaixaDiario, pk=pk)

        if fechamento.cancelada:
            return JsonResponse({'ok': False, 'error': 'Já cancelado.'}, status=400)

        agora = timezone.now()
        fechamento.cancelada = True
        fechamento.cancelada_em = agora
        fechamento.cancelada_por = request.user
        fechamento.save(update_fields=['cancelada', 'cancelada_em', 'cancelada_por'])

        return JsonResponse({'ok': True})


class CancelarTransferenciaView(LoginRequiredMixin, View):
    """
    POST: cancela uma CaixaAdmTransferencia pendente (não conciliada).
    Remove a BankTransaction correspondente e mantém o registro visível na listagem.
    """
    login_url = reverse_lazy('accounts:login')

    def post(self, request, pk):
        from banks.models import BankTransaction
        from django.shortcuts import get_object_or_404

        transferencia = get_object_or_404(CaixaAdmTransferencia, pk=pk)

        if transferencia.cancelada:
            return JsonResponse({'ok': False, 'error': 'Já cancelada.'}, status=400)
        if transferencia.conciliado:
            return JsonResponse({'ok': False, 'error': 'Transferência já conciliada, não pode ser cancelada.'}, status=400)

        # Remove a BankTransaction pendente associada
        BankTransaction.objects.filter(
            bank=transferencia.banco_destino,
            is_entrada=True,
            valor=transferencia.valor,
            descricao=transferencia.descricao,
        ).delete()

        agora = timezone.now()
        transferencia.cancelada = True
        transferencia.cancelada_em = agora
        transferencia.cancelada_por = request.user
        transferencia.save(update_fields=['cancelada', 'cancelada_em', 'cancelada_por'])

        return JsonResponse({'ok': True})


class AtualizarFechamentoCaixaView(LoginRequiredMixin, View):
    """
    POST: atualiza os valores de um FechamentoCaixaDiario e registra um
    AjusteFechamentoCaixaDiario como auditoria da alteração.
    """
    login_url = reverse_lazy('accounts:login')

    def post(self, request):
        from django.shortcuts import get_object_or_404

        fechamento_id = request.POST.get('fechamento_id', '').strip()
        observacao = request.POST.get('observacao', '').strip()

        if not fechamento_id:
            return JsonResponse({'ok': False, 'error': 'Fechamento não informado.'}, status=400)

        def _dec(key):
            raw = request.POST.get(key, '0').replace(',', '.').strip()
            try:
                v = Decimal(raw)
                return v if v >= 0 else Decimal('0.00')
            except Exception:
                return Decimal('0.00')

        fechamento = get_object_or_404(FechamentoCaixaDiario, pk=fechamento_id)

        # Captura valores ANTES do ajuste
        prev_valor_inicial  = fechamento.valor_inicial
        prev_total_dinheiro = fechamento.total_dinheiro
        prev_total_debito   = fechamento.total_debito
        prev_total_credito  = fechamento.total_credito
        prev_total_pix      = fechamento.total_pix
        prev_total_sangrias = fechamento.total_sangrias
        prev_total_final    = fechamento.total_final

        valor_inicial  = _dec('valor_inicial')
        total_dinheiro = _dec('total_dinheiro')
        total_debito   = _dec('total_debito')
        total_credito  = _dec('total_credito')
        total_pix      = _dec('total_pix')
        total_sangrias = _dec('total_sangrias')
        total_entradas = total_dinheiro + total_debito + total_credito + total_pix
        total_final    = total_entradas - total_sangrias

        fechamento.valor_inicial  = valor_inicial
        fechamento.total_dinheiro = total_dinheiro
        fechamento.total_debito   = total_debito
        fechamento.total_credito  = total_credito
        fechamento.total_pix      = total_pix
        fechamento.total_sangrias = total_sangrias
        fechamento.total_entradas = total_entradas
        fechamento.total_final    = total_final
        fechamento.save()

        AjusteFechamentoCaixaDiario.objects.create(
            fechamento=fechamento,
            ajustado_por=request.user,
            # Antes
            prev_valor_inicial=prev_valor_inicial,
            prev_total_dinheiro=prev_total_dinheiro,
            prev_total_debito=prev_total_debito,
            prev_total_credito=prev_total_credito,
            prev_total_pix=prev_total_pix,
            prev_total_sangrias=prev_total_sangrias,
            prev_total_final=prev_total_final,
            # Depois
            valor_inicial=valor_inicial,
            total_dinheiro=total_dinheiro,
            total_debito=total_debito,
            total_credito=total_credito,
            total_pix=total_pix,
            total_sangrias=total_sangrias,
            total_entradas=total_entradas,
            total_final=total_final,
            observacao=observacao,
        )

        return JsonResponse({
            'ok': True,
            'total_final': str(total_final),
            'total_entradas': str(total_entradas),
        })


class ConferenciaCaixaView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Exibe todos os FechamentoCaixaDiario como cards — assim que o caixa é
    fechado, aparece automaticamente aqui para conferência e transferência.
    """
    permission_required = 'financials.view_caixaadm'
    template_name = 'financials/conferencia_caixa.html'
    login_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        fechamentos = (
            FechamentoCaixaDiario.objects
            .select_related('fechado_por', 'malote', 'malote__concluido_por')
            .prefetch_related('malote__despesas', 'ajustes', 'ajustes__ajustado_por')
            .order_by('-data')
        )
        total_geral = fechamentos.aggregate(
            total=Sum('total_final')
        )['total'] or Decimal('0.00')
        total_dinheiro = fechamentos.aggregate(
            total=Sum('total_dinheiro')
        )['total'] or Decimal('0.00')
        total_transferencias = CaixaAdmTransferencia.objects.filter(
            cancelada=False
        ).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

        from banks.models import Bank
        from pinpads.models import Pinpad

        # Monta lookup de transferências por (data_caixa, metodo) — apenas não canceladas
        transf_rows = (
            CaixaAdmTransferencia.objects
            .filter(cancelada=False)
            .values('data_caixa', 'metodo_pagamento')
            .annotate(total=Sum('valor'))
        )
        transf_lookup = {
            (r['data_caixa'], r['metodo_pagamento']): r['total'] or Decimal('0')
            for r in transf_rows
        }

        # Anota cada fechamento com restantes por método
        fechamentos_list = list(fechamentos)
        for f in fechamentos_list:
            t_din = transf_lookup.get((f.data, 'dinheiro'), Decimal('0'))
            t_deb = transf_lookup.get((f.data, 'debito'),   Decimal('0'))
            t_cre = transf_lookup.get((f.data, 'credito'),  Decimal('0'))
            t_pix = transf_lookup.get((f.data, 'pix'),      Decimal('0'))
            f.transf_dinheiro = t_din
            f.transf_debito   = t_deb
            f.transf_credito  = t_cre
            f.transf_pix      = t_pix
            f.rest_dinheiro   = max(f.total_dinheiro - t_din, Decimal('0'))
            f.rest_debito     = max(f.total_debito   - t_deb, Decimal('0'))
            f.rest_credito    = max(f.total_credito  - t_cre, Decimal('0'))
            f.rest_pix        = max(f.total_pix      - t_pix, Decimal('0'))
            f.total_transferido = t_din + t_deb + t_cre + t_pix
            f.total_restante    = max(f.total_final - f.total_transferido, Decimal('0'))

        pinpad_ativo = Pinpad.objects.filter(is_active=True).prefetch_related('bandeiras').first()
        context['fechamentos'] = fechamentos_list
        context['total_geral'] = total_geral
        context['total_dinheiro'] = total_dinheiro
        context['total_transferencias'] = total_transferencias
        context['total_disponivel'] = max(total_geral - total_transferencias, Decimal('0.00'))
        context['banks'] = Bank.objects.order_by('nome')
        context['bandeiras_pinpad'] = list(pinpad_ativo.bandeiras.values('nome')) if pinpad_ativo else []
        context['metodos_pagamento'] = CaixaAdmTransferencia.METODO_CHOICES
        context['transferencias_recentes'] = CaixaAdmTransferencia.objects.select_related(
            'banco_destino', 'criado_por', 'cancelada_por'
        ).order_by('cancelada', '-criado_em')[:30]
        context['fechamentos_cancelados'] = FechamentoCaixaDiario.objects.filter(
            cancelada=True
        ).select_related('cancelada_por').order_by('-cancelada_em')[:30]
        return context
