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

    quebra_positiva = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('5.00'),
        verbose_name="Quebra de Caixa Positiva (R$)",
        help_text="Margem máxima tolerada de sobra em espécie (caixa com mais dinheiro do que o previsto)."
    )
    quebra_negativa = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('5.00'),
        verbose_name="Quebra de Caixa Negativa (R$)",
        help_text="Margem máxima tolerada de falta em espécie (caixa com menos dinheiro do que o previsto)."
    )

    comissao_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Comissão sobre Vendas (%)",
        help_text="Percentual de comissão pago ao operador sobre o total de vendas do período."
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