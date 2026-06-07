from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, View
from django.views import View as BaseView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime, date
from decimal import Decimal

from .models import Bank, BankTransaction
from .forms import BankForm


class BankListView(LoginRequiredMixin, ListView):
    model = Bank
    template_name = 'bank/bank_list.html'
    context_object_name = 'banks'


class BankCreateView(LoginRequiredMixin, CreateView):
    model = Bank
    form_class = BankForm
    template_name = 'bank/bank_form.html'
    success_url = reverse_lazy('banks:bank_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Novo Banco'
        ctx['is_editing'] = False
        return ctx

    def form_valid(self, form):
        form.instance.criado_por = self.request.user
        messages.success(self.request, f'Banco "{form.instance.nome}" cadastrado com sucesso!')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Corrija os erros abaixo.')
        return super().form_invalid(form)


class BankUpdateView(LoginRequiredMixin, UpdateView):
    model = Bank
    form_class = BankForm
    template_name = 'bank/bank_form.html'
    success_url = reverse_lazy('banks:bank_list')

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

    def delete(self, request, *args, **kwargs):
        bank = self.get_object()
        messages.success(request, f'Banco "{bank.nome}" removido.')
        return super().delete(request, *args, **kwargs)


class BankStatementView(LoginRequiredMixin, BaseView):
    template_name = 'statement/bank_statement.html'

    def get(self, request, pk):
        from django.shortcuts import render
        bank = get_object_or_404(Bank, pk=pk)
        outros_bancos = Bank.objects.exclude(pk=pk)

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

        def calc_saldo(qs):
            entradas = qs.filter(is_entrada=True).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            saidas = qs.filter(is_entrada=False).aggregate(t=Sum('valor'))['t'] or Decimal('0')
            return entradas - saidas

        all_txs = bank.transactions.all()
        saldo_atual = valor_inicial + calc_saldo(all_txs)

        saldo_anterior = None
        total_periodo = None
        filtrado = bool(data_inicio or data_fim)

        if filtrado:
            before_qs = bank.transactions.all()
            period_qs = bank.transactions.all()

            if data_inicio:
                before_qs = before_qs.filter(data__date__lt=data_inicio)
                period_qs = period_qs.filter(data__date__gte=data_inicio)

            if data_fim:
                period_qs = period_qs.filter(data__date__lte=data_fim)

            saldo_anterior = valor_inicial + calc_saldo(before_qs)
            total_periodo = calc_saldo(period_qs)
            transacoes = period_qs.order_by('-data', '-id')
        else:
            transacoes = all_txs.order_by('-data', '-id')

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
        })


class BankAdicionarView(LoginRequiredMixin, BaseView):
    def post(self, request, pk):
        bank = get_object_or_404(Bank, pk=pk)
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
            bank=bank,
            tipo='deposito',
            descricao=descricao,
            valor=valor,
            is_entrada=True,
            observacao=observacao,
            criado_por=request.user,
        )
        messages.success(request, f'Depósito de R$ {valor:.2f} adicionado.')
        return redirect('banks:bank_statement', pk=pk)


class BankPagarView(LoginRequiredMixin, BaseView):
    def post(self, request, pk):
        bank = get_object_or_404(Bank, pk=pk)
        descricao = request.POST.get('descricao', '').strip() or 'Pagamento'
        observacao = request.POST.get('observacao', '').strip()
        try:
            valor = Decimal(request.POST.get('valor', '0').replace(',', '.'))
        except Exception:
            valor = Decimal('0')

        if valor <= 0:
            messages.error(request, 'Informe um valor válido.')
            return redirect('banks:bank_statement', pk=pk)

        BankTransaction.objects.create(
            bank=bank,
            tipo='pagamento',
            descricao=descricao,
            valor=valor,
            is_entrada=False,
            observacao=observacao,
            criado_por=request.user,
        )
        messages.success(request, f'Pagamento de R$ {valor:.2f} registrado.')
        return redirect('banks:bank_statement', pk=pk)


class BankTransferirView(LoginRequiredMixin, BaseView):
    def post(self, request, pk):
        bank = get_object_or_404(Bank, pk=pk)
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
            bank=bank,
            tipo='transferencia',
            descricao=f'Transferência para {banco_destino.nome if banco_destino else "externo"}',
            valor=valor,
            is_entrada=False,
            observacao=observacao,
            banco_destino=banco_destino,
            criado_por=request.user,
        )

        if banco_destino:
            BankTransaction.objects.create(
                bank=banco_destino,
                tipo='transferencia',
                descricao=f'Transferência de {bank.nome}',
                valor=valor,
                is_entrada=True,
                observacao=observacao,
                banco_destino=bank,
                criado_por=request.user,
            )

        messages.success(request, f'Transferência de R$ {valor:.2f} realizada.')
        return redirect('banks:bank_statement', pk=pk)
