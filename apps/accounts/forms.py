from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django import forms
from .models import User


class CustomUserCreationForm(UserCreationForm):
    """
    Formulário simples de criação de usuário com confirmação de senha
    """
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Nome de usuário'
        }),
        label='Nome de usuário'
    )
    
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Senha'
        }),
        label='Senha'
    )
    
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Confirme a senha'
        }),
        label='Confirmação de senha'
    )

    class Meta:
        model = User
        fields = ('username', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove help texts
        for fieldname in ['username', 'password1', 'password2']:
            self.fields[fieldname].help_text = None


class UserPermissionForm(forms.ModelForm):
    password = forms.CharField(
        required=True, 
        label='Senha',
        widget=forms.PasswordInput()
    )
    confirm_password = forms.CharField(
        required=True, 
        label='Confirmar Senha',
        widget=forms.PasswordInput()
    )

    class Meta:
        model = User
        fields = ['username']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        # Se alguma senha for preenchida
        if password or confirm_password:
            if password != confirm_password:
                raise forms.ValidationError("As senhas não coincidem.")
            if len(password) < 6:
                raise forms.ValidationError("A senha precisa ter pelo menos 6 caracteres.")
                
        return cleaned_data