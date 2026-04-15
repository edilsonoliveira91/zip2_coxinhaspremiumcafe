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