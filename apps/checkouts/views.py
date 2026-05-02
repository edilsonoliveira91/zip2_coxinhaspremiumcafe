from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Sum, Avg, Q
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.utils import timezone
from django.db import transaction
from datetime import datetime
import json
from orders.models import Comanda, Pedido
Order = Comanda # temp fix
from decimal import Decimal

# Tente importar o modelo Checkout, se existir
try:
    from checkouts.models import Checkout
except ImportError:
    Checkout = None


class CheckoutOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    View para listagem de comandas no sistema de checkout
    """
    permission_required = 'checkouts.view_checkout'
    model = Comanda
    template_name = 'checkout_orderlist.html'
    context_object_name = 'orders'
    paginate_by = 50
    
    def get_queryset(self):
        """
        Retorna apenas comandas abertas (não entregues e não canceladas)
        Ordena por status (pronta primeiro, depois preparando, depois aguardando)
        """
        queryset = Comanda.objects.filter(
            ~Q(status='entregue') & ~Q(status='cancelada')
        ).select_related().prefetch_related('items')
        
        # Ordenação personalizada: pronta > preparando > aguardando
        return queryset.extra(
            select={
                'status_priority': """
                    CASE status 
                        WHEN 'pronta' THEN 1 
                        WHEN 'preparando' THEN 2 
                        WHEN 'aguardando' THEN 3 
                        ELSE 4 
                    END
                """
            }
        ).order_by('status_priority', 'created_at')
    
    def get_context_data(self, **kwargs):
        """
        Adiciona estatísticas e dados extras ao contexto
        """
        context = super().get_context_data(**kwargs)
        
        # Comandas abertas (não entregues e não canceladas)
        open_orders = Comanda.objects.filter(
            ~Q(status='entregue') & ~Q(status='cancelada')
        )
        
        # Estatísticas
        stats = open_orders.aggregate(
            total_orders=Count('id'),
            total_value=Sum('total_amount'),
            avg_ticket=Avg('total_amount')
        )
        
        # Adicionar total de itens para cada comanda
        orders = context['orders']
        for order in orders:
            order.total_items = order.items.aggregate(
                total=Sum('quantity')
            )['total'] or 0
        
        # Adicionar ao contexto
        context.update({
            'total_orders': stats['total_orders'] or 0,
            'total_value': stats['total_value'] or 0,
            'avg_ticket': stats['avg_ticket'] or 0,
            'page_title': 'Sistema de Checkout - Comandas Abertas'
        })
        
        return context


class CheckoutOrderPrintView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    View para impressão de comanda
    """
    permission_required = 'checkouts.view_checkout'
    template_name = 'checkout_printitens.html'
    
    def get(self, request, *args, **kwargs):
        code = self.kwargs.get('code')
        is_fiscal = request.GET.get('fiscal') == 'true'
        
        try:
            order = Comanda.objects.prefetch_related('items__product').get(code=code)
            
            # Calcular subtotal para cada item
            for item in order.items.all():
                item.subtotal = item.quantity * item.unit_price
            
            context = {
                'order': order,
                'print_time': datetime.now(),
                'is_fiscal': is_fiscal,
                'tem_nfce': order.tem_nfce
            }
            
            return render(request, self.template_name, context)
            
        except Comanda.DoesNotExist:
            return HttpResponse(f"<h1>Comanda #{code} não encontrada</h1><p>Verifique se o código está correto.</p>")
        except Exception as e:
            return HttpResponse(f"<h1>Erro ao carregar comanda</h1><p>Erro: {str(e)}</p>")

class CheckoutFinalizeView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    API para finalizar comanda e processar pagamento
    """
    permission_required = 'checkouts.add_checkout'
    
    def post(self, request, code):
        try:
            comanda = get_object_or_404(Comanda, numero=code)

            if comanda.status == 'fechada':
                return JsonResponse({
                    'success': False,
                    'message': f'Comanda já está {comanda.status}!'
                }, status=400)

            data = json.loads(request.body)
            # Suporta lista de pagamentos parciais ou pagamento único (retrocompatibilidade)
            payments_raw = data.get('payments', None)
            change_amount = float(data.get('change_amount', 0))

            VALID_METHODS = ['dinheiro', 'cartao_debito', 'cartao_credito', 'pix', 'voucher']

            if payments_raw:
                # Novo formato: lista [{method, amount}]
                payments = []
                for p in payments_raw:
                    m = p.get('method', '')
                    a = float(p.get('amount', 0))
                    if m not in VALID_METHODS:
                        return JsonResponse({'success': False, 'message': f'Método inválido: {m}'}, status=400)
                    if a <= 0:
                        return JsonResponse({'success': False, 'message': 'Valor deve ser maior que zero.'}, status=400)
                    payments.append({'method': m, 'amount': Decimal(str(a))})

                total_pago = sum(p['amount'] for p in payments)
                if total_pago < comanda.total_amount - Decimal('0.01'):
                    return JsonResponse({
                        'success': False,
                        'message': f'Valor pago (R$ {total_pago:.2f}) insuficiente para cobrir R$ {comanda.total_amount:.2f}!'
                    }, status=400)

                unique_methods = set(p['method'] for p in payments)
                payment_method = list(unique_methods)[0] if len(unique_methods) == 1 else 'parcial'
            else:
                # Formato antigo: campo único (retrocompatibilidade)
                payment_method = data.get('payment_method')
                received_amount = float(data.get('received_amount', 0))
                if payment_method not in VALID_METHODS:
                    return JsonResponse({'success': False, 'message': 'Método de pagamento inválido!'}, status=400)
                if payment_method == 'dinheiro' and received_amount < float(comanda.total_amount):
                    return JsonResponse({'success': False, 'message': 'Valor recebido é insuficiente!'}, status=400)
                payments = [{'method': payment_method, 'amount': comanda.total_amount}]

            # Fechar a comanda em transação atômica
            with transaction.atomic():
                comanda.status = 'fechada'
                comanda.save()
                comanda.pedidos.filter(status__in=['preparando', 'pronta', 'aguardando']).update(
                    status='entregue',
                    delivered_at=timezone.now()
                )

            # Criar/atualizar Checkout e CheckoutPayment fora do atomic
            if Checkout:
                try:
                    from checkouts.models import CheckoutPayment
                    notes_parts = [f'{p["method"]}: R$ {p["amount"]:.2f}' for p in payments]
                    if change_amount > 0:
                        notes_parts.append(f'Troco: R$ {change_amount:.2f}')

                    checkout, _ = Checkout.objects.update_or_create(
                        comanda=comanda,
                        defaults=dict(
                            subtotal=comanda.total_amount,
                            desconto=Decimal('0.00'),
                            taxa_servico=Decimal('0.00'),
                            total=comanda.total_amount,
                            payment_method=payment_method,
                            status='aprovado',
                            processed_by=request.user,
                            processed_at=timezone.now(),
                            notes=' | '.join(notes_parts),
                        )
                    )
                    # Recriar registros individuais de pagamento
                    checkout.payments.all().delete()
                    for p in payments:
                        CheckoutPayment.objects.create(
                            checkout=checkout,
                            payment_method=p['method'],
                            amount=p['amount'],
                        )
                except Exception as e:
                    print(f"Erro ao criar/atualizar registro de checkout: {e}")

            return JsonResponse({
                'success': True,
                'message': f'Comanda #{code} finalizada com sucesso!',
            })
                
        except Comanda.DoesNotExist:
            return JsonResponse({'success': False, 'message': f'Comanda #{code} não encontrada!'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Erro interno: {str(e)}'}, status=500)


class AlterarMetodoPagamentoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Altera o método de pagamento de um Checkout já finalizado.
    Requer permissão de add_checkout (mesma do caixa).
    """
    permission_required = 'checkouts.add_checkout'

    def post(self, request, code):
        try:
            comanda = get_object_or_404(Comanda, numero=code)
            if comanda.status != 'fechada':
                return JsonResponse({'success': False, 'message': 'Comanda não está fechada.'}, status=400)

            checkout = get_object_or_404(Checkout, comanda=comanda)

            data = json.loads(request.body)
            novo_metodo = data.get('payment_method', '').strip()

            metodos_validos = [m[0] for m in Checkout.PAYMENT_METHOD_CHOICES]
            if novo_metodo not in metodos_validos:
                return JsonResponse({'success': False, 'message': 'Método de pagamento inválido.'}, status=400)

            metodo_antigo = checkout.get_payment_method_display()
            checkout.payment_method = novo_metodo
            checkout.notes = (checkout.notes or '') + f'\n[Alterado por {request.user} em {timezone.now().strftime("%d/%m/%Y %H:%M")}]: {metodo_antigo} → {checkout.get_payment_method_display()}'
            checkout.save(update_fields=['payment_method', 'notes'])

            return JsonResponse({
                'success': True,
                'message': f'Método de pagamento alterado para {checkout.get_payment_method_display()}.',
                'payment_method_display': checkout.get_payment_method_display(),
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Erro interno: {str(e)}'}, status=500)


class FechamentoCaixaView(LoginRequiredMixin, View):
    """
    Tela de fechamento de caixa.
    - Usuário is_caixa vê sua sessão aberta + seus próprios fechamentos
    - Superuser/staff vê todos os fechamentos
    """
    template_name = 'checkouts/fechamento_caixa.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        if not (request.user.is_caixa or request.user.is_superuser or request.user.is_staff):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from checkouts.models import SessaoCaixa
        usuario = request.user

        # Sessão atualmente aberta (apenas do próprio usuário)
        sessao_aberta = None
        if usuario.is_caixa:
            sessao_aberta = SessaoCaixa.objects.filter(
                usuario=usuario, status='aberta'
            ).first()

        # Lista de fechamentos
        if usuario.is_superuser or usuario.is_staff:
            fechamentos = SessaoCaixa.objects.filter(status='fechada').select_related('usuario')
        else:
            fechamentos = SessaoCaixa.objects.filter(usuario=usuario, status='fechada')

        context = {
            'sessao_aberta': sessao_aberta,
            'fechamentos': fechamentos,
        }
        if sessao_aberta:
            context['totais_por_metodo'] = sessao_aberta.totais_por_metodo()
            context['total_sessao'] = sessao_aberta.total()

        return render(request, self.template_name, context)


class FechamentoCaixaFecharView(LoginRequiredMixin, View):
    """
    POST: fecha a sessão de caixa aberta do usuário logado.
    """

    def post(self, request):
        from checkouts.models import SessaoCaixa
        from django.utils import timezone

        if not request.user.is_caixa:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied

        sessao = SessaoCaixa.objects.filter(
            usuario=request.user, status='aberta'
        ).first()

        if sessao:
            sessao.fechada_em = timezone.now()
            sessao.status = 'fechada'
            sessao.save()
            from django.contrib import messages
            messages.success(request, 'Caixa fechado com sucesso!')
        else:
            from django.contrib import messages
            messages.info(request, 'Nenhum caixa aberto encontrado.')

        from django.shortcuts import redirect
        return redirect('checkouts:fechamento_caixa')


class FechamentoCaixaDetalheView(LoginRequiredMixin, View):
    """
    GET: retorna JSON com os totais por método de pagamento de uma sessão fechada.
    Usado pelo modal de visualização.
    """

    def get(self, request, pk):
        from checkouts.models import SessaoCaixa
        from django.http import JsonResponse

        sessao = SessaoCaixa.objects.filter(pk=pk).first()
        if not sessao:
            return JsonResponse({'error': 'Sessão não encontrada'}, status=404)

        # Apenas o próprio usuário ou admin pode ver
        if not (request.user.is_superuser or request.user.is_staff or sessao.usuario == request.user):
            return JsonResponse({'error': 'Sem permissão'}, status=403)

        LABELS = {
            'dinheiro': 'Dinheiro',
            'cartao_debito': 'Cartão de Débito',
            'cartao_credito': 'Cartão de Crédito',
            'pix': 'PIX',
            'voucher': 'Voucher',
        }

        totais = []
        for item in sessao.totais_por_metodo():
            totais.append({
                'metodo': LABELS.get(item['payment_method'], item['payment_method']),
                'quantidade': item['quantidade'],
                'total': float(item['total'] or 0),
            })

        return JsonResponse({
            'usuario': sessao.usuario.username,
            'aberta_em': sessao.aberta_em.strftime('%d/%m/%Y %H:%M'),
            'fechada_em': sessao.fechada_em.strftime('%d/%m/%Y %H:%M') if sessao.fechada_em else '-',
            'total': float(sessao.total()),
            'totais': totais,
        })
