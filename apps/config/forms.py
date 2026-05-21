from django import forms
from .models import ConfigTempoEspera, ConfigTrocoInicial, ConfigQuebraCaixa, ConfigComissao

WIDGET_BASE = "px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:border-orange-500 text-lg font-bold text-gray-800 text-center shadow-inner"

class SystemConfigForm(forms.ModelForm):
    class Meta:
        model = ConfigTempoEspera
        fields = ["max_order_time_minutes"]
        widgets = {
            "max_order_time_minutes": forms.NumberInput(attrs={
                "class": WIDGET_BASE + " focus:ring-orange-500 w-32",
                "min": "1",
            }),
        }


class TrocoInicialForm(forms.ModelForm):
    class Meta:
        model = ConfigTrocoInicial
        fields = ["troco_inicial"]
        widgets = {
            "troco_inicial": forms.NumberInput(attrs={
                "class": WIDGET_BASE + " focus:ring-green-500 w-40",
                "min": "0",
                "step": "0.01",
            }),
        }


class QuebraCaixaForm(forms.ModelForm):
    class Meta:
        model = ConfigQuebraCaixa
        fields = ["quebra_positiva", "quebra_negativa"]
        widgets = {
            "quebra_positiva": forms.NumberInput(attrs={
                "class": WIDGET_BASE + " focus:ring-green-500 w-40",
                "min": "0",
                "step": "0.01",
            }),
            "quebra_negativa": forms.NumberInput(attrs={
                "class": WIDGET_BASE + " focus:ring-red-500 w-40",
                "min": "0",
                "step": "0.01",
            }),
        }


class ComissaoForm(forms.ModelForm):
    class Meta:
        model = ConfigComissao
        fields = ["comissao_percentual"]
        widgets = {
            "comissao_percentual": forms.NumberInput(attrs={
                "class": WIDGET_BASE + " focus:ring-blue-500 w-40",
                "min": "0",
                "max": "100",
                "step": "0.01",
            }),
        }
