from django import forms
from django.forms import inlineformset_factory
from .models import Product, Combo, ComboItem, RawMaterial
from django import forms
from django.forms import inlineformset_factory
from .models import Product, Combo, ComboItem
import datetime
from .models import StockEntry


class ProductForm(forms.ModelForm):
    """
    Formulário para criação e edição de produtos
    """
    
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'category', 'price', 'show_in_menu', 'is_active', 'destino_producao', 'image',
            'ncm', 'cfop', 'cst_icms', 'base_calculo_icms', 'aliq_icms',
            'codigo_cbenef', 'dados_adicionais_nfe', 'cst_pis_cofins',
            'aliq_pis', 'aliq_cofins', 'cst_ibs_cbs', 'cclass',
        ]
        
        _input_class = 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
        
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
            'is_active': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-green-600 focus:ring-green-500 focus:ring-offset-0'
            }),
            'destino_producao': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-amber-500 focus:border-amber-500 h-12 appearance-none bg-white',
                'style': 'height: 48px !important; min-height: 48px !important;'
            }),
            'image': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'accept': 'image/*'
            }),
            # NFCe fields
            'ncm': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Ex: 21069090'
            }),
            'cfop': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Ex: 5102'
            }),
            'cst_icms': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Ex: 400'
            }),
            'base_calculo_icms': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '100.00'
            }),
            'aliq_icms': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00'
            }),
            'codigo_cbenef': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Ex: SC820050'
            }),
            'dados_adicionais_nfe': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'rows': 3,
                'placeholder': 'Informações adicionais que constarão na NF-e'
            }),
            'cst_pis_cofins': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Ex: 07'
            }),
            'aliq_pis': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00'
            }),
            'aliq_cofins': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': '0.00'
            }),
            'cst_ibs_cbs': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Ex: 00'
            }),
            'cclass': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Código de classificação'
            }),
        }
        
        labels = {
            'name': 'Nome do Produto',
            'description': 'Descrição',
            'category': 'Categoria',
            'price': 'Preço (R$)',
            'show_in_menu': 'Mostrar no Cardápio',
            'is_active': 'Produto Ativo',
            'destino_producao': 'Destino de Produção',
            'image': 'Imagem do Produto',
            'ncm': 'NCM',
            'cfop': 'CFOP',
            'cst_icms': 'CST ICMS',
            'base_calculo_icms': '% Base de Cálculo ICMS',
            'aliq_icms': 'Alíquota ICMS (%)',
            'codigo_cbenef': 'Código CBENEF',
            'dados_adicionais_nfe': 'Dados Adicionais da NF-e',
            'cst_pis_cofins': 'CST PIS e COFINS',
            'aliq_pis': 'Alíquota PIS (%)',
            'aliq_cofins': 'Alíquota COFINS (%)',
            'cst_ibs_cbs': 'CST IBS CBS',
            'cclass': 'CCLASS',
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


class StockEntryForm(forms.ModelForm):
    class Meta:
        model = StockEntry
        fields = ['date', 'product', 'quantity', 'unit_cost', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition',
            }),
            'product': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 h-12 appearance-none bg-white',
                'style': 'height: 48px !important; min-height: 48px !important;',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition',
                'placeholder': '0', 'min': '1',
            }),
            'unit_cost': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition',
                'placeholder': '0,00',
                'inputmode': 'numeric',
                'autocomplete': 'off',
            }),
            'notes': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 transition',
                'placeholder': 'Observações opcionais (ex: fornecedor, nota fiscal...)',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('date') and not self.data.get('date'):
            self.initial['date'] = datetime.date.today().isoformat()
        self.fields['product'].queryset = Product.objects.filter(is_active=True).order_by('category', 'name')
        self.fields['product'].empty_label = 'Selecione um produto...'
        self.fields['notes'].required = False


class RawMaterialForm(forms.ModelForm):
    class Meta:
        model = RawMaterial
        fields = ['name', 'unit_measure']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'placeholder': 'Ex: Farinha de Trigo',
            }),
            'unit_measure': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500 bg-white',
                'style': 'height: 48px !important;',
            }),
        }
        labels = {
            'name': 'Nome da Matéria Prima',
            'unit_measure': 'Unidade de Medida',
        }
        error_messages = {
            'name': {'unique': 'Já existe uma matéria prima com este nome.'}
        }
