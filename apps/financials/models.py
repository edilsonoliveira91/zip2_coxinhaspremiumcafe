from django.db import models
from django.conf import settings  # Mudança aqui
from django.core.validators import MinValueValidator
from decimal import Decimal
from utils.models import TimeStampedModel


class Sangria(TimeStampedModel):
    """
    Modelo para registrar sangrias (retiradas de dinheiro do caixa)
    """
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Valor da Sangria",
        help_text="Valor em reais que foi retirado do caixa"
    )
    
    observacao = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observação",
        help_text="Motivo ou observação sobre a sangria"
    )
    
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='sangrias',
        verbose_name="Usuário",
        help_text="Usuário que realizou a sangria"
    )
    
    class Meta:
        verbose_name = "Sangria"
        verbose_name_plural = "Sangrias"
        ordering = ['-created_at']  # Mais recentes primeiro
        permissions = [
            ("can_view_sangria", "Can view sangria"),
            ("can_add_sangria", "Can add sangria"),
        ]
    
    def __str__(self):
        return f"Sangria R$ {self.valor} - {self.usuario.get_full_name() or self.usuario.username} ({self.created_at.strftime('%d/%m/%Y %H:%M')})"
    
    @property
    def valor_formatado(self):
        """Retorna o valor formatado em reais"""
        return f"R$ {self.valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')