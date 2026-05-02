from django import forms
from django.core.exceptions import ValidationError
from .models import Comanda, Pedido, PedidoItem


def validar_numero_comanda(value):
    """Aceita apenas números inteiros de 0 a 999, formatados como 3 dígitos."""
    v = str(value).strip()
    if not v.isdigit():
        raise ValidationError('O número da comanda deve conter apenas dígitos.')
    num = int(v)
    if num < 0 or num > 999:
        raise ValidationError('O número da comanda deve ser entre 000 e 999.')


class ComandaForm(forms.ModelForm):
    class Meta:
        model = Comanda
        fields = ['numero', 'cliente_nome']

    def clean_numero(self):
        value = self.cleaned_data.get('numero', '').strip()
        validar_numero_comanda(value)
        return str(int(value)).zfill(3)


class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ['observations']


class ScannerForm(forms.Form):
    barcode = forms.CharField(max_length=20)


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = ['status']


from django.forms import inlineformset_factory
PedidoItemFormSet = inlineformset_factory(
    Pedido, PedidoItem, fields=['product', 'quantity', 'unit_price', 'observations'], extra=1
)
