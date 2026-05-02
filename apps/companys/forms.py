from django import forms
from .models import Company, CertificadoDigital


class CompanyForm(forms.ModelForm):
    """
    Formulário para cadastro e edição de empresas.
    
    Este formulário gerencia todos os dados necessários para 
    emissão de NFCe, incluindo dados fiscais e endereço.
    """
    
    class Meta:
        model = Company
        exclude = ['created_at', 'updated_at']
        widgets = {
            # === DADOS BÁSICOS DA EMPRESA ===
            'cnpj': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': '00.000.000/0000-00',
                'maxlength': '18'
            }),
            
            'razao_social': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Razão Social da Empresa'
            }),
            
            'nome_fantasia': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Nome Fantasia'
            }),
            
            'inscricao_estadual': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Inscrição Estadual'
            }),
            
            'inscricao_municipal': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Inscrição Municipal'
            }),
            
            # === ENDEREÇO ===
            'logradouro': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Logradouro / Endereço'
            }),
            
            'numero': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Número'
            }),
            
            'complemento': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Complemento (opcional)'
            }),
            
            'bairro': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Bairro'
            }),
            
            'cidade': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Cidade'
            }),
            
            'uf': forms.Select(attrs={
                'class': 'select-field'
            }),
            
            'cep': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': '00000-000',
                'maxlength': '9'
            }),
            
            # === CONTATO ===
            'telefone': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': '(00) 0000-0000'
            }),
            
            'email': forms.EmailInput(attrs={
                'class': 'input-field',
                'placeholder': 'email@empresa.com'
            }),
            
            # === CONFIGURAÇÕES FISCAIS ===
            'regime_tributario': forms.Select(attrs={
                'class': 'select-field'
            }),
            
            # === CONFIGURAÇÕES NFCe ===
            'csc_id': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'ID do CSC'
            }),
            
            'csc_codigo': forms.TextInput(attrs={
                'class': 'input-field',
                'placeholder': 'Código CSC'
            }),
            
            'serie_nfce': forms.NumberInput(attrs={
                'class': 'input-field',
                'placeholder': 'Série da NFCe'
            }),
            
            'proximo_numero_nfce': forms.NumberInput(attrs={
                'class': 'input-readonly',
                'readonly': 'readonly',
                'placeholder': 'Controlado automaticamente pelo sistema'
            }),
            
            'ambiente_nfce': forms.Select(attrs={
                'class': 'select-field'
            }),
            
            # === CONFIGURAÇÕES DE STATUS ===
            'ativa': forms.CheckboxInput(attrs={
                'class': 'checkbox-field'
            }),

            'cfop_padrao': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500 transition duration-150 ease-in-out',
                'placeholder': '5102',
                'value': '5102'  # Valor padrão
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Define campos obrigatórios
        required_fields = [
            'cnpj', 'razao_social', 'logradouro', 'numero', 
            'bairro', 'cidade', 'uf', 'cep', 'csc_id', 'csc_codigo', 'cfop_padrao'
        ]
        
        for field_name in required_fields:
            if field_name in self.fields:
                self.fields[field_name].required = True
        
        # Aplica classes CSS via Media (método mais limpo)
        for field_name, field in self.fields.items():
            widget = field.widget
            current_attrs = widget.attrs
            
            # Define classes base conforme o tipo de widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.update({'class': self._get_checkbox_classes()})
            elif isinstance(widget, forms.Select):
                widget.attrs.update({'class': self._get_select_classes()})
            elif field_name == 'proximo_numero_nfce':
                widget.attrs.update({'class': self._get_readonly_classes()})
            else:
                widget.attrs.update({'class': self._get_input_classes()})
    
    def _get_input_classes(self):
        """Retorna classes CSS para campos de input normais"""
        return ('w-full px-4 py-3 border border-gray-300 rounded-xl '
                'focus:ring-2 focus:ring-orange-500 focus:border-orange-500 '
                'transition duration-150 ease-in-out')
    
    def _get_select_classes(self):
        """Retorna classes CSS para campos select"""
        return ('w-full px-4 py-3 border border-gray-300 rounded-xl '
                'focus:ring-2 focus:ring-orange-500 focus:border-orange-500 '
                'transition duration-150 ease-in-out appearance-none bg-white '
                'h-12')
    
    def _get_readonly_classes(self):
        """Retorna classes CSS para campos readonly"""
        return ('w-full px-4 py-3 border border-gray-300 rounded-xl '
                'bg-gray-100 text-gray-600 cursor-not-allowed')
    
    def _get_checkbox_classes(self):
        """Retorna classes CSS para campos checkbox"""
        return ('w-4 h-4 text-orange-600 bg-gray-100 border-gray-300 '
                'rounded focus:ring-orange-500 focus:ring-2')


class CertificadoDigitalForm(forms.ModelForm):
    """Formulário para upload e gerenciamento do certificado A1 (.pfx)"""

    class Meta:
        model = CertificadoDigital
        fields = ['arquivo_pfx', 'senha_pfx', 'numero_serie', 'valido_ate']
        widgets = {
            'arquivo_pfx': forms.FileInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150',
                'accept': '.pfx,.p12',
            }),
            'senha_pfx': forms.PasswordInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150',
                'placeholder': 'Senha do certificado .pfx',
            }),
            'numero_serie': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150',
                'placeholder': 'Número de série (opcional)',
            }),
            'valido_ate': forms.DateTimeInput(attrs={
                'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition duration-150',
                'type': 'datetime-local',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['arquivo_pfx'].required = True
        self.fields['senha_pfx'].required = True
        self.fields['numero_serie'].required = False
        self.fields['valido_ate'].required = False

        # When editing, arquivo_pfx is not required (keep existing file)
        if self.instance and self.instance.pk:
            self.fields['arquivo_pfx'].required = False
            self.fields['arquivo_pfx'].help_text = 'Deixe em branco para manter o arquivo atual.'

    def clean_senha_pfx(self):
        return self.cleaned_data.get('senha_pfx')