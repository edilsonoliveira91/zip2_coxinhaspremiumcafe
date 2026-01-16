from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from products.models import Product
from orders.models import Order
from checkouts.models import Checkout


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
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
            'placeholder': 'Digite o nome do usuário (minúsculo)',
        }),
        help_text='Use apenas letras minúsculas, sem espaços'
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
            'placeholder': 'Digite a senha',
        }),
        help_text='Mínimo 8 caracteres'
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
            'placeholder': 'Confirme a senha',
        }),
        label='Confirmar senha'
    )
    
    # Checkboxes para permissões de Produtos
    products_view = forms.BooleanField(required=False, label='Ver produtos')
    products_add = forms.BooleanField(required=False, label='Adicionar produtos')
    products_change = forms.BooleanField(required=False, label='Editar produtos')
    products_delete = forms.BooleanField(required=False, label='Deletar produtos')
    
    # Checkboxes para permissões de Pedidos
    orders_view = forms.BooleanField(required=False, label='Ver pedidos')
    orders_add = forms.BooleanField(required=False, label='Criar pedidos')
    orders_change = forms.BooleanField(required=False, label='Editar pedidos')
    orders_delete = forms.BooleanField(required=False, label='Deletar pedidos')
    
    # Checkboxes para permissões de Checkouts
    checkouts_view = forms.BooleanField(required=False, label='Ver checkouts')
    checkouts_add = forms.BooleanField(required=False, label='Criar checkouts')
    checkouts_change = forms.BooleanField(required=False, label='Editar checkouts')
    checkouts_delete = forms.BooleanField(required=False, label='Deletar checkouts')
    
    class Meta:
        model = User
        fields = ['username']
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            username = username.lower().strip()
            if ' ' in username:
                raise forms.ValidationError('O nome de usuário não pode conter espaços.')
            if not username.isalnum():
                raise forms.ValidationError('Use apenas letras e números.')
        return username
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise forms.ValidationError('As senhas não coincidem.')
            if len(password) < 8:
                raise forms.ValidationError('A senha deve ter pelo menos 8 caracteres.')
        
        return cleaned_data
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_staff = True  # Permite acesso ao sistema
        
        if commit:
            user.save()
            self._save_permissions(user)
        
        return user
    
    def _save_permissions(self, user):
        """Salva as permissões selecionadas nos checkboxes"""
        
        permissions_to_add = []
        
        # Mapear checkboxes para permissões
        permission_mapping = {
            'products': (Product, [
                ('products_view', 'view_product'),
                ('products_add', 'add_product'),
                ('products_change', 'change_product'),
                ('products_delete', 'delete_product'),
            ]),
            'orders': (Order, [
                ('orders_view', 'view_order'),
                ('orders_add', 'add_order'),
                ('orders_change', 'change_order'),
                ('orders_delete', 'delete_order'),
            ]),
            'checkouts': (Checkout, [
                ('checkouts_view', 'view_checkout'),
                ('checkouts_add', 'add_checkout'),
                ('checkouts_change', 'change_checkout'),
                ('checkouts_delete', 'delete_checkout'),
            ]),
        }
        
        for module, (model, perms) in permission_mapping.items():
            content_type = ContentType.objects.get_for_model(model)
            for field_name, codename in perms:
                if self.cleaned_data.get(field_name):
                    try:
                        perm = Permission.objects.get(
                            codename=codename,
                            content_type=content_type
                        )
                        permissions_to_add.append(perm)
                    except Permission.DoesNotExist:
                        pass
        
        user.user_permissions.set(permissions_to_add)