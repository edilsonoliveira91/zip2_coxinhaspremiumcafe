from django import forms
from django.core.validators import URLValidator
from .models import Pinpad


from django import forms
from django.core.validators import URLValidator
from .models import Pinpad


class PinpadForm(forms.ModelForm):
    """
    Formulário para cadastro e edição de Pinpads
    """
    
    def __init__(self, *args, **kwargs):
        # Remove o parâmetro 'user' dos kwargs se existir
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    class Meta:
        model = Pinpad
        fields = [
            'name', 'description', 'provider', 'status',
            'api_url', 'api_key', 'api_secret', 'merchant_id', 'terminal_id',
            'pix_key', 'webhook_url',  # Novos campos PIX
            'supports_credit', 'supports_debit', 'supports_contactless', 'supports_pix',
            'credit_fee_percentage', 'debit_fee_percentage', 'pix_fee_percentage',
            'credit_fee_fixed', 'debit_fee_fixed',
            'timeout', 'max_amount', 'is_default', 'is_active'
        ]
        
        widgets = {
            # Campos de texto
            'name': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Ex: Stone Terminal 1'
            }),
            
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Descrição do pinpad...',
                'rows': 3
            }),
            
            # Selects
            'provider': forms.Select(attrs={
                'class': 'w-full px-4 py-3 h-12 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),

            'status': forms.Select(attrs={
                'class': 'w-full px-4 py-3 h-12 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
            }),
            
            # URLs e APIs
            'api_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'https://api.exemplo.com'
            }),
            
            'api_key': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Chave de acesso da API'
            }),
            
            'api_secret': forms.PasswordInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Chave secreta (opcional)'
            }),
            
            'merchant_id': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'ID do Merchant'
            }),
            
            'terminal_id': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'ID do Terminal'
            }),

            # Novos campos PIX
            'pix_key': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'Ex: usuario@email.com, +5511999999999, CPF/CNPJ'
            }),

            'webhook_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'https://seusite.com/webhook/pix'
            }),
            
            # Campos numéricos - Taxas
            'credit_fee_percentage': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': '2.49',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            
            'debit_fee_percentage': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': '1.99',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),

            'pix_fee_percentage': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': '0.99',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            
            'credit_fee_fixed': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': '0.39',
                'step': '0.01',
                'min': '0'
            }),
            
            'debit_fee_fixed': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': '0.39',
                'step': '0.01',
                'min': '0'
            }),
            
            # Configurações avançadas
            'timeout': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': '60',
                'min': '1'
            }),
            
            'max_amount': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'placeholder': '1000.00',
                'step': '0.01',
                'min': '0'
            }),
            
            # Checkboxes
            'supports_credit': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
            
            'supports_debit': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),
            
            'supports_contactless': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
            }),

            'supports_pix': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 text-green-600 border-gray-300 rounded focus:ring-green-500'
            }),
            
            'is_default': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 text-orange-600 border-gray-300 rounded focus:ring-orange-500'
            }),
            
            'is_active': forms.CheckboxInput(attrs={
                'class': 'w-5 h-5 text-green-600 border-gray-300 rounded focus:ring-green-500'
            }),
        }
        
        labels = {
            'name': 'Nome do Pinpad',
            'description': 'Descrição',
            'provider': 'Provedor',
            'status': 'Status',
            'api_url': 'URL da API',
            'api_key': 'API Key',
            'api_secret': 'API Secret',
            'merchant_id': 'ID do Merchant',
            'terminal_id': 'ID do Terminal',
            'pix_key': 'Chave PIX',
            'webhook_url': 'Webhook URL',
            'supports_credit': 'Suporta Crédito',
            'supports_debit': 'Suporta Débito',
            'supports_contactless': 'Suporta Contactless',
            'supports_pix': 'Suporta PIX',
            'credit_fee_percentage': 'Taxa Crédito (%)',
            'debit_fee_percentage': 'Taxa Débito (%)',
            'pix_fee_percentage': 'Taxa PIX (%)',
            'credit_fee_fixed': 'Taxa Fixa Crédito (R$)',
            'debit_fee_fixed': 'Taxa Fixa Débito (R$)',
            'timeout': 'Timeout (segundos)',
            'max_amount': 'Valor Máximo (R$)',
            'is_default': 'Pinpad Padrão',
            'is_active': 'Ativo',
        }
        
        help_texts = {
            'name': 'Nome identificador do pinpad',
            'description': 'Descrição adicional (opcional)',
            'pix_key': 'Chave PIX: email, telefone, CPF/CNPJ ou chave aleatória',
            'webhook_url': 'URL para receber notificações de pagamento PIX',
            'credit_fee_percentage': 'Taxa percentual do crédito (ex: 2.49 para 2,49%)',
            'debit_fee_percentage': 'Taxa percentual do débito (ex: 1.99 para 1,99%)',
            'pix_fee_percentage': 'Taxa percentual do PIX (ex: 0.99 para 0,99%)',
            'credit_fee_fixed': 'Taxa fixa por transação de crédito em reais',
            'debit_fee_fixed': 'Taxa fixa por transação de débito em reais',
            'timeout': 'Tempo limite para transações em segundos',
            'max_amount': 'Valor máximo permitido por transação (opcional)',
            'is_default': 'Usar como pinpad padrão do sistema',
            'api_secret': 'Deixe em branco se não for necessário',
        }

    def save(self, commit=True):
        """Sobrescrever save para definir usuário de criação/atualização"""
        instance = super().save(commit=False)
        
        if self.user:
            if not instance.pk:  # Se é criação
                instance.created_by = self.user
            instance.updated_by = self.user
        
        if commit:
            instance.save()
        return instance

    def clean(self):
        """Validações gerais do formulário"""
        cleaned_data = super().clean()
        
        # Validar se pelo menos um tipo de pagamento é suportado
        supports_credit = cleaned_data.get('supports_credit')
        supports_debit = cleaned_data.get('supports_debit')
        supports_pix = cleaned_data.get('supports_pix')
        
        if not supports_credit and not supports_debit and not supports_pix:
            raise forms.ValidationError(
                'O pinpad deve suportar pelo menos crédito, débito ou PIX.'
            )
        
        # Validar taxas se os tipos de pagamento estão habilitados
        if supports_credit:
            credit_fee_percentage = cleaned_data.get('credit_fee_percentage')
            if credit_fee_percentage is None:
                raise forms.ValidationError('Taxa percentual do crédito é obrigatória.')
                
        if supports_debit:
            debit_fee_percentage = cleaned_data.get('debit_fee_percentage')
            if debit_fee_percentage is None:
                raise forms.ValidationError('Taxa percentual do débito é obrigatória.')
                
        if supports_pix:
            pix_fee_percentage = cleaned_data.get('pix_fee_percentage')
            if pix_fee_percentage is None:
                raise forms.ValidationError('Taxa percentual do PIX é obrigatória.')
        
        return cleaned_data


class PinpadTestForm(forms.Form):
    """
    Formulário simples para testar conexão com pinpad
    """
    pinpad = forms.ModelChoiceField(
        queryset=Pinpad.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
        }),
        label='Selecione o Pinpad',
        help_text='Escolha o pinpad para testar a conexão'
    )
    
    test_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=1.00,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': '1.00',
            'step': '0.01',
            'min': '0.01'
        }),
        label='Valor de Teste (R$)',
        help_text='Valor para simular teste de transação'
    )

class PinpadTestForm(forms.Form):
    """
    Formulário simples para testar conexão com pinpad
    """
    pinpad = forms.ModelChoiceField(
        queryset=Pinpad.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500'
        }),
        label='Selecione o Pinpad',
        help_text='Escolha o pinpad para testar a conexão'
    )
    
    test_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=1.00,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': '1.00',
            'step': '0.01',
            'min': '0.01'
        }),
        label='Valor de Teste (R$)',
        help_text='Valor para simular teste de transação'
    )