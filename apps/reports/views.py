from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import TemplateView, View
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Q
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from orders.models import Comanda, Pedido, PedidoItem
from products.models import Product
from config.models import Garcom
import threading
import time
import json
import os
import zipfile
import io


class BaseReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Base para todas as views de relatórios"""
    permission_required = 'orders.view_order'


class NFCeReportView(BaseReportView):
    """Relatório de NFCe emitidas (Cupons Fiscais)"""
    template_name = 'reports/nfce_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Filtros de data
        data_inicio = self.request.GET.get('data_inicio', '')
        data_fim = self.request.GET.get('data_fim', '')
        numero_comanda = self.request.GET.get('numero_comanda', '').strip()

        today = timezone.localtime().date()
        if not data_inicio:
            data_inicio = today.strftime('%Y-%m-%d')
        if not data_fim:
            data_fim = today.strftime('%Y-%m-%d')

        # Busca comandas com NFCe emitida (fechada ou cortesia)
        queryset = Comanda.objects.filter(
            status__in=['fechada', 'cortesia'],
            nfce_numero__isnull=False,
            nfce_emitida_em__date__gte=data_inicio,
            nfce_emitida_em__date__lte=data_fim,
        )

        if numero_comanda:
            queryset = queryset.filter(numero__icontains=numero_comanda)

        queryset = queryset.order_by('-nfce_emitida_em')

        # Estatísticas
        total_cupons = queryset.count()
        total_valor = queryset.aggregate(total=Sum('total_amount'))['total'] or 0
        valor_medio = total_valor / total_cupons if total_cupons > 0 else 0

        # Comandas finalizadas sem NFC-e no período
        sem_nfce_qs = Comanda.objects.filter(
            status__in=['fechada', 'cortesia'],
            nfce_emitida_em__isnull=True,
            created_at__date__gte=data_inicio,
            created_at__date__lte=data_fim,
        )
        if numero_comanda:
            sem_nfce_qs = sem_nfce_qs.filter(numero__icontains=numero_comanda)
        sem_nfce_qs = sem_nfce_qs.order_by('-created_at')

        context.update({
            'nfce_list': queryset,
            'sem_nfce_list': sem_nfce_qs,
            'total_cupons': total_cupons,
            'total_valor': total_valor,
            'valor_medio': valor_medio,
            'total_sem_nfce': sem_nfce_qs.count(),
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'numero_comanda': numero_comanda,
        })

        return context


class SalesReportView(BaseReportView):
    """Relatório de Vendas"""
    template_name = 'reports/sales_report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filtros de data
        data_inicio = self.request.GET.get('data_inicio')
        data_fim = self.request.GET.get('data_fim')
        
        # Se não informado, últimos 30 dias
        if not data_inicio:
            data_inicio = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not data_fim:
            data_fim = timezone.now().strftime('%Y-%m-%d')
        
        # Busca vendas
        vendas_queryset = Comanda.objects.filter(
            status='DELIVERED',
            created_at__date__gte=data_inicio,
            created_at__date__lte=data_fim
        ).order_by('-created_at')
        
        # Produtos mais vendidos
        produtos_vendidos = PedidoItem.objects.filter(
            order__in=vendas_queryset
        ).values(
            'product__name'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('quantity') * Sum('unit_price')
        ).order_by('-total_quantity')[:10]
        
        # Estatísticas
        total_vendas = vendas_queryset.count()
        total_faturamento = vendas_queryset.aggregate(total=Sum('total_amount'))['total'] or 0
        ticket_medio = total_faturamento / total_vendas if total_vendas > 0 else 0
        
        # Vendas por dia
        vendas_por_dia = vendas_queryset.extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            total_vendas=Count('id'),
            total_valor=Sum('total_amount')
        ).order_by('day')
        
        context.update({
            'vendas_list': vendas_queryset,
            'produtos_vendidos': produtos_vendidos,
            'vendas_por_dia': vendas_por_dia,
            'total_vendas': total_vendas,
            'total_faturamento': total_faturamento,
            'ticket_medio': ticket_medio,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        })
        
        return context


class SellsReportView(BaseReportView):
    """Relatório de Vendas por Produto — lista produto + quantidade vendida no período"""
    template_name = 'reports/sells_reports.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.db.models import F, DecimalField, ExpressionWrapper, Case, When, Value
        from decimal import Decimal as _Dec

        today = timezone.localtime().date()
        data_inicio = self.request.GET.get('data_inicio', '').strip() or today.strftime('%Y-%m-%d')
        data_fim = self.request.GET.get('data_fim', '').strip() or today.strftime('%Y-%m-%d')
        q = self.request.GET.get('q', '').strip()

        # Quantidade: considera fechadas + cortesias (produto realmente saiu)
        # Valor financeiro: apenas fechadas (alinhado com o Extrato)
        items_qs = PedidoItem.objects.filter(
            pedido__comanda__status__in=['fechada', 'cortesia'],
            pedido__comanda__updated_at__date__gte=data_inicio,
            pedido__comanda__updated_at__date__lte=data_fim,
            pedido__status__in=['aguardando', 'preparando', 'pronta', 'entregue'],
        )
        if q:
            items_qs = items_qs.filter(
                Q(product__name__icontains=q) |
                Q(opcional_obrigatorio__name__icontains=q)
            )

        produtos = (
            items_qs
            .values(
                'product__id',
                'product__name',
                'product__category',
                'opcional_obrigatorio__id',
                'opcional_obrigatorio__name',
            )
            .annotate(
                qtd_vendida=Sum('quantity'),
                total_faturado=Sum(
                    Case(
                        When(
                            pedido__comanda__status='fechada',
                            then=ExpressionWrapper(
                                F('quantity') * F('unit_price'),
                                output_field=DecimalField()
                            ),
                        ),
                        default=Value(_Dec('0.00')),
                        output_field=DecimalField(),
                    )
                ),
            )
            .order_by('-qtd_vendida', 'product__name', 'opcional_obrigatorio__name')
        )

        produtos = list(produtos)
        total_itens = sum(p['qtd_vendida'] or 0 for p in produtos)
        total_faturado = sum(p['total_faturado'] or 0 for p in produtos)

        groups_map = {}
        for row in produtos:
            product_id = row.get('product__id')
            group = groups_map.get(product_id)
            if not group:
                group = {
                    'group_key': f'p{product_id}',
                    'product__id': product_id,
                    'product__name': row.get('product__name'),
                    'product__category': row.get('product__category'),
                    'qtd_vendida': 0,
                    'total_faturado': 0,
                    'variacoes': [],
                }
                groups_map[product_id] = group

            group['qtd_vendida'] += row.get('qtd_vendida') or 0
            group['total_faturado'] += row.get('total_faturado') or 0
            group['variacoes'].append({
                'name': row.get('opcional_obrigatorio__name') or 'Sem variação',
                'qtd_vendida': row.get('qtd_vendida') or 0,
                'total_faturado': row.get('total_faturado') or 0,
            })

        grouped_products = sorted(groups_map.values(), key=lambda x: x['qtd_vendida'], reverse=True)

        context.update({
            'produtos': produtos,
            'grouped_products': grouped_products,
            'total_itens': total_itens,
            'total_faturado': total_faturado,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'q': q,
        })
        return context

class CanceledCortesiaReportView(BaseReportView):
    """Relatório de cancelamentos e cortesias de comandas."""
    template_name = 'reports/canceledcortesia_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = timezone.localtime().date()
        data_inicio = self.request.GET.get('data_inicio', '').strip() or today.strftime('%Y-%m-%d')
        data_fim = self.request.GET.get('data_fim', '').strip() or today.strftime('%Y-%m-%d')
        tipo = self.request.GET.get('tipo', '').strip()
        numero_comanda = self.request.GET.get('numero_comanda', '').strip()

        queryset = Comanda.objects.filter(
            status__in=['cancelada', 'cortesia'],
            updated_at__date__gte=data_inicio,
            updated_at__date__lte=data_fim,
        ).order_by('-updated_at', '-created_at')

        if tipo in ['cancelada', 'cortesia']:
            queryset = queryset.filter(status=tipo)
        if numero_comanda:
            queryset = queryset.filter(numero__icontains=numero_comanda)

        registros = []
        for comanda in queryset:
            usuario_obj = comanda.updated_by
            if not usuario_obj and comanda.status == 'cancelada':
                try:
                    checkout = comanda.checkout
                except Exception:
                    checkout = None
                if checkout and checkout.processed_by:
                    usuario_obj = checkout.processed_by

            if usuario_obj:
                usuario = usuario_obj.get_full_name().strip() or usuario_obj.get_username()
            else:
                usuario = '—'

            registros.append({
                'id': comanda.id,
                'numero': comanda.numero,
                'usuario': usuario,
                'tipo': comanda.status,
                'tipo_label': 'Cancelamento' if comanda.status == 'cancelada' else 'Cortesia',
                'abertura_em': timezone.localtime(comanda.created_at).strftime('%d/%m/%Y %H:%M') if comanda.created_at else '—',
                'cancelamento_em': timezone.localtime(comanda.updated_at).strftime('%d/%m/%Y %H:%M') if comanda.updated_at else '—',
                'observacao': comanda.motivo_cancelamento or '—',
                'total_amount': comanda.total_amount or 0,
            })

        total_registros = len(registros)
        total_cancelamentos = queryset.filter(status='cancelada').count()
        total_cortesias = queryset.filter(status='cortesia').count()
        total_valor = queryset.aggregate(total=Sum('total_amount'))['total'] or 0

        context.update({
            'registros': registros,
            'total_registros': total_registros,
            'total_cancelamentos': total_cancelamentos,
            'total_cortesias': total_cortesias,
            'total_valor': total_valor,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'tipo': tipo,
            'numero_comanda': numero_comanda,
        })
        return context


# ─── Estado global da emissão em lote ────────────────────────────────────────
_lote_state = {
    'running': False,
    'total': 0,
    'processados': 0,
    'sucesso': 0,
    'emitidas': [],  # list of {'comanda': str, 'nfce': str}
    'erros': [],  # list of {'comanda': str, 'erro': str}
    'completed_at': None,  # ISO timestamp do fim do lote
}
_lote_lock = threading.Lock()


class EmitirLoteView(LoginRequiredMixin, View):
    """Inicia emissão em lote de NFC-e para comandas sem cupom fiscal."""

    def post(self, request, *args, **kwargs):
        global _lote_state

        with _lote_lock:
            if _lote_state['running']:
                return JsonResponse({'ok': False, 'message': 'Já existe uma emissão em lote em andamento.'})

        # Busca apenas comandas FECHADAS sem NFC-e (cortesia e canceladas não emitem cupom fiscal)
        pendentes = list(Comanda.objects.filter(
            status='fechada',
            nfce_numero__isnull=True,
        ).order_by('created_at'))

        if not pendentes:
            return JsonResponse({'ok': True, 'message': 'Nenhuma comanda pendente de NFC-e.'})

        with _lote_lock:
            _lote_state = {
                'running': True,
                'total': len(pendentes),
                'processados': 0,
                'sucesso': 0,
                'emitidas': [],
                'erros': [],
                'completed_at': None,
            }

        def _worker(comandas, user_id):
            global _lote_state
            from companys.models import Company  # import local para evitar circular
            from utils.nfce_service import NFCeService
            try:
                empresa = Company.objects.filter(ativa=True).first()
                if not empresa:
                    with _lote_lock:
                        _lote_state['running'] = False
                        _lote_state['erros'].append({'comanda': '—', 'erro': 'Empresa não encontrada.'})
                    return

                for comanda in comandas:
                    try:
                        service = NFCeService(empresa)
                        resultado = service.emitir_nfce(comanda)
                        if resultado.get('sucesso'):
                            comanda.nfce_numero = resultado['numero_nfce']
                            comanda.nfce_chave = resultado['chave_acesso']
                            comanda.nfce_protocolo = resultado['protocolo']
                            comanda.nfce_emitida_em = timezone.now()
                            comanda.nfce_xml_path = resultado.get('xml_path')
                            comanda.save(update_fields=[
                                'nfce_numero', 'nfce_chave', 'nfce_protocolo',
                                'nfce_emitida_em', 'nfce_xml_path'
                            ])
                            with _lote_lock:
                                _lote_state['sucesso'] += 1
                                _lote_state['emitidas'].append({
                                    'comanda': str(comanda.numero),
                                    'nfce': str(resultado.get('numero_nfce') or ''),
                                })
                        else:
                            with _lote_lock:
                                _lote_state['erros'].append({
                                    'comanda': str(comanda.numero),
                                    'erro': resultado.get('erro', 'Erro desconhecido'),
                                })
                    except Exception as e:
                        with _lote_lock:
                            _lote_state['erros'].append({
                                'comanda': str(comanda.numero),
                                'erro': str(e),
                            })
                    finally:
                        with _lote_lock:
                            _lote_state['processados'] += 1
                        time.sleep(1)  # evita rejeição por frequência na SEFAZ

            finally:
                with _lote_lock:
                    _lote_state['running'] = False
                    _lote_state['completed_at'] = timezone.now().isoformat()

        t = threading.Thread(target=_worker, args=(pendentes, request.user.id), daemon=True)
        t.start()

        return JsonResponse({
            'ok': True,
            'total': len(pendentes),
            'message': f'Emissão em lote iniciada para {len(pendentes)} comanda(s).',
        })


class EmitirLoteStatusView(LoginRequiredMixin, View):
    """Retorna o estado atual da emissão em lote (polling)."""

    def get(self, request, *args, **kwargs):
        with _lote_lock:
            state = dict(_lote_state)
        return JsonResponse(state)


class DownloadXMLZipView(LoginRequiredMixin, View):
    """Gera e retorna um ZIP com os XMLs de NFC-e do período filtrado."""

    def get(self, request, *args, **kwargs):
        data_inicio = request.GET.get('data_inicio', '')
        data_fim = request.GET.get('data_fim', '')

        today = timezone.localtime().date().strftime('%Y-%m-%d')
        if not data_inicio:
            data_inicio = today
        if not data_fim:
            data_fim = today

        comandas = Comanda.objects.filter(
            status__in=['fechada', 'cortesia'],
            nfce_numero__isnull=False,
            nfce_xml_path__isnull=False,
            nfce_emitida_em__date__gte=data_inicio,
            nfce_emitida_em__date__lte=data_fim,
        ).exclude(nfce_xml_path='')

        buffer = io.BytesIO()
        count = 0
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for comanda in comandas:
                xml_path = comanda.nfce_xml_path
                if xml_path and os.path.exists(xml_path):
                    filename = os.path.basename(xml_path)
                    with open(xml_path, 'r', encoding='utf-8') as xf:
                        zf.writestr(filename, xf.read())
                    count += 1

        if count == 0:
            return HttpResponse(
                'Nenhum XML disponível para o período selecionado.',
                status=404,
                content_type='text/plain'
            )

        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="nfce_xml_{data_inicio}_{data_fim}.zip"'
        return response


class CozinhaReportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Relatório de performance da cozinha: tempos por pedido entregue."""
    permission_required = 'orders.view_order'
    template_name = 'reports/cozinha_report.html'

    def handle_no_permission(self):
        from django.shortcuts import redirect
        return redirect('accounts:login')

    def get(self, request):
        from django.db.models import F, ExpressionWrapper, DurationField
        today = timezone.localtime().date()

        data_inicio = request.GET.get('data_inicio', today.strftime('%Y-%m-%d'))
        data_fim    = request.GET.get('data_fim',    today.strftime('%Y-%m-%d'))

        try:
            dt_inicio = timezone.make_aware(datetime.strptime(data_inicio, '%Y-%m-%d'))
            dt_fim    = timezone.make_aware(datetime.strptime(data_fim, '%Y-%m-%d') + timedelta(days=1))
        except ValueError:
            dt_inicio = timezone.make_aware(datetime(today.year, today.month, today.day))
            dt_fim    = dt_inicio + timedelta(days=1)

        pedidos = (
            Pedido.objects
            .filter(
                status='entregue',
                delivered_at__gte=dt_inicio,
                delivered_at__lt=dt_fim,
                items__product__destino_producao='cozinha',
            )
            .distinct()
            .select_related('comanda')
            .prefetch_related('items__product')
            .order_by('-delivered_at')
        )

        rows = []
        total_segundos = 0
        count_com_tempo = 0

        for p in pedidos:
            t_feito    = timezone.localtime(p.created_at)  if p.created_at   else None
            t_impresso = timezone.localtime(p.started_at)  if p.started_at   else None
            t_entregue = timezone.localtime(p.delivered_at) if p.delivered_at else None

            # Tempo total: criação → entrega
            if t_feito and t_entregue:
                delta = p.delivered_at - p.created_at
                secs  = int(delta.total_seconds())
                total_segundos += secs
                count_com_tempo += 1
                mins, seg = divmod(secs, 60)
                horas, mins = divmod(mins, 60)
                tempo_total = f"{horas:02d}:{mins:02d}:{seg:02d}" if horas else f"{mins:02d}:{seg:02d}"
            else:
                tempo_total = "—"
                secs = None

            # Tempo feito → impresso
            if t_feito and t_impresso:
                d2 = p.started_at - p.created_at
                s2 = int(d2.total_seconds())
                m2, s2r = divmod(s2, 60)
                h2, m2r = divmod(m2, 60)
                tempo_prep = f"{h2:02d}:{m2r:02d}:{s2r:02d}" if h2 else f"{m2r:02d}:{s2r:02d}"
            else:
                tempo_prep = "—"

            # Tempo impresso → entregue
            if t_impresso and t_entregue:
                d3 = p.delivered_at - p.started_at
                s3 = int(d3.total_seconds())
                m3, s3r = divmod(s3, 60)
                h3, m3r = divmod(m3, 60)
                tempo_entrega = f"{h3:02d}:{m3r:02d}:{s3r:02d}" if h3 else f"{m3r:02d}:{s3r:02d}"
            else:
                tempo_entrega = "—"

            rows.append({
                'pedido_seq': p.pedido_seq,
                'comanda_numero': p.comanda.numero,
                'cliente_nome': p.comanda.cliente_nome or '',
                'data_pedido': t_feito.strftime('%d/%m/%Y') if t_feito else '—',
                't_recebido':  t_feito.strftime('%H:%M:%S') if t_feito else '—',
                't_impresso': t_impresso.strftime('%H:%M:%S') if t_impresso else '—',
                't_entregue': t_entregue.strftime('%H:%M:%S') if t_entregue else '—',
                'tempo_prep': tempo_prep,
                'tempo_entrega': tempo_entrega,
                'tempo_total': tempo_total,
                'tempo_total_secs': secs,
                'itens_json': json.dumps([
                    {'qty': item.quantity, 'nome': item.product.name, 'obs': item.observations or ''}
                    for item in p.items.all()
                    if item.product.destino_producao == 'cozinha'
                ]),
            })

        # Tempo médio geral
        if count_com_tempo > 0:
            media_secs = total_segundos // count_com_tempo
            mm, ms = divmod(media_secs, 60)
            hm, mmr = divmod(mm, 60)
            media_str = f"{hm:02d}:{mmr:02d}:{ms:02d}" if hm else f"{mmr:02d}:{ms:02d}"
        else:
            media_str = "—"

        return render(request, self.template_name, {
            'rows': rows,
            'total': len(rows),
            'media_tempo': media_str,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
        })


class PedidosReportView(BaseReportView):
    """Relatório de todos os pedidos realizados"""
    template_name = 'reports/pedidos_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = timezone.localtime().date()
        data_inicio = self.request.GET.get('data_inicio', '') or today.strftime('%Y-%m-%d')
        data_fim = self.request.GET.get('data_fim', '') or today.strftime('%Y-%m-%d')
        status_filtro = self.request.GET.get('status', '')
        atendente_filtro = self.request.GET.get('atendente', '').strip()
        q = self.request.GET.get('q', '').strip()

        qs = (
            Pedido.objects
            .select_related('comanda')
            .prefetch_related('items')
            .annotate(qtd_itens=Sum('items__quantity'))
            .filter(created_at__date__gte=data_inicio, created_at__date__lte=data_fim)
        )

        if status_filtro:
            qs = qs.filter(status=status_filtro)

        if atendente_filtro.isdigit():
            qs = qs.filter(atendente_numero=int(atendente_filtro))

        if q:
            qs = qs.filter(
                Q(comanda__numero__icontains=q) |
                Q(comanda__cliente_nome__icontains=q) |
                Q(atendente_numero__icontains=q)
            )

        qs = qs.order_by('-created_at')

        total_pedidos = qs.count()
        total_valor = qs.aggregate(t=Sum('total_amount'))['t'] or 0
        total_itens = qs.aggregate(t=Sum('items__quantity'))['t'] or 0

        garcons = Garcom.objects.order_by('numero')
        garcom_map = {g.numero: g.nome for g in garcons}

        pedidos = list(qs)
        for p in pedidos:
            p.nome_atendente = garcom_map.get(p.atendente_numero) if p.atendente_numero else None

        context.update({
            'pedidos': pedidos,
            'total_pedidos': total_pedidos,
            'total_valor': total_valor,
            'total_itens': total_itens,
            'data_inicio': data_inicio,
            'data_fim': data_fim,
            'status_filtro': status_filtro,
            'atendente_filtro': atendente_filtro,
            'q': q,
            'status_choices': Pedido.STATUS_CHOICES,
            'garcons': garcons,
        })
        return context
