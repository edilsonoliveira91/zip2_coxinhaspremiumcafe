---
name: project-architecture
description: Mapa das entidades financeiras do Coxinhas Premium Café e fluxo de caixa completo
metadata:
  type: project
---

## Entidades Financeiras Principais

- **Comanda** (orders/models.py): entidade raiz. Tem total_amount, status, forma_pagamento_kiosk.
- **Pedido / PedidoItem**: itens que compõem a comanda. update_total() propaga de PedidoItem → Pedido → Comanda.
- **ComandaPartialPayment**: pagamentos parciais registrados enquanto a comanda ainda está aberta (apagados ao fechar).
- **Checkout** (checkouts/models.py): 1:1 com Comanda. Registra o pagamento final (subtotal, desconto, taxa, total, payment_method, processed_at).
- **CheckoutPayment**: detalhamento de cada método num checkout parcial (multi-método).
- **SessaoCaixa**: sessão de turno do operador; criada via signal ao primeiro Checkout aprovado.
- **Sangria** (financials/models.py): retiradas de dinheiro do caixa. Vinculada ao usuário.
- **FechamentoCaixaDiario**: arquiva totais do dia (dinheiro, débito, crédito, pix, sangrias, total_final).
- **AjusteFechamentoCaixaDiario**: auditoria de edições manuais em FechamentoCaixaDiario.
- **CaixaAdm (Malote)**: 1:1 com FechamentoCaixaDiario. Enviado pelo operador para ADM.
- **DespesaMalote**: despesas vinculadas ao malote (descontadas do total_dinheiro).
- **CaixaAdmTransferencia**: registro de transferências do caixa físico para um banco.
- **Bank / BankTransaction** (banks/models.py): bancos e transações bancárias.

## Fluxo de Caixa

1. Cliente abre comanda → status em_uso
2. Garçom/kiosk adiciona pedidos → PedidoItem → update_total() sobe até Comanda.total_amount
3. Caixa finaliza comanda → CheckoutFinalizeView:
   - Comanda: status = 'fechada'
   - Pedidos pendentes: status = 'entregue'
   - Checkout criado (status='aprovado', processed_at=timezone.now())
   - CheckoutPayment criados por método
   - ComandaPartialPayment apagados
   - Signal dispara: SessaoCaixa aberta para operador is_caixa
4. Sangrias registradas manualmente (CriarSangriaView)
5. ADM fecha o dia: RealizarFechamentoCaixaView → FechamentoCaixaDiario salvo
6. Operador envia malote: EnviarMaloteView → CaixaAdm criado
7. ADM confere malote: ConcluirMaloteView → CaixaAdm.concluido=True
8. ADM registra despesas: DespesaMalote (descontadas do dinheiro)
9. ADM transfere para banco: TransferirCaixaAdmParaBancoView → BankTransaction + CaixaAdmTransferencia
10. Conciliação bancária: ConciliarTransferenciaView → antecipa BankTransaction para hoje, marca conciliado=True

## Referência de Campos-Chave

- `Checkout.processed_at` → campo principal de data financeira (usado em todos os filtros do financeiro)
- `Comanda.updated_at` → usado em alguns filtros de fechamento (inconsistência vs processed_at)
- `FechamentoCaixaDiario.data` → DateField único por dia
- `CaixaAdmTransferencia.data_caixa` → data do caixa (pode diferir da data de liquidação)
- `CaixaAdmTransferencia.data_prevista_liquidacao` → baseada em dias de pinpad ativo

**Why:** Documentar para futuras conversas evitar confusão entre campos de data.
**How to apply:** Ao analisar queries de filtro de data, verificar se usa processed_at (correto) ou updated_at (inconsistente).
