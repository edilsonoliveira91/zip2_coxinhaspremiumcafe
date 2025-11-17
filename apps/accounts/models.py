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
    
    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"

    def __str__(self):
        return self.username