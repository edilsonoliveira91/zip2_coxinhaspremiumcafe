from django import forms
from .models import Comanda, Pedido, PedidoItem

class ComandaForm(forms.ModelForm):
    class Meta:
        model = Comanda
        fields = ['numero', 'cliente_nome']

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
