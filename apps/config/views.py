from django.shortcuts import render, redirect
from django.views.generic import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import SystemConfig
from .forms import SystemConfigForm, TrocoInicialForm

class TimeConfigView(LoginRequiredMixin, UserPassesTestMixin, View):
    # Apenas super usuário terá permissão para ver essa tela
    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request):
        config_obj = SystemConfig.get_settings()
        form = SystemConfigForm(instance=config_obj)
        return render(request, 'time/timeconfig.html', {'form': form})

    def post(self, request):
        config_obj = SystemConfig.get_settings()
        form = SystemConfigForm(request.POST, instance=config_obj)
        
        if form.is_valid():
            form.save()
            messages.success(request, "Configuração de tempo alterada com sucesso!")
            return redirect('config:time_config')
            
        return render(request, 'time/timeconfig.html', {'form': form})


class TrocoInicialView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.is_superuser

    def get(self, request):
        config_obj = SystemConfig.get_settings()
        form = TrocoInicialForm(instance=config_obj)
        return render(request, 'config/troco_inicial.html', {'form': form, 'config': config_obj})

    def post(self, request):
        config_obj = SystemConfig.get_settings()
        form = TrocoInicialForm(request.POST, instance=config_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Troco inicial atualizado com sucesso!")
            return redirect('config:troco_inicial')
        return render(request, 'config/troco_inicial.html', {'form': form, 'config': config_obj})
