from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.views import View as BaseView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime, date
from decimal import Decimal

from .models import Bank, BankTransaction, UserBankAccess
from .forms import BankForm, BankEditForm


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
        from django.db.models import Sum, Q
        hoje = date.today()
        return _accessible_banks(self.request.user).annotate(
            _entradas=Sum(
                'transactions__valor',
                filter=Q(transactions__is_entrada=True, transactions__data__date__lte=hoje),
            ),
            _saidas=Sum(
                'transactions__valor',
                filter=Q(transactions__is_entrada=False, transactions__data__date__lte=hoje),
            ),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        total_geral = Decimal('0.00')
        for bank in ctx['banks']:
            vi       = bank.valor_inicial or Decimal('0.00')
            entradas = bank._entradas     or Decimal('0.00')
            saidas   = bank._saidas       or Decimal('0.00')
            bank.saldo_atual = vi + entradas - saidas
            total_geral += bank.saldo_atual
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

        data_inicio_str = request.GET.get('data_inicio', '')
        data_fim_str = request.GET.get('data_fim', '')

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
        hoje = date.today()

        def calc_saldo(qs):
            entradas = qs.filter(is_entrada=True).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            saidas = qs.filter(is_entrada=False).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            return entradas - saidas

        settled_txs = bank.transactions.filter(data__date__lte=hoje)
        a_receber_txs = bank.transactions.filter(data__date__gt=hoje, is_entrada=True).order_by('data')
        saldo_atual = valor_inicial + calc_saldo(settled_txs)
        total_a_receber = a_receber_txs.aggregate(t=Sum('valor'))['t'] or Decimal('0')

        saldo_anterior = None
        total_periodo = None
        filtrado = bool(data_inicio or data_fim)

        if filtrado:
            before_qs = settled_txs
            period_qs = settled_txs

            if data_inicio:
                before_qs = before_qs.filter(data__date__lt=data_inicio)
                period_qs = period_qs.filter(data__date__gte=data_inicio)

            if data_fim:
                period_qs = period_qs.filter(data__date__lte=data_fim)

            saldo_anterior = valor_inicial + calc_saldo(before_qs)
            total_periodo = calc_saldo(period_qs)
            transacoes = period_qs.order_by('-data', '-id')
        else:
            transacoes = settled_txs.order_by('-data', '-id')

        from financials.models import CaixaAdmTransferencia
        a_receber_detalhe = CaixaAdmTransferencia.objects.filter(
            banco_destino=bank,
            conciliado=False,
        ).select_related('criado_por').order_by('-criado_em')

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
            'a_receber': a_receber_detalhe,
            'total_a_receber': total_a_receber,
            'hoje': hoje,
            'can_add_tx':      _check_bank(request.user, bank, 'add_tx'),
            'can_pay_tx':      _check_bank(request.user, bank, 'pay_tx'),
            'can_transfer_tx': _check_bank(request.user, bank, 'transfer_tx'),
            'can_change':      _check_bank(request.user, bank, 'change'),
            'can_del_tx':      _check_bank(request.user, bank, 'del_tx'),
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

        BankTransaction.objects.create(
            bank=bank, tipo='deposito', descricao=descricao,
            valor=valor, is_entrada=True, observacao=observacao,
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
        comprovante = request.FILES.get('comprovante')
        try:
            valor = Decimal(request.POST.get('valor', '0').replace(',', '.'))
        except Exception:
            valor = Decimal('0')

        if valor <= 0:
            messages.error(request, 'Informe um valor válido.')
            return redirect('banks:bank_statement', pk=pk)

        BankTransaction.objects.create(
            bank=bank, tipo='pagamento', descricao=descricao,
            valor=valor, is_entrada=False, observacao=observacao,
            comprovante=comprovante,
            criado_por=request.user,
        )
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
