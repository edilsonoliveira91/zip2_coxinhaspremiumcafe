from django import forms
from .models import SystemConfig

class SystemConfigForm(forms.ModelForm):
    class Meta:
        model = SystemConfig
        fields = ['max_order_time_minutes']
        widgets = {
            'max_order_time_minutes': forms.NumberInput(attrs={
                'class': 'w-32 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-lg font-bold text-gray-800 text-center shadow-inner',
                'min': '1',
            }),
        }


class TrocoInicialForm(forms.ModelForm):
    class Meta:
        model = SystemConfig
        fields = ['troco_inicial']
        widgets = {
            'troco_inicial': forms.NumberInput(attrs={
                'class': 'w-40 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500 text-lg font-bold text-gray-800 text-center shadow-inner',
                'min': '0',
                'step': '0.01',
            }),
        }


class QuebraCaixaForm(forms.ModelForm):
    class Meta:
        model = SystemConfig
        fields = ['quebra_positiva', 'quebra_negativa']
        widgets = {
            'quebra_positiva': forms.NumberInput(attrs={
                'class': 'w-40 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-green-500 text-lg font-bold text-gray-800 text-center shadow-inner',
                'min': '0',
                'step': '0.01',
            }),
            'quebra_negativa': forms.NumberInput(attrs={
                'class': 'w-40 px-4 py-3 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-red-500 focus:border-red-500 text-lg font-bold text-gray-800 text-center shadow-inner',
                'min': '0',
                'step': '0.01',
            }),
        }
