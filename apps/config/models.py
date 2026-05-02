from django.db import models
from decimal import Decimal

class SystemConfig(models.Model):
    max_order_time_minutes = models.PositiveIntegerField(
        default=20,
        verbose_name="Tempo Máximo de Espera (minutos)",
        help_text="Pedidos abertos após este tempo farão a comanda piscar em vermelho."
    )
    troco_inicial = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('50.00'),
        verbose_name="Troco Inicial (R$)",
        help_text="Valor padrão com que o caixa inicia todos os dias."
    )

    class Meta:
        verbose_name = "Configuração do Sistema"
        verbose_name_plural = "Configurações do Sistema"

    def __str__(self):
        return "Configurações Globais"
        
    def save(self, *args, **kwargs):
        # Garantir que só exista UMA configuração (id=1)
        self.pk = 1
        super().save(*args, **kwargs)
        
    @classmethod
    def get_settings(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj