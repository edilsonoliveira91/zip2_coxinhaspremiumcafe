from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.views import View as BaseView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import Bank, BankTransaction, BankTransactionAnexo, UserBankAccess
from .forms import BankForm, BankEditForm
from financials.models import CaixaAdmTransferencia


# ── Helpers de taxa de bandeira ──────────────────────────────────────────────

def _build_bandeira_rates(pinpad_obj):
    """Retorna dict {nome_bandeira: {credito: pct, debito: pct}} para um pinpad."""
    from pinpads.models import BandeiraPinpad
    rates = {}
    if pinpad_obj:
        for b in BandeiraPinpad.objects.filter(pinpad=pinpad_obj):
            rates[b.nome.lower()] = {
                'credito': b.taxa_credito,
                'debito':  b.taxa_debito,
            }
    return rates


def _calc_taxa_transferencias(transferencias_qs, rates_map):
    """Calcula o total de taxas de um queryset de CaixaAdmTransferencia."""
    total = Decimal('0')
    for t in transferencias_qs.values('valor', 'metodo_pagamento', 'bandeira', 'taxa_aplicada'):
        pct = t.get('taxa_aplicada') or Decimal('0')
        if not pct and t['metodo_pagamento'] in ('credito', 'debito'):
            chave = (t['bandeira'] or '').lower()
            r = rates_map.get(chave, {})
            pct = r.get(t['metodo_pagamento'], Decimal('0'))
        total += t['valor'] * pct / Decimal('100')
    return total


def _build_excluir_ids(bank, a_receber_qs):
    """
    Retorna o set de IDs de BankTransaction a excluir do saldo (são "A Receber").

    Usa o FK direto (bank_transaction_id) para registros novos — sem ambiguidade.
    Para registros antigos sem FK, faz fallback por valor+descricao tomando apenas
    UM resultado por pendência (evita over-exclusão quando existem dois iguais).
    """
    excluir_ids = set()
    used_ids = set()

    # Registros com FK direto — O(1) por registro, sem ambiguidade
    for bt_id in a_receber_qs.filter(bank_transaction__isnull=False).values_list('bank_transaction_id', flat=True):
        excluir_ids.add(bt_id)
        used_ids.add(bt_id)

    # Registros antigos sem FK — fallback por valor+descricao, um BT por pendência
    for p in a_receber_qs.filter(bank_transaction__isnull=True).values('valor', 'descricao'):
        qs = bank.transactions.filter(is_entrada=True, valor=p['valor']).exclude(id__in=used_ids)
        if p['descricao']:
            qs = qs.filter(descricao=p['descricao'])
        bt_id = qs.order_by('id').values_list('id', flat=True).first()
        if bt_id:
            excluir_ids.add(bt_id)
            used_ids.add(bt_id)

    return excluir_ids


# ── Helpers de acesso ────────────────────────────────────────────────────────

def _has_global(user, perm):
    return user.is_superuser or user.has_perm(f'banks.{perm}')


def _check_bank(user, bank, action):
    """
    Verifica se o usuário pode executar `action` num banco específico.
    action: 'view' | 'change' | 'add_tx' | 'pay_tx' | 'transfer_tx' | 'del_tx'
    Retorna True se tem acesso global ou acesso por UserBankAccess.
    """
    global_map = {
        'view':        'view_bank',
        'change':      'change_bank',
        'add_tx':      'add_banktransaction',
        'pay_tx':      'add_banktransaction',
        'transfer_tx': 'add_banktransaction',
        'del_tx':      'delete_banktransaction',
    }
    if _has_global(user, global_map[action]):
        return True

    field_map = {
        'view':        'can_view',
        'change':      'can_change',
        'add_tx':      'can_add_transaction',
        'pay_tx':      'can_pay_transaction',
        'transfer_tx': 'can_transfer_transaction',
        'del_tx':      'can_delete_transaction',
    }
    try:
        access = UserBankAccess.objects.get(user=user, bank=bank)
        return getattr(access, field_map[action], False)
    except UserBankAccess.DoesNotExist:
        return False


def _accessible_banks(user):
    """Queryset de bancos que o usuário pode visualizar."""
    if _has_global(user, 'view_bank'):
        return Bank.objects.all()
    return Bank.objects.filter(user_accesses__user=user, user_accesses__can_view=True)


# ── Views ─────────────────────────────────────────────────────────────────────

class BankListView(LoginRequiredMixin, ListView):
    model = Bank
    template_name = 'bank/bank_list.html'
    context_object_name = 'banks'

    def get_queryset(self):
        return _accessible_banks(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        from pinpads.models import Pinpad
        hoje   = timezone.localdate()
        banks  = list(ctx['banks'])
        pinpad = Pinpad.objects.filter(is_active=True).first()
        rates  = _build_bandeira_rates(pinpad)

        total_geral = Decimal('0.00')
        for bank in banks:
            a_receber_qs = CaixaAdmTransferencia.objects.filter(
                banco_destino=bank,
                conciliado=False,
                cancelada=False,
            )
            excluir_ids = _build_excluir_ids(bank, a_receber_qs)
            settled  = bank.transactions.filter(data__date__lte=hoje).exclude(id__in=excluir_ids)
            vi       = bank.valor_inicial or Decimal('0')
            entradas = settled.filter(is_entrada=True).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            saidas   = settled.filter(is_entrada=False).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            saldo_bruto = vi + entradas - saidas

            # Deduz taxas (mesmo cálculo do card "Saldo disponível" do extrato)
            all_conciliadas = CaixaAdmTransferencia.objects.filter(
                banco_destino=bank, conciliado=True, cancelada=False
            )
            total_taxa = _calc_taxa_transferencias(all_conciliadas, rates)

            bank.saldo_atual = saldo_bruto - total_taxa
            total_geral += bank.saldo_atual

        ctx['banks']       = banks
        ctx['total_geral'] = total_geral
        return ctx


class BankCreateView(LoginRequiredMixin, CreateView):
    model = Bank
    form_class = BankForm
    template_name = 'bank/bank_form.html'
    success_url = reverse_lazy('banks:bank_list')

    def dispatch(self, request, *args, **kwargs):
        if not _has_global(request.user, 'add_bank'):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Novo Banco'
        ctx['is_editing'] = False
        return ctx

    def form_valid(self, form):
        valor_inicial = form.cleaned_data.get('valor_inicial') or Decimal('0.00')
        form.instance.criado_por = self.request.user
        form.instance.valor_inicial = Decimal('0.00')  # saldo via transaction, não campo direto
        response = super().form_valid(form)
        if valor_inicial > 0:
            BankTransaction.objects.create(
                bank=self.object,
                tipo='deposito',
                descricao='Saldo Inicial',
                valor=valor_inicial,
                is_entrada=True,
                criado_por=self.request.user,
            )
        messages.success(self.request, f'Banco "{self.object.nome}" cadastrado com sucesso!')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Corrija os erros abaixo.')
        return super().form_invalid(form)


class BankUpdateView(LoginRequiredMixin, UpdateView):
    model = Bank
    form_class = BankEditForm
    template_name = 'bank/bank_form.html'
    success_url = reverse_lazy('banks:bank_list')

    def dispatch(self, request, *args, **kwargs):
        bank = get_object_or_404(Bank, pk=kwargs['pk'])
        if not _check_bank(request.user, bank, 'change'):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = f'Editar: {self.object.nome}'
        ctx['is_editing'] = True
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f'Banco "{form.instance.nome}" atualizado com sucesso!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Corrija os erros abaixo.')
        return super().form_invalid(form)


class BankDeleteView(LoginRequiredMixin, DeleteView):
    model = Bank
    success_url = reverse_lazy('banks:bank_list')

    def dispatch(self, request, *args, **kwargs):
        if not _has_global(request.user, 'delete_bank'):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        bank = self.get_object()
        messages.success(request, f'Banco "{bank.nome}" removido.')
        return super().delete(request, *args, **kwargs)


class BankStatementView(LoginRequiredMixin, BaseView):
    template_name = 'statement/bank_statement.html'

    def get(self, request, pk):
        from django.shortcuts import render
        bank = get_object_or_404(Bank, pk=pk)

        if not _check_bank(request.user, bank, 'view'):
            raise PermissionDenied

        outros_bancos = _accessible_banks(request.user).exclude(pk=pk)

        from financials.models import CaixaAdmTransferencia

        hoje = timezone.localdate()
        hoje_str = hoje.strftime('%Y-%m-%d')

        # Padrão: filtra pela data atual; usuário pode limpar os campos para ver tudo
        data_inicio_str = request.GET.get('data_inicio', hoje_str)
        data_fim_str    = request.GET.get('data_fim',    hoje_str)

        data_inicio = None
        data_fim = None

        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        valor_inicial = bank.valor_inicial or Decimal('0.00')

        def calc_saldo(qs):
            entradas = qs.filter(is_entrada=True).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            saidas = qs.filter(is_entrada=False).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            return entradas - saidas

        a_receber_qs = CaixaAdmTransferencia.objects.filter(
            banco_destino=bank,
            conciliado=False,
            cancelada=False,
        ).select_related('criado_por')

        total_a_receber = a_receber_qs.aggregate(t=Sum('valor'))['t'] or Decimal('0')

        # Calcula data de liquidação dinamicamente pelo pinpad ativo
        from pinpads.models import Pinpad, BandeiraPinpad
        pinpad = Pinpad.objects.filter(is_active=True).first()
        dias_map = {
            'credito':  pinpad.dias_credito if pinpad else 30,
            'debito':   pinpad.dias_debito  if pinpad else 1,
            'pix':      pinpad.dias_pix     if pinpad else 1,
            'dinheiro': 0,
        }
        a_receber_detalhe = list(a_receber_qs)
        for t in a_receber_detalhe:
            base = t.data_caixa or hoje
            t.data_liquidacao_dinamica = base + timedelta(days=dias_map.get(t.metodo_pagamento, 0))
        a_receber_detalhe.sort(key=lambda t: (t.data_liquidacao_dinamica, t.criado_em))

        # Mesmo que o prazo já tenha chegado, a entrada só conta no saldo
        # quando o usuário conciliar manualmente.
        pendente_tx_ids = _build_excluir_ids(bank, a_receber_qs)

        settled_txs = bank.transactions.filter(data__date__lte=hoje).exclude(id__in=pendente_tx_ids)
        saldo_atual = valor_inicial + calc_saldo(settled_txs)

        saldo_anterior = None
        total_periodo = None

        # Sempre aplica o filtro de datas na listagem (padrão: hoje)
        period_qs = settled_txs
        if data_inicio:
            period_qs = period_qs.filter(data__date__gte=data_inicio)
        if data_fim:
            period_qs = period_qs.filter(data__date__lte=data_fim)

        # Filtro por tipo de lançamento
        tipo_filtro = request.GET.get('tipo', '').strip()
        if tipo_filtro in ('deposito', 'pagamento', 'transferencia'):
            period_qs_tipo = period_qs.filter(tipo=tipo_filtro)
        else:
            tipo_filtro = ''
            period_qs_tipo = period_qs

        transacoes = period_qs_tipo.prefetch_related('anexos').order_by('-data', '-id')

        # Saldo da filtragem de tipo (para atualizar o card Saldo Disponível)
        saldo_filtrado = calc_saldo(period_qs_tipo)

        # 3 cards só aparecem quando o range abrange mais de um dia
        filtrado = bool(data_inicio and data_fim and data_inicio != data_fim)
        if filtrado:
            before_qs = settled_txs.filter(data__date__lt=data_inicio)
            saldo_anterior = valor_inicial + calc_saldo(before_qs)
            total_periodo = calc_saldo(period_qs)

        bandeiras_rates = _build_bandeira_rates(pinpad)

        # Anotar cada transação com taxa individual e valor líquido
        # Usa taxa_tx gravada no DB (set na conciliação); fallback dinâmico para registros antigos
        transacoes = list(transacoes)
        for tx in transacoes:
            stored_taxa = tx.taxa_tx or Decimal('0')
            if stored_taxa > 0:
                pass  # usa o valor gravado
            elif tx.is_entrada and tx.metodo_pagamento in ('credito', 'debito'):
                chave = (tx.bandeira or '').lower()
                r = bandeiras_rates.get(chave, {})
                pct = r.get(tx.metodo_pagamento, Decimal('0'))
                stored_taxa = (tx.valor * pct / Decimal('100')).quantize(Decimal('0.01')) if pct else Decimal('0')
            tx.taxa_tx = stored_taxa
            tx.valor_liquido = tx.valor - tx.taxa_tx

        # Totais sobre TODAS as transferências já conciliadas do banco
        all_conciliadas = CaixaAdmTransferencia.objects.filter(
            banco_destino=bank, conciliado=True, cancelada=False
        )
        total_taxa    = _calc_taxa_transferencias(all_conciliadas, bandeiras_rates)
        # saldo_atual já inclui pagamentos feitos no banco (is_entrada=False)
        # bruto_geral = saldo real antes de descontar taxas de bandeira
        bruto_geral   = saldo_atual
        liquido_geral = saldo_atual - total_taxa

        # Para o card "Saldo do período" (filtrado multi-dia)
        if filtrado and data_inicio and data_fim:
            periodo_conciliadas = all_conciliadas.filter(
                conciliado_em__date__gte=data_inicio,
                conciliado_em__date__lte=data_fim,
            )
            taxa_periodo    = _calc_taxa_transferencias(periodo_conciliadas, bandeiras_rates)
            # bruto_periodo = saldo líquido das transações do período (entradas - saídas)
            bruto_periodo   = calc_saldo(period_qs)
            liquido_periodo = bruto_periodo - taxa_periodo
        else:
            bruto_periodo   = bruto_geral
            taxa_periodo    = total_taxa
            liquido_periodo = liquido_geral

        # A Receber: bruto/taxa/líquido das transferências pendentes
        taxa_a_receber = _calc_taxa_transferencias(a_receber_qs, bandeiras_rates)
        liquido_a_receber = total_a_receber - taxa_a_receber

        return render(request, self.template_name, {
            'bank': bank,
            'outros_bancos': outros_bancos,
            'transacoes': transacoes,
            'saldo_atual': saldo_atual,
            'saldo_anterior': saldo_anterior,
            'total_periodo': total_periodo,
            'filtrado': filtrado,
            'data_inicio': data_inicio_str,
            'data_fim': data_fim_str,
            'tipo_filtro': tipo_filtro,
            'saldo_filtrado': saldo_filtrado,
            'tipos_lancamento': [
                ('deposito',      'Depósito'),
                ('pagamento',     'Pagamento'),
                ('transferencia', 'Transferência'),
            ],
            'a_receber': a_receber_detalhe,
            'total_a_receber': total_a_receber,
            'taxa_a_receber': taxa_a_receber,
            'liquido_a_receber': liquido_a_receber,
            'hoje': hoje,
            'bruto_geral': bruto_geral,
            'total_taxa': total_taxa,
            'liquido_geral': liquido_geral,
            'bruto_periodo': bruto_periodo,
            'taxa_periodo': taxa_periodo,
            'liquido_periodo': liquido_periodo,
            'can_add_tx':      _check_bank(request.user, bank, 'add_tx'),
            'can_pay_tx':      _check_bank(request.user, bank, 'pay_tx'),
            'can_transfer_tx': _check_bank(request.user, bank, 'transfer_tx'),
            'can_change':      _check_bank(request.user, bank, 'change'),
            'can_del_tx':      _check_bank(request.user, bank, 'del_tx'),
            'bandeiras_pinpad': list(
                BandeiraPinpad.objects.filter(pinpad=pinpad).values('nome', 'taxa_credito', 'taxa_debito')
            ) if pinpad else [],
            'metodos_pagamento': [
                ('dinheiro', 'Dinheiro'),
                ('pix',      'PIX'),
                ('debito',   'Débito'),
                ('credito',  'Crédito'),
            ],
        })


class BankAdicionarView(LoginRequiredMixin, BaseView):
    def post(self, request, pk):
        bank = get_object_or_404(Bank, pk=pk)
        if not _check_bank(request.user, bank, 'add_tx'):
            raise PermissionDenied

        descricao = request.POST.get('descricao', '').strip() or 'Depósito'
        observacao = request.POST.get('observacao', '').strip()
        try:
            valor = Decimal(request.POST.get('valor', '0').replace(',', '.'))
        except Exception:
            valor = Decimal('0')

        if valor <= 0:
            messages.error(request, 'Informe um valor válido.')
            return redirect('banks:bank_statement', pk=pk)

        metodo  = request.POST.get('metodo_pagamento', '').strip()
        bandeira = request.POST.get('bandeira', '').strip()

        BankTransaction.objects.create(
            bank=bank, tipo='deposito', descricao=descricao,
            valor=valor, is_entrada=True, observacao=observacao,
            metodo_pagamento=metodo, bandeira=bandeira,
            criado_por=request.user,
        )
        messages.success(request, f'Depósito de R$ {valor:.2f} adicionado.')
        return redirect('banks:bank_statement', pk=pk)


class BankPagarView(LoginRequiredMixin, BaseView):
    def post(self, request, pk):
        bank = get_object_or_404(Bank, pk=pk)
        if not _check_bank(request.user, bank, 'pay_tx'):
            raise PermissionDenied

        descricao = request.POST.get('descricao', '').strip() or 'Pagamento'
        observacao = request.POST.get('observacao', '').strip()
        arquivos = request.FILES.getlist('comprovantes')
        try:
            valor = Decimal(request.POST.get('valor', '0').replace(',', '.'))
        except Exception:
            valor = Decimal('0')

        if valor <= 0:
            messages.error(request, 'Informe um valor válido.')
            return redirect('banks:bank_statement', pk=pk)

        # Primeiro arquivo vai para o campo legado; os demais vão para BankTransactionAnexo
        primeiro = arquivos[0] if arquivos else None
        tx = BankTransaction.objects.create(
            bank=bank, tipo='pagamento', descricao=descricao,
            valor=valor, is_entrada=False, observacao=observacao,
            comprovante=primeiro,
            criado_por=request.user,
        )
        for arq in arquivos:
            BankTransactionAnexo.objects.create(transaction=tx, arquivo=arq)

        messages.success(request, f'Pagamento de R$ {valor:.2f} registrado.')
        return redirect('banks:bank_statement', pk=pk)


class BankTransferirView(LoginRequiredMixin, BaseView):
    def post(self, request, pk):
        bank = get_object_or_404(Bank, pk=pk)
        if not _check_bank(request.user, bank, 'transfer_tx'):
            raise PermissionDenied

        destino_id = request.POST.get('banco_destino')
        descricao = request.POST.get('descricao', '').strip() or 'Transferência'
        observacao = request.POST.get('observacao', '').strip()
        try:
            valor = Decimal(request.POST.get('valor', '0').replace(',', '.'))
        except Exception:
            valor = Decimal('0')

        if valor <= 0:
            messages.error(request, 'Informe um valor válido.')
            return redirect('banks:bank_statement', pk=pk)

        banco_destino = None
        if destino_id:
            banco_destino = Bank.objects.filter(pk=destino_id).first()

        BankTransaction.objects.create(
            bank=bank, tipo='transferencia',
            descricao=f'Transferência para {banco_destino.nome if banco_destino else "externo"}',
            valor=valor, is_entrada=False, observacao=observacao,
            banco_destino=banco_destino, criado_por=request.user,
        )

        if banco_destino:
            BankTransaction.objects.create(
                bank=banco_destino, tipo='transferencia',
                descricao=f'Transferência de {bank.nome}',
                valor=valor, is_entrada=True, observacao=observacao,
                banco_destino=bank, criado_por=request.user,
            )

        messages.success(request, f'Transferência de R$ {valor:.2f} realizada.')
        return redirect('banks:bank_statement', pk=pk)


class BankTransactionEditView(LoginRequiredMixin, BaseView):
    def post(self, request, bank_pk, tx_pk):
        bank = get_object_or_404(Bank, pk=bank_pk)
        if not _check_bank(request.user, bank, 'change'):
            raise PermissionDenied

        tx = get_object_or_404(BankTransaction, pk=tx_pk, bank=bank)

        descricao = request.POST.get('descricao', '').strip() or tx.descricao
        observacao = request.POST.get('observacao', '').strip()
        data_str = request.POST.get('data', '').strip()

        try:
            valor = Decimal(request.POST.get('valor', '0').replace(',', '.'))
        except Exception:
            valor = tx.valor

        if valor <= 0:
            messages.error(request, 'Informe um valor válido.')
            return redirect('banks:bank_statement', pk=bank_pk)

        tx.descricao = descricao
        tx.observacao = observacao
        tx.valor = valor

        if data_str:
            try:
                from django.utils import timezone as tz
                naive = datetime.strptime(data_str, '%Y-%m-%dT%H:%M')
                tx.data = tz.make_aware(naive)
            except ValueError:
                pass

        tx.save()
        messages.success(request, 'Lançamento atualizado com sucesso.')
        return redirect('banks:bank_statement', pk=bank_pk)


class BankTransactionDeleteView(LoginRequiredMixin, BaseView):
    def post(self, request, bank_pk, tx_pk):
        bank = get_object_or_404(Bank, pk=bank_pk)
        if not _check_bank(request.user, bank, 'del_tx'):
            raise PermissionDenied

        tx = get_object_or_404(BankTransaction, pk=tx_pk, bank=bank)
        tx.delete()
        messages.success(request, 'Lançamento removido.')
        return redirect('banks:bank_statement', pk=bank_pk)


class BankStatementPDFView(LoginRequiredMixin, BaseView):
    def get(self, request, pk):
        import io
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        from django.http import HttpResponse
        from decimal import Decimal

        bank = get_object_or_404(Bank, pk=pk)
        if not _check_bank(request.user, bank, 'view'):
            raise PermissionDenied

        hoje = timezone.localdate()
        hoje_str = hoje.strftime('%Y-%m-%d')

        data_inicio_str = request.GET.get('data_inicio', hoje_str)
        data_fim_str    = request.GET.get('data_fim',    hoje_str)

        data_inicio = None
        data_fim = None
        if data_inicio_str:
            try:
                data_inicio = datetime.strptime(data_inicio_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if data_fim_str:
            try:
                data_fim = datetime.strptime(data_fim_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        from financials.models import CaixaAdmTransferencia

        valor_inicial = bank.valor_inicial or Decimal('0.00')

        def calc_saldo(qs):
            entradas = qs.filter(is_entrada=True).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            saidas   = qs.filter(is_entrada=False).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            return entradas - saidas

        pendente_ids = set()
        for p in CaixaAdmTransferencia.objects.filter(banco_destino=bank, conciliado=False, cancelada=False):
            pendente_ids.update(
                bank.transactions.filter(is_entrada=True, valor=p.valor, descricao=p.descricao)
                .values_list('id', flat=True)
            )

        settled_txs = bank.transactions.filter(data__date__lte=hoje).exclude(id__in=pendente_ids)
        saldo_atual = valor_inicial + calc_saldo(settled_txs)

        period_qs = settled_txs
        if data_inicio:
            period_qs = period_qs.filter(data__date__gte=data_inicio)
        if data_fim:
            period_qs = period_qs.filter(data__date__lte=data_fim)
        transacoes = list(period_qs.order_by('-data', '-id'))

        # ── Cálculo de taxas das bandeiras ───────────────────────────────────
        from pinpads.models import Pinpad, BandeiraPinpad

        pinpad = Pinpad.objects.filter(is_active=True).first()

        bandeiras_rates = {}
        if pinpad:
            for b in BandeiraPinpad.objects.filter(pinpad=pinpad):
                bandeiras_rates[b.nome.lower()] = {
                    'credito': b.taxa_credito,
                    'debito':  b.taxa_debito,
                }

        # Anota cada transação com taxa individual — mesma lógica da tela
        for tx in transacoes:
            stored = tx.taxa_tx or Decimal('0')
            if not stored and tx.is_entrada and tx.metodo_pagamento in ('credito', 'debito'):
                chave = (tx.bandeira or '').lower()
                r = bandeiras_rates.get(chave, {})
                pct = r.get(tx.metodo_pagamento, Decimal('0'))
                stored = (tx.valor * pct / Decimal('100')).quantize(Decimal('0.01')) if pct else Decimal('0')
            tx.taxa_tx = stored
            tx.valor_liquido = tx.valor - stored

        def _calc_taxa_pdf(transferencias_qs):
            total = Decimal('0')
            for t in transferencias_qs.values('valor', 'metodo_pagamento', 'bandeira', 'taxa_aplicada'):
                pct = t.get('taxa_aplicada') or Decimal('0')
                if not pct and t['metodo_pagamento'] in ('credito', 'debito'):
                    chave = t['bandeira'].lower() if t['bandeira'] else ''
                    r = bandeiras_rates.get(chave, {})
                    pct = r.get(t['metodo_pagamento'], Decimal('0'))
                total += t['valor'] * pct / Decimal('100')
            return total

        all_conciliadas = CaixaAdmTransferencia.objects.filter(
            banco_destino=bank, conciliado=True, cancelada=False
        )
        bruto_geral   = all_conciliadas.aggregate(t=Sum('valor'))['t'] or Decimal('0')
        total_taxa    = _calc_taxa_pdf(all_conciliadas)
        liquido_geral = bruto_geral - total_taxa

        # Fees específicas do período
        filtrado_pdf = bool(data_inicio and data_fim and data_inicio != data_fim)
        if filtrado_pdf:
            periodo_conciliadas = all_conciliadas.filter(
                conciliado_em__date__gte=data_inicio,
                conciliado_em__date__lte=data_fim,
            )
        else:
            periodo_conciliadas = all_conciliadas
        taxa_periodo_pdf    = _calc_taxa_pdf(periodo_conciliadas)
        bruto_periodo_pdf   = calc_saldo(period_qs)
        liquido_periodo_pdf = bruto_periodo_pdf - taxa_periodo_pdf

        saldo_anterior_pdf = None
        if filtrado_pdf and data_inicio:
            before_qs = settled_txs.filter(data__date__lt=data_inicio)
            saldo_anterior_pdf = valor_inicial + calc_saldo(before_qs)

        # Breakdown crédito / débito (acumulado, todas as conciliadas)

        # Breakdown de taxas por bandeira (crédito e débito separados)
        credito_por_bandeira = {}
        debito_por_bandeira  = {}
        for _t in all_conciliadas.values('valor', 'metodo_pagamento', 'bandeira'):
            _chave = _t['bandeira'].lower() if _t['bandeira'] else ''
            _nome  = _t['bandeira'].strip() if _t['bandeira'] else 'Sem bandeira'
            _r     = bandeiras_rates.get(_chave, {})
            if _t['metodo_pagamento'] == 'credito':
                _pct = _r.get('credito', Decimal('0'))
                if _pct:
                    _taxa = _t['valor'] * _pct / Decimal('100')
                    credito_por_bandeira[_nome] = credito_por_bandeira.get(_nome, Decimal('0')) + _taxa
            elif _t['metodo_pagamento'] == 'debito':
                _pct = _r.get('debito', Decimal('0'))
                if _pct:
                    _taxa = _t['valor'] * _pct / Decimal('100')
                    debito_por_bandeira[_nome] = debito_por_bandeira.get(_nome, Decimal('0')) + _taxa



        # ── Monta o PDF (estilo Apple) ───────────────────────────────────────
        buffer = io.BytesIO()
        page_w, page_h = A4
        margin = 18 * mm
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=margin, rightMargin=margin,
            topMargin=16*mm, bottomMargin=16*mm,
        )
        content_w = page_w - 2 * margin

        # ── Paleta ───────────────────────────────────────────────────────────
        azul    = colors.HexColor('#007AFF')
        azul2   = colors.HexColor('#5AC8FA')
        cinza   = colors.HexColor('#8E8E93')
        escuro  = colors.HexColor('#1D1D1F')
        claro   = colors.HexColor('#F5F5F7')
        borda   = colors.HexColor('#E5E5EA')
        verde   = colors.HexColor('#34C759')
        verm    = colors.HexColor('#FF3B30')
        laranja = colors.HexColor('#FF9500')
        amarelo = colors.HexColor('#FFD60A')
        branco  = colors.white
        fundo2  = colors.HexColor('#FAFAFA')

        # ── Helpers ──────────────────────────────────────────────────────────
        fmt = lambda v: f'R$ {v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

        def ps(name, size=9, bold=False, color=escuro, align=TA_LEFT, leading=None):
            return ParagraphStyle(
                name,
                fontSize=size,
                fontName='Helvetica-Bold' if bold else 'Helvetica',
                textColor=color,
                alignment=align,
                leading=leading or (size * 1.35),
            )

        label_di = data_inicio.strftime('%d/%m/%Y') if data_inicio else hoje.strftime('%d/%m/%Y')
        label_df = data_fim.strftime('%d/%m/%Y')    if data_fim    else hoje.strftime('%d/%m/%Y')
        periodo_txt = f'{label_di} → {label_df}' if label_di != label_df else label_di
        gerado_em = timezone.localtime(timezone.now()).strftime('%d/%m/%Y às %H:%M')

        story = []

        # ── HEADER ───────────────────────────────────────────────────────────
        conta_info = ''
        if bank.numero_conta:
            conta_info = f'Conta {bank.numero_conta}'
            if bank.agencia:
                conta_info += f'  ·  Ag. {bank.agencia}'

        header_table = Table(
            [[
                Paragraph(bank.nome, ps('hn', 20, bold=True, color=escuro)),
                Paragraph(f'Gerado em {gerado_em}', ps('hg', 8, color=cinza, align=TA_RIGHT)),
            ],[
                Paragraph(conta_info, ps('hc', 9, color=cinza)),
                Paragraph(f'Período: {periodo_txt}', ps('hp', 9, color=azul, align=TA_RIGHT, bold=True)),
            ]],
            colWidths=[content_w * 0.6, content_w * 0.4],
        )
        header_table.setStyle(TableStyle([
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING',    (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('LEFTPADDING',   (0,0), (-1,-1), 0),
            ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ]))
        story += [header_table, Spacer(1, 3*mm)]

        # Linha divisória
        from reportlab.platypus import HRFlowable
        story += [
            HRFlowable(width='100%', thickness=1, color=borda, spaceAfter=4*mm),
        ]



        # ── CARDS DE MÉTRICAS ────────────────────────────────────────────────
        entradas_p = sum(tx.valor for tx in transacoes if tx.is_entrada)
        saidas_p   = sum(tx.valor for tx in transacoes if not tx.is_entrada)

        azul_light = colors.HexColor('#A8D8FF')
        azul_bg2   = colors.HexColor('#EAF3FF')
        azul_bd2   = colors.HexColor('#BDD8FF')
        dark_card  = colors.HexColor('#1C1C1E')

        gap    = 4 * mm
        card_w = (content_w - 3 * gap) / 4

        # Flowable customizado: roundRect desenhado direto no canvas (sem clipping)
        from reportlab.platypus import Flowable as _Flowable

        class RoundCard(_Flowable):
            def __init__(self, width, rows, border_color, radius=8):
                super().__init__()
                self._w  = width
                self._rows = rows
                self._bc = border_color
                self._r  = radius
                self._h  = sum(tp + round(sz * 1.4) + bp for _, sz, _, _, tp, bp in rows)

            def wrap(self, aw, ah):
                return self._w, self._h

            def draw(self):
                c = self.canv
                w, h, r = self._w, self._h, self._r
                c.saveState()
                c.setFillColor(colors.white)
                c.setStrokeColor(self._bc)
                c.setLineWidth(0.8)
                c.roundRect(0, 0, w, h, r, stroke=1, fill=1)
                y = h
                pad = 10
                for (text, size, bold, color, tp, bp) in self._rows:
                    y -= tp + round(size * 1.4)
                    c.setFillColor(color)
                    c.setFont('Helvetica-Bold' if bold else 'Helvetica', size)
                    c.drawString(pad, y, text)
                    y -= bp
                c.restoreState()

        # Bordas claras por tema
        bd_azul  = colors.HexColor('#C8E2FF')
        bd_verde = colors.HexColor('#C2F0D0')
        bd_verm  = colors.HexColor('#FFD0CE')
        bd_cinza = colors.HexColor('#D1D1D6')

        ts_cards = TableStyle([
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ])

        if filtrado_pdf and saldo_anterior_pdf is not None:
            # ── 3 cards: Anterior | No Período | Saldo Atual ─────────────────
            card_w3 = (content_w - 2 * gap) / 3

            label_di_curto = data_inicio.strftime('%d/%m/%y') if data_inicio else ''
            label_df_curto = data_fim.strftime('%d/%m/%y')    if data_fim    else ''

            c_anterior = RoundCard(card_w3, [
                ('SALDO ANTERIOR',       6, True,  cinza,  10, 2),
                (fmt(saldo_anterior_pdf),14, True,  escuro,  2, 2),
                (f'Ate {label_di_curto}', 6, False, cinza,   2, 10),
            ], border_color=bd_cinza)

            c_periodo = RoundCard(card_w3, [
                ('NO PERIODO',                        6, True,  azul,   10, 2),
                (fmt(bruto_periodo_pdf),             13, True,  escuro,  2, 2),
                (f'Entradas: {fmt(entradas_p)}',      6, False, verde,   3, 1),
                (f'Saidas:   {fmt(saidas_p)}',        6, False, verm,    1, 1),
                (f'Taxas:   -{fmt(taxa_periodo_pdf)}', 6, False, laranja, 1, 1),
                (f'Liquido:  {fmt(liquido_periodo_pdf)}', 6, True, verde, 2, 8),
            ], border_color=bd_azul)

            c_atual = RoundCard(card_w3, [
                ('SALDO ATUAL',         6, True,  verde,  10, 2),
                (fmt(saldo_atual),     14, True,  escuro,  2, 2),
                ('Saldo total do banco', 6, False, cinza,   2, 10),
            ], border_color=bd_verde)

            cards_row = Table(
                [[c_anterior, '', c_periodo, '', c_atual]],
                colWidths=[card_w3, gap, card_w3, gap, card_w3],
            )
        else:
            # ── 4 cards: Saldo Anterior | Entradas | Saídas | Saldo Atual ────
            if data_inicio:
                before_4 = settled_txs.filter(data__date__lt=data_inicio)
                saldo_ant_4 = valor_inicial + calc_saldo(before_4)
                label_ant_4 = f'Antes de {data_inicio.strftime("%d/%m/%y")}'
            else:
                saldo_ant_4 = valor_inicial
                label_ant_4 = 'Saldo de abertura'

            card_saldo = RoundCard(card_w, [
                ('SALDO ANTERIOR',   6, True,  cinza,  10, 2),
                (fmt(saldo_ant_4),  14, True,  escuro,  2, 2),
                (label_ant_4,        6, False, cinza,   2, 10),
            ], border_color=bd_cinza)

            card_entradas = RoundCard(card_w, [
                ('ENTRADAS DO PERIODO', 6, True,  verde,  10, 2),
                (fmt(entradas_p),      14, True,  escuro,  2, 2),
                (periodo_txt,           6, False, cinza,   2, 10),
            ], border_color=bd_verde)

            card_saidas = RoundCard(card_w, [
                ('SAIDAS DO PERIODO',  6, True,  verm,   10, 2),
                (fmt(saidas_p),        14, True,  escuro,  2, 2),
                (periodo_txt,           6, False, cinza,   2, 10),
            ], border_color=bd_verm)

            card_taxas = RoundCard(card_w, [
                ('SALDO ATUAL',         6, True,  verde,  10, 2),
                (fmt(saldo_atual),     14, True,  escuro,  2, 2),
                ('Saldo total do banco', 6, False, cinza,   2, 10),
            ], border_color=bd_verde)

            cards_row = Table(
                [[card_saldo, '', card_entradas, '', card_saidas, '', card_taxas]],
                colWidths=[card_w, gap, card_w, gap, card_w, gap, card_w],
            )

        cards_row.setStyle(ts_cards)
        story += [cards_row, Spacer(1, 3*mm)]


        # Cards credito / debito por bandeira
        from reportlab.platypus import Flowable as _Flowable2

        class KVCard(_Flowable2):
            def __init__(self, width, title, title_color, border_color, rows, radius=8):
                super().__init__()
                self._w      = width
                self._title  = title
                self._tc     = title_color
                self._bc     = border_color
                self._rows   = rows
                self._r      = radius
                self._h      = 12 + 6 + 4 + len(rows) * 17 + 10

            def wrap(self, aw, ah):
                return self._w, self._h

            def draw(self):
                c = self.canv
                w, h, r = self._w, self._h, self._r
                pad = 10
                c.saveState()
                c.setFillColor(colors.white)
                c.setStrokeColor(self._bc)
                c.setLineWidth(0.8)
                c.roundRect(0, 0, w, h, r, stroke=1, fill=1)
                y = h - 10
                y -= 9
                c.setFillColor(self._tc)
                c.setFont('Helvetica-Bold', 7)
                c.drawString(pad, y, self._title)
                y -= 4
                c.setStrokeColor(self._bc)
                c.setLineWidth(0.5)
                c.line(pad, y, w - pad, y)
                y -= 4
                for (label, value, lc, vc) in self._rows:
                    y -= 10
                    c.setFillColor(lc)
                    c.setFont('Helvetica', 7)
                    c.drawString(pad, y, label)
                    c.setFillColor(vc)
                    c.setFont('Helvetica-Bold', 9)
                    c.drawRightString(w - pad, y, value)
                    y -= 7
                c.restoreState()


        # Taxas por bandeira
        detail_gap = 4 * mm
        detail_w   = (content_w - detail_gap) / 2

        rows_credito = [
            (nome, fmt(taxa), cinza, escuro)
            for nome, taxa in sorted(credito_por_bandeira.items())
        ] or [('Sem lancamentos', '---', cinza, cinza)]

        rows_debito = [
            (nome, fmt(taxa), cinza, escuro)
            for nome, taxa in sorted(debito_por_bandeira.items())
        ] or [('Sem lancamentos', '---', cinza, cinza)]

        kv_credito = KVCard(
            detail_w,
            title='CREDITO  -  taxa por bandeira',
            title_color=azul,
            border_color=bd_azul,
            rows=rows_credito,
        )

        kv_debito = KVCard(
            detail_w,
            title='DEBITO  -  taxa por bandeira',
            title_color=verde,
            border_color=bd_verde,
            rows=rows_debito,
        )

        detail_row = Table(
            [[kv_credito, '', kv_debito]],
            colWidths=[detail_w, detail_gap, detail_w],
        )
        detail_row.setStyle(TableStyle([
            ('LEFTPADDING',   (0, 0), (-1, -1), 0),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ]))
        story += [detail_row, Spacer(1, 5*mm)]





        # ── MOVIMENTAÇÕES DO PERÍODO ─────────────────────────────────────────
        story += [
            Paragraph('MOVIMENTAÇÕES DO PERÍODO', ps('sec', 8, bold=True, color=cinza)),
            Spacer(1, 2*mm),
        ]

        th    = ps('th',  8, bold=True, color=cinza, align=TA_CENTER)
        td    = ps('td',  8, color=escuro)
        td_c  = ps('tdc', 8, color=escuro, align=TA_CENTER)

        tipo_labels = {'deposito': 'Depósito', 'pagamento': 'Pagamento', 'transferencia': 'Transf.'}

        rows = [[
            Paragraph('Data / Hora', th),
            Paragraph('Descrição',   th),
            Paragraph('Tipo',        th),
            Paragraph('Valor',       ps('thv', 8, bold=True, color=cinza, align=TA_RIGHT)),
        ]]

        for tx in transacoes:
            data_local = timezone.localtime(tx.data)
            sinal  = '+' if tx.is_entrada else '\u2212'
            cor_v  = verde if tx.is_entrada else verm
            # Usa valor_liquido quando h\u00e1 taxa (igual \u00e0 tela)
            valor_exibido = tx.valor_liquido if tx.taxa_tx else tx.valor
            desc_extra = ''
            if tx.taxa_tx:
                desc_extra = f'<br/><font size="7" color="#FF9500">bruto {fmt(tx.valor)} \u00b7 taxa -{fmt(tx.taxa_tx)}</font>'
            rows.append([
                Paragraph(data_local.strftime('%d/%m/%Y\n%H:%M'),
                          ps(f'td_dt{tx.pk}', 8, color=escuro, leading=11)),
                Paragraph((tx.descricao or '\u2014') + desc_extra, td),
                Paragraph(tipo_labels.get(tx.tipo, tx.tipo), td_c),
                Paragraph(f'{sinal}{fmt(valor_exibido)}',
                          ps(f'tv{tx.pk}', 8, bold=True, color=cor_v, align=TA_RIGHT)),
            ])

        if not transacoes:
            rows.append([
                Paragraph('Nenhuma transação no período selecionado.',
                          ps('emp', 9, color=cinza)),
                '', '', '',
            ])

        col_w = [32*mm, content_w - 32*mm - 28*mm - 30*mm, 28*mm, 30*mm]
        tx_table = Table(rows, colWidths=col_w, repeatRows=1)
        tx_table.setStyle(TableStyle([
            ('BACKGROUND',    (0, 0), (-1,  0), claro),
            ('LINEBELOW',     (0, 0), (-1,  0), 0.8, borda),
            ('ROWBACKGROUNDS',(0, 1), (-1, -1), [branco, colors.HexColor('#FAFAFA')]),
            ('LINEBELOW',     (0, 1), (-1, -2), 0.3, borda),
            ('TOPPADDING',    (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('BOX',           (0, 0), (-1, -1), 0.5, borda),
        ]))
        story += [tx_table, Spacer(1, 5*mm)]

        doc.build(story)
        buffer.seek(0)

        nome_arquivo = f'extrato_{bank.nome.lower().replace(" ", "_")}_{label_di.replace("/", "-")}_{label_df.replace("/", "-")}.pdf'
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
        return response
