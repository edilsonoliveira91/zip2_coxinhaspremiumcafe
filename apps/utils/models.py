from django.db import models
from django.conf import settings


class TimeStampedModel(models.Model):
    """
    Modelo base abstrato que fornece campos de auditoria padrão
    para todos os modelos do sistema ERP como: ID, criado em, atualizado em, criado por, atualizado por e ativo.
    """
    id = models.AutoField(
        primary_key=True,
        verbose_name="ID"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
        verbose_name="Criado por"
    )
    
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated',
        verbose_name="Atualizado por"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.__class__.__name__} - {self.id}"