from django import forms
from django.forms import inlineformset_factory
from .models import Order, OrderItem
from products.models import Product


class OrderForm(forms.ModelForm):
    """
    Formulário para criação e edição de comandas
    """
    
    class Meta:
        model = Order
        fields = ['name', 'observations']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500 bg-white/80 backdrop-blur-sm transition-all',
                    'placeholder': 'Ex: Mesa 5, João Silva, Balcão 1...',
                    'required': True,
                }
            ),
            'observations': forms.Textarea(
                attrs={
                    'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500 bg-white/80 backdrop-blur-sm resize-none text-sm',
                    'rows': 2,
                    'placeholder': 'Observações especiais para a comanda...',
                }
            ),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].label = 'Nome da Comanda'
        self.fields['observations'].label = 'Observações'
        self.fields['observations'].required = False


class OrderItemForm(forms.ModelForm):
    """
    Formulário para itens da comanda
    """
    
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'unit_price', 'observations']
        widgets = {
            'product': forms.Select(
                attrs={
                    'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
                }
            ),
            'quantity': forms.NumberInput(
                attrs={
                    'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                    'min': 1,
                    'value': 1,
                }
            ),
            'unit_price': forms.NumberInput(
                attrs={
                    'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                    'step': '0.01',
                    'min': '0.01',
                }
            ),
            'observations': forms.TextInput(
                attrs={
                    'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                    'placeholder': 'Ex: Sem cebola, extra queijo...',
                }
            ),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar apenas produtos ativos que aparecem no menu
        self.fields['product'].queryset = Product.objects.filter(
            is_active=True,
            show_in_menu=True
        ).order_by('category', 'name')
        
        # Labels
        self.fields['product'].label = 'Produto'
        self.fields['quantity'].label = 'Quantidade'
        self.fields['unit_price'].label = 'Preço Unitário'
        self.fields['observations'].label = 'Observações do Item'
        
        # Campos opcionais
        self.fields['unit_price'].required = False
        self.fields['observations'].required = False
    
    def clean_unit_price(self):
        """Validar e definir preço unitário"""
        unit_price = self.cleaned_data.get('unit_price')
        product = self.cleaned_data.get('product')
        
        # Se não foi informado preço, usar o preço do produto
        if not unit_price and product:
            unit_price = product.price
        
        return unit_price


class OrderStatusForm(forms.ModelForm):
    """
    Formulário simples para atualizar status da comanda
    (usado no scanner/atualização rápida)
    """
    
    class Meta:
        model = Order
        fields = ['status']
        widgets = {
            'status': forms.Select(
                attrs={
                    'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500 bg-white text-lg font-medium'
                }
            )
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].label = 'Status da Comanda'


class QuickOrderForm(forms.Form):
    """
    Formulário simplificado para criação rápida de comanda
    (usado no modal do sistema)
    """
    
    name = forms.CharField(
        max_length=100,
        label='Nome da Comanda',
        widget=forms.TextInput(
            attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500 bg-white/80 backdrop-blur-sm transition-all text-sm',
                'placeholder': 'Ex: Mesa 5, João Silva...',
                'id': 'orderName',
            }
        )
    )
    
    observations = forms.CharField(
        required=False,
        label='Observações',
        widget=forms.TextInput(
            attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500 bg-white/80 backdrop-blur-sm transition-all text-sm',
                'placeholder': 'Observações especiais...',
            }
        )
    )


# Formset para múltiplos itens da comanda
OrderItemFormSet = inlineformset_factory(
    Order,
    OrderItem,
    form=OrderItemForm,
    extra=1,  # Quantidade de forms vazios por padrão
    can_delete=True,
    min_num=1,  # Mínimo 1 item por comanda
    validate_min=True,
)


class ScannerForm(forms.Form):
    """
    Formulário para scanner de código de barras
    """
    
    barcode = forms.CharField(
        max_length=4,
        label='Código da Comanda',
        widget=forms.TextInput(
            attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-center text-2xl font-mono tracking-widest',
                'placeholder': '0000',
                'maxlength': 4,
                'pattern': '[0-9]{4}',
                'autocomplete': 'off',
                'autofocus': True,
            }
        )
    )
    
    def clean_barcode(self):
        """Validar código de barras"""
        barcode = self.cleaned_data.get('barcode')
        
        if not barcode or len(barcode) != 4 or not barcode.isdigit():
            raise forms.ValidationError('Código deve ter exatamente 4 dígitos.')
        
        # Verificar se existe comanda com este código
        try:
            order = Order.objects.get(code=barcode)
            return barcode
        except Order.DoesNotExist:
            raise forms.ValidationError(f'Comanda {barcode} não encontrada.')