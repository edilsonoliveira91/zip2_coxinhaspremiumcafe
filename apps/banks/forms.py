from django import forms
from .models import Bank


class BankForm(forms.ModelForm):
    """Formulário de criação — inclui valor_inicial para gerar o lançamento inicial."""
    class Meta:
        model = Bank
        fields = ['nome', 'numero_conta', 'agencia', 'valor_inicial']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nome'].required = True
        self.fields['numero_conta'].required = False
        self.fields['agencia'].required = False
        self.fields['valor_inicial'].required = False


class BankEditForm(forms.ModelForm):
    """Formulário de edição — sem valor_inicial (não pode ser alterado após criação)."""
    class Meta:
        model = Bank
        fields = ['nome', 'numero_conta', 'agencia']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['nome'].required = True
        self.fields['numero_conta'].required = False
        self.fields['agencia'].required = False
