from django import forms
from .models import Pinpad


class PinpadForm(forms.ModelForm):
    class Meta:
        model = Pinpad
        fields = ['name', 'dias_credito', 'dias_debito', 'dias_pix', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Ex: Stone Caixa 1',
            }),
            'dias_credito': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'min': '0',
            }),
            'dias_debito': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'min': '0',
            }),
            'dias_pix': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'min': '0',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500',
            }),
        }
        labels = {
            'name': 'Nome da Pinpad',
            'dias_credito': 'Crédito (dias)',
            'dias_debito': 'Débito (dias)',
            'dias_pix': 'PIX (dias)',
            'is_active': 'Ativo',
        }
