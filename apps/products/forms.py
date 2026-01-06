from django import forms
from django.forms import inlineformset_factory
from .models import Product, Combo, ComboItem


from django import forms
from django.forms import inlineformset_factory
from .models import Product, Combo, ComboItem


class ProductForm(forms.ModelForm):
    """
    Formulário para criação e edição de produtos
    """
    
    class Meta:
        model = Product
        fields = ['name', 'description', 'category', 'price', 'show_in_menu', 'image']
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'placeholder': 'Nome do produto'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'rows': 4,
                'placeholder': 'Descrição do produto'
            }),
            'category': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500 h-12 appearance-none bg-white',
                'style': 'height: 48px !important; min-height: 48px !important;'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'show_in_menu': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-orange-600 focus:ring-orange-500 focus:ring-offset-0'
            }),
            'image': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'accept': 'image/*'
            })
        }
        
        labels = {
            'name': 'Nome do Produto',
            'description': 'Descrição',
            'category': 'Categoria',
            'price': 'Preço (R$)',
            'show_in_menu': 'Mostrar no Cardápio',
            'image': 'Imagem do Produto'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Remover mensagens de help padrão
        for field_name, field in self.fields.items():
            field.help_text = None
            
        # Personalizar mensagens de erro
        self.fields['name'].error_messages = {
            'required': 'O nome do produto é obrigatório.',
            'max_length': 'O nome deve ter no máximo 100 caracteres.'
        }
        
        self.fields['price'].error_messages = {
            'required': 'O preço é obrigatório.',
            'invalid': 'Digite um preço válido.',
            'min_value': 'O preço deve ser maior que zero.'
        }


class ComboForm(forms.ModelForm):
    """
    Formulário para criação e edição de combos
    """
    
    class Meta:
        model = Combo
        fields = ['name', 'description', 'show_in_menu', 'image']
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'placeholder': 'Nome do combo'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'rows': 4,
                'placeholder': 'Descrição do combo'
            }),
            'show_in_menu': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-orange-600 focus:ring-orange-500 focus:ring-offset-0'
            }),
            'image': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'accept': 'image/*'
            })
        }
        
        labels = {
            'name': 'Nome do Combo',
            'description': 'Descrição do Combo',
            'show_in_menu': 'Mostrar no Cardápio',
            'image': 'Imagem do Combo'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Remover mensagens de help padrão
        for field_name, field in self.fields.items():
            field.help_text = None
            
        # Personalizar mensagens de erro
        self.fields['name'].error_messages = {
            'required': 'O nome do combo é obrigatório.',
            'max_length': 'O nome deve ter no máximo 100 caracteres.'
        }


class ComboItemForm(forms.ModelForm):
    """
    Formulário para itens do combo - permite alterar preço individual
    """
    
    class Meta:
        model = ComboItem
        fields = ['product', 'quantity', 'combo_price']
        
        widgets = {
            'product': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-sm',
                'onchange': 'updateOriginalPrice(this)'  # JavaScript para mostrar preço original
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-sm text-center',
                'min': '1',
                'value': '1'
            }),
            'combo_price': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-sm',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            })
        }
        
        labels = {
            'product': 'Produto',
            'quantity': 'Qtd',
            'combo_price': 'Preço no Combo (R$)'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filtrar apenas produtos ativos e que podem aparecer no cardápio
        self.fields['product'].queryset = Product.objects.filter(
            is_active=True
        ).order_by('category', 'name')
        
        # Adicionar option vazio
        self.fields['product'].empty_label = "Selecione um produto"
        
        # Remover help texts
        for field_name, field in self.fields.items():
            field.help_text = None
            
        # Mensagens de erro personalizadas
        self.fields['product'].error_messages = {
            'required': 'Selecione um produto.',
            'invalid_choice': 'Produto inválido.'
        }
        
        self.fields['quantity'].error_messages = {
            'required': 'A quantidade é obrigatória.',
            'min_value': 'A quantidade deve ser maior que zero.'
        }
        
        self.fields['combo_price'].error_messages = {
            'required': 'O preço no combo é obrigatório.',
            'invalid': 'Digite um preço válido.',
            'min_value': 'O preço deve ser maior que zero.'
        }

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        combo_price = cleaned_data.get('combo_price')
        
        # Validação: o preço no combo não pode ser maior que o dobro do preço original
        if product and combo_price:
            max_allowed = product.price * 2
            if combo_price > max_allowed:
                raise forms.ValidationError(
                    f'O preço no combo (R$ {combo_price}) não pode ser maior que '
                    f'R$ {max_allowed} (dobro do preço original).'
                )
        
        return cleaned_data


# Formset para múltiplos itens do combo
ComboItemFormSet = inlineformset_factory(
    Combo,                    # Modelo pai
    ComboItem,               # Modelo filho
    form=ComboItemForm,      # Formulário para cada item
    extra=3,                 # 3 formulários extras vazios
    min_num=1,               # Pelo menos 1 item obrigatório
    validate_min=True,       # Validar mínimo
    can_delete=True,         # Permitir exclusão de itens
    fields=['product', 'quantity', 'combo_price']
)


class ProductSearchForm(forms.Form):
    """
    Formulário para pesquisa de produtos
    """
    search = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
            'placeholder': 'Pesquisar produtos...'
        })
    )
    
    category = forms.ChoiceField(
        required=False,
        choices=[('', 'Todas as categorias')] + Product.CATEGORY_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
        })
    )
    
    show_in_menu = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Todos'),
            ('true', 'No cardápio'),
            ('false', 'Fora do cardápio')
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
        }),
        label='Status no Cardápio'
    )


class ComboSearchForm(forms.Form):
    """
    Formulário para pesquisa de combos
    """
    search = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
            'placeholder': 'Pesquisar combos...'
        })
    )
    
    show_in_menu = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Todos'),
            ('true', 'No cardápio'),
            ('false', 'Fora do cardápio')
        ],
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
        }),
        label='Status no Cardápio'
    )