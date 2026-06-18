---
name: project-calc-patterns
description: Padrões de cálculo monetário, biblioteca Decimal, lógica de pagamentos parciais
metadata:
  type: project
---

## Biblioteca Decimal

- O projeto usa `from decimal import Decimal` consistentemente. Não usa float para valores monetários no backend.
- Arredondamento: `.quantize(Decimal('0.01'))` usado apenas em cálculo de impostos e comissões. Não usado nas somas principais.
- Risco: `CheckoutFinalizeView` converte `float(p.get('amount', 0))` para `Decimal(str(a))` — correto.

## Lógica de Pagamentos Parciais

- Um Checkout com payment_method='parcial' tem N registros CheckoutPayment.
- Filtros financeiros sempre fazem: (checkouts não-parciais por Checkout.total) + (checkouts parciais por CheckoutPayment.amount).
- Essa lógica está replicada em: FinancialDashboardView._sum_method, ExtratoView._soma, FechamentoCaixaDiarioView._calcular_extrato, ExtratoAbertosAPIView._soma, SessaoCaixa.totais_por_metodo, RelatorioPagamentosCSVView.
- Voucher aparece no CSV mas não no dashboard — inconsistência conhecida.

## Cálculo do Total Disponível (Conferencia Caixa)

```python
total_disponivel = max(total_geral - total_transferencias, 0)
```
- total_geral = soma de FechamentoCaixaDiario.total_final de TODOS os fechamentos
- total_transferencias = soma de CaixaAdmTransferencia.valor de TODAS as transferências (sem filtro de banco ou data)

## Cálculo de Dinheiro Disponível (Sangria View)

```python
dinheiro_disponivel = valor_inicial + dinheiro_recebido_hoje - sangrias_hoje
```
- dinheiro_recebido_hoje: filtra checkouts_hoje com payment_method='dinheiro' mas NÃO considera pagamentos parciais com dinheiro.

## Fechamento de Caixa vs Dashboard — Diferença de filtro

- Dashboard: filtra por `Checkout.processed_at__date`
- RealizarFechamentoCaixaView: filtra por `comanda__updated_at__date` (diferente!)
- Essa inconsistência pode causar valores diferentes entre o extrato ao vivo e o fechamento gravado.
