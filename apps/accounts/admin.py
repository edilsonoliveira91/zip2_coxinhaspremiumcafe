from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    """
    Configuração completa do Admin para o modelo User customizado, 
    liberando a aba de Permissões, Staff e Superuser.
    """
    # O que aparece na lista principal
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_superuser', 'is_active']
    list_filter = ['is_active', 'is_staff', 'is_superuser', 'groups']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['username']

    # Filtros visuais bonitos para selecionar múltiplas permissões
    filter_horizontal = ('groups', 'user_permissions',)

    # Organização dos campos ao EDITAR o usuário no painel
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Informações Pessoais'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('Permissões de Acesso'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Datas Importantes'), {'fields': ('last_login', 'date_joined')}),
    )

    # Organização dos campos ao CRIAR um NOVO usuário pelo painel
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password', 'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'is_superuser'),
        }),
    )