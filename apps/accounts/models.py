from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Modelo de usuário customizado simples baseado no AbstractUser
    Mantém apenas o essencial: username, password, email
    """
    
    # O AbstractUser já vem com:
    # - username
    # - password 
    # - email
    # - first_name
    # - last_name
    # - is_active
    # - is_staff
    # - is_superuser
    # - date_joined
    # - last_login
    
    is_caixa = models.BooleanField(
        default=False,
        verbose_name='Operador de Caixa',
        help_text='Permite que este usuário opere o caixa e acesse o fechamento de caixa.'
    )

    DASHBOARD_CHOICES = [
        ('home', 'Dashboard Principal (Comandas)'),
        ('ceo', 'Dashboard CEO'),
        ('manage', 'Dashboard Gerencial'),
    ]
    dashboard_home = models.CharField(
        max_length=20,
        choices=DASHBOARD_CHOICES,
        default='home',
        verbose_name='Tela inicial',
        help_text='Tela para a qual o usuário será redirecionado após o login.',
    )

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    def __str__(self):
        return self.username