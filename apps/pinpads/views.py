from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Q
from django.http import JsonResponse
from django.views import View
from decimal import Decimal, InvalidOperation
from .models import Pinpad, BandeiraPinpad
from .forms import PinpadForm
import json
import logging

logger = logging.getLogger(__name__)


class PinpadListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = 'pinpads.view_pinpad'
    model = Pinpad
    template_name = 'pinpad_list.html'
    context_object_name = 'pinpads'
    paginate_by = 12

    def get_queryset(self):
        qs = Pinpad.objects.prefetch_related('bandeiras').select_related('created_by')
        search = self.request.GET.get('search', '').strip()
        if search:
            qs = qs.filter(name__icontains=search)
        active = self.request.GET.get('active', '')
        if active == 'true':
            qs = qs.filter(is_active=True)
        elif active == 'false':
            qs = qs.filter(is_active=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        all_p = Pinpad.objects.all()
        ctx.update({
            'total_pinpads': all_p.count(),
            'active_pinpads': all_p.filter(is_active=True).count(),
            'current_search': self.request.GET.get('search', ''),
            'current_active': self.request.GET.get('active', ''),
        })
        return ctx


class PinpadCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'pinpads.add_pinpad'
    template_name = 'pinpad_form.html'

    def get(self, request):
        return render(request, self.template_name, {'form': PinpadForm(), 'bandeiras': []})

    def post(self, request):
        form = PinpadForm(request.POST)
        if form.is_valid():
            pinpad = form.save(commit=False)
            pinpad.created_by = request.user
            pinpad.save()
            _save_bandeiras(request, pinpad)
            messages.success(request, f'Pinpad "{pinpad.name}" criado com sucesso!')
            return redirect('pinpads:pinpad_list')
        return render(request, self.template_name, {
            'form': form,
            'bandeiras': _parse_bandeiras_from_post(request),
        })


class PinpadUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'pinpads.change_pinpad'
    template_name = 'pinpad_form.html'

    def get(self, request, pk):
        pinpad = get_object_or_404(Pinpad, pk=pk)
        form = PinpadForm(instance=pinpad)
        bandeiras = list(pinpad.bandeiras.values('nome', 'taxa_credito', 'taxa_debito'))
        return render(request, self.template_name, {'form': form, 'object': pinpad, 'bandeiras': bandeiras})

    def post(self, request, pk):
        pinpad = get_object_or_404(Pinpad, pk=pk)
        form = PinpadForm(request.POST, instance=pinpad)
        if form.is_valid():
            p = form.save(commit=False)
            p.updated_by = request.user
            p.save()
            pinpad.bandeiras.all().delete()
            _save_bandeiras(request, pinpad)
            messages.success(request, f'Pinpad "{pinpad.name}" atualizado com sucesso!')
            return redirect('pinpads:pinpad_list')
        return render(request, self.template_name, {
            'form': form,
            'object': pinpad,
            'bandeiras': _parse_bandeiras_from_post(request),
        })


class PinpadDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'pinpads.delete_pinpad'
    model = Pinpad
    template_name = 'pinpads/pinpad_confirm_delete.html'
    success_url = reverse_lazy('pinpads:pinpad_list')

    def delete(self, request, *args, **kwargs):
        pinpad = self.get_object()
        messages.success(request, f'Pinpad "{pinpad.name}" excluído com sucesso!')
        return super().delete(request, *args, **kwargs)


class PinpadToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'pinpads.change_pinpad'

    def post(self, request, pk):
        pinpad = get_object_or_404(Pinpad, pk=pk)
        pinpad.is_active = not pinpad.is_active
        pinpad.updated_by = request.user
        # save() desativa as demais automaticamente se is_active=True
        pinpad.save()
        if pinpad.is_active:
            msg = f'"{pinpad.name}" ativada. As demais foram desativadas.'
        else:
            msg = f'"{pinpad.name}" desativada.'
        return JsonResponse({'success': True, 'message': msg, 'is_active': pinpad.is_active})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_bandeiras_from_post(request):
    count = _int(request.POST.get('bandeiras_count', '0'))
    result = []
    for i in range(count):
        nome = request.POST.get(f'bandeira_nome_{i}', '').strip()
        credito = request.POST.get(f'bandeira_credito_{i}', '0')
        debito = request.POST.get(f'bandeira_debito_{i}', '0')
        if nome:
            result.append({'nome': nome, 'taxa_credito': credito, 'taxa_debito': debito})
    return result


def _save_bandeiras(request, pinpad):
    count = _int(request.POST.get('bandeiras_count', '0'))
    for i in range(count):
        nome = request.POST.get(f'bandeira_nome_{i}', '').strip()
        if not nome:
            continue
        credito = _dec(request.POST.get(f'bandeira_credito_{i}', '0'))
        debito = _dec(request.POST.get(f'bandeira_debito_{i}', '0'))
        BandeiraPinpad.objects.create(pinpad=pinpad, nome=nome, taxa_credito=credito, taxa_debito=debito)


def _int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _dec(val, default=Decimal('0.00')):
    try:
        return Decimal(str(val).replace(',', '.'))
    except (InvalidOperation, TypeError):
        return default


# ---------------------------------------------------------------------------
# Stubs kept for URL compatibility (Point integration removed with model)
# ---------------------------------------------------------------------------

class PointTestView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = 'pinpads.view_pinpad'
    template_name = 'point_test.html'


class PinpadTestConnectionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'pinpads.view_pinpad'

    def post(self, request, pk):
        return JsonResponse({'success': False, 'message': 'Integração de API não disponível.'})


class PinpadSetDefaultView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'pinpads.change_pinpad'

    def post(self, request, pk):
        return JsonResponse({'success': False, 'message': 'Funcionalidade não disponível.'})


class PinpadStatsView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'pinpads.view_pinpad'

    def get(self, request):
        all_p = Pinpad.objects.all()
        return JsonResponse({'success': True, 'stats': {'total': all_p.count(), 'active': all_p.filter(is_active=True).count()}})


class PointDevicesView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'pinpads.view_pinpad'

    def get(self, request, pinpad_id):
        return JsonResponse({'success': False, 'message': 'Integração Point não disponível.'})


class PointPaymentView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'pinpads.change_pinpad'

    def post(self, request, pinpad_id):
        return JsonResponse({'success': False, 'message': 'Integração Point não disponível.'})


class PointPaymentStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'pinpads.view_pinpad'

    def get(self, request, pinpad_id, payment_intent_id):
        return JsonResponse({'success': False, 'message': 'Integração Point não disponível.'})


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse as _JR


@csrf_exempt
def mercadopago_webhook(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            logger.info(f"Webhook recebido: {data}")
            return _JR({'status': 'ok'})
        except Exception as e:
            return _JR({'error': str(e)}, status=500)
    return _JR({'error': 'Method not allowed'}, status=405)
