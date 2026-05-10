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


# ─── Estado global da emissão em lote ────────────────────────────────────────
_lote_state = {
    'running': False,
    'total': 0,
    'processados': 0,
    'sucesso': 0,
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

        # Busca todas as comandas fechadas/cortesia sem NFC-e
        pendentes = list(Comanda.objects.filter(
            status__in=['fechada', 'cortesia'],
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
                'erros': [],
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
