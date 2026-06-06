from django.shortcuts import render, redirect
from django.views.generic import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from .models import ConfigTempoEspera, ConfigTrocoInicial, ConfigQuebraCaixa, ConfigComissao, Garcom, ConfigKioskPin
from .forms import SystemConfigForm, TrocoInicialForm, QuebraCaixaForm, ComissaoForm, KioskPinForm


class TimeConfigView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'config.change_configtempoespera'
    raise_exception = True

    def get(self, request):
        form = SystemConfigForm(instance=ConfigTempoEspera.get_settings())
        return render(request, "time/timeconfig.html", {"form": form})

    def post(self, request):
        form = SystemConfigForm(request.POST, instance=ConfigTempoEspera.get_settings())
        if form.is_valid():
            form.save()
            messages.success(request, "Configuração de tempo alterada com sucesso!")
            return redirect("config:time_config")
        return render(request, "time/timeconfig.html", {"form": form})


class TrocoInicialView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'config.change_configtrocoinicial'
    raise_exception = True

    def get(self, request):
        config_obj = ConfigTrocoInicial.get_settings()
        form = TrocoInicialForm(instance=config_obj)
        return render(request, "config/troco_inicial.html", {"form": form, "config": config_obj})

    def post(self, request):
        config_obj = ConfigTrocoInicial.get_settings()
        form = TrocoInicialForm(request.POST, instance=config_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Troco inicial atualizado com sucesso!")
            return redirect("config:troco_inicial")
        return render(request, "config/troco_inicial.html", {"form": form, "config": config_obj})


class QuebraCaixaView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'config.change_configquebracaixa'
    raise_exception = True

    def get(self, request):
        config_obj = ConfigQuebraCaixa.get_settings()
        form = QuebraCaixaForm(instance=config_obj)
        return render(request, "config/quebra_caixa.html", {"form": form, "config": config_obj})

    def post(self, request):
        config_obj = ConfigQuebraCaixa.get_settings()
        form = QuebraCaixaForm(request.POST, instance=config_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuração de quebra de caixa atualizada com sucesso!")
            return redirect("config:quebra_caixa")
        return render(request, "config/quebra_caixa.html", {"form": form, "config": config_obj})


class ComissaoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'config.change_configcomissao'
    raise_exception = True

    def get(self, request):
        config_obj = ConfigComissao.get_settings()
        form = ComissaoForm(instance=config_obj)
        return render(request, "config/comissao.html", {"form": form, "config": config_obj})

    def post(self, request):
        config_obj = ConfigComissao.get_settings()
        form = ComissaoForm(request.POST, instance=config_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Comissão atualizada com sucesso!")
            return redirect("config:comissao")
        return render(request, "config/comissao.html", {"form": form, "config": config_obj})


class GarcomView(LoginRequiredMixin, View):

    def get(self, request):
        next_numero = (Garcom.objects.order_by('-numero').values_list('numero', flat=True).first() or 0) + 1
        garcons = Garcom.objects.select_related('criado_por').order_by('numero')
        return render(request, 'config/garcom.html', {
            'next_numero': next_numero,
            'garcons': garcons,
        })

    def post(self, request):
        nome = request.POST.get('nome', '').strip()
        if not nome:
            messages.error(request, "O nome do garçom é obrigatório.")
            return redirect('config:cadastro_garcom')

        next_numero = (Garcom.objects.order_by('-numero').values_list('numero', flat=True).first() or 0) + 1
        Garcom.objects.create(
            numero=next_numero,
            nome=nome,
            criado_por=request.user,
        )
        messages.success(request, f"Garçom #{next_numero} — {nome} cadastrado com sucesso!")
        return redirect('config:cadastro_garcom')


class KioskPinView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'config.change_configkioskpin'
    raise_exception = True

    def get(self, request):
        config_obj = ConfigKioskPin.get_settings()
        form = KioskPinForm(instance=config_obj)
        return render(request, 'config/kiosk_pin.html', {'form': form, 'config': config_obj})

    def post(self, request):
        config_obj = ConfigKioskPin.get_settings()
        form = KioskPinForm(request.POST, instance=config_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'PIN do Kiosk atualizado com sucesso!')
            return redirect('config:kiosk_pin')
        return render(request, 'config/kiosk_pin.html', {'form': form, 'config': config_obj})
