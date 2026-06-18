---
name: project-known-issues
description: Bugs confirmados e potenciais identificados na análise de junho/2026
metadata:
  type: project
---

## Bugs Confirmados / Alta Probabilidade

1. **Inconsistência de filtro de data no fechamento** (views.py:692):
   - `RealizarFechamentoCaixaView` filtra por `comanda__updated_at__date` mas todo o resto usa `processed_at__date`.
   - Risco: fechamento pode gravar valor diferente do extrato ao vivo.

2. **SangriaView não considera pagamentos parciais em dinheiro** (views.py:251-253):
   - `dinheiro_recebido_hoje` filtra `payment_method='dinheiro'` no Checkout, mas não soma CheckoutPayment com método dinheiro em checkouts parciais.
   - Resultado: dinheiro disponível pode aparecer menor que o real.

3. **ConciliarTransferenciaView — busca frágil da BankTransaction** (views.py:1335-1341):
   - Filtra por banco + valor + descrição + data > hoje. Se houver duas transferências com mesmo valor/descrição/banco, ambas serão atualizadas. Não há vínculo direto (FK) entre CaixaAdmTransferencia e BankTransaction.

4. **total_a_receber em CaixaAdmView não desconta despesas** (views.py:1002-1004):
   - Card "A Receber" soma `fechamento__total_final` dos malotes pendentes SEM descontar DespesaMalote dos malotes pendentes. Só desconta nos malotes concluídos.

5. **total_transferencias em ConferenciaCaixaView sem filtro de conciliação** (views.py:1458-1460):
   - Soma TODAS as transferências independente de estarem conciliadas. Se uma transferência for cancelada ou duplicada manualmente, o total disponível estará errado.

## Riscos Menores

6. **ExtratoAbertosAPIView — closure de _soma no loop** (views.py:788):
   - `_soma` definida dentro de loop for com `_ckts=checkouts, _pids=parcial_ids` como defaults. Correto, mas padrão frágil.

7. **CheckoutFinalizeView — criação de Checkout fora do atomic** (views.py:213-246):
   - Comanda é fechada dentro de `transaction.atomic()`, mas Checkout é criado FORA. Se o segundo bloco falhar (e.g., erro de integridade), comanda fica fechada sem Checkout.

8. **RegistrarDespesaDiaView cria FechamentoCaixaDiario stub zerado** (views.py:1153-1157):
   - Cria fechamento com todos os valores zerados se não existir. Esse stub aparece no historico com total R$0,00.

9. **Sangria: permissão dupla na exclusão** (views.py:404-419):
   - `ExcluirSangriaView` requer `financials.can_add_sangria` para acessar a view, depois verifica `financials.delete_sangria`. Qualquer usuário com can_add_sangria que não tenha delete_sangria recebe 403 após já ter passado pelo dispatch.

10. **CriarSangriaView decorada com @csrf_exempt** (views.py:276):
    - Usa csrf_exempt + LoginRequiredMixin. O CSRF está desabilitado — risco de CSRF em navegadores com cookies de sessão ativos.

**Why:** Documentado para orientar futuras correções prioritárias.
**How to apply:** Ao trabalhar em qualquer dessas áreas, verificar se o bug ainda existe antes de mencionar ao usuário.
