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

class FechamentoCaixaDiario(TimeStampedModel):
    """
    Arquiva o extrato do caixa ao final de cada dia operacional.
    Permite verificar o histórico de fechamentos passados.
    """
    data = models.DateField(
        unique=True,
        verbose_name="Data do Fechamento",
    )
    fechado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='fechamentos_caixa',
        verbose_name="Fechado por",
    )
    valor_inicial   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Troco Inicial")
    total_dinheiro  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Dinheiro")
    total_debito    = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Cartao Debito")
    total_credito   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Cartao Credito")
    total_pix       = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="PIX")
    total_voucher   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Voucher")
    total_sangrias  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Sangrias")
    total_entradas  = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Entradas")
    total_final     = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Total Final em Caixa")
    total_comandas  = models.PositiveIntegerField(default=0, verbose_name="Qtd Comandas")
    observacao      = models.TextField(blank=True, verbose_name="Observacao")

    class Meta:
        verbose_name = "Fechamento de Caixa Diario"
        verbose_name_plural = "Fechamentos de Caixa Diarios"
        ordering = ['-data']

    def __str__(self):
        return f"Fechamento {self.data.strftime('%d/%m/%Y')} - R$ {self.total_final}"


class CaixaAdm(models.Model):
    """
    Malote enviado pelo operador de caixa para conferência administrativa.
    Criado quando o operador clica em "Enviar Malote" no histórico de fechamentos.
    """
    fechamento = models.OneToOneField(
        FechamentoCaixaDiario,
        on_delete=models.CASCADE,
        related_name='malote',
        verbose_name="Fechamento",
    )
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='malotes_enviados',
        verbose_name="Enviado por",
    )
    enviado_em = models.DateTimeField(auto_now_add=True, verbose_name="Enviado em")
    concluido = models.BooleanField(default=False, verbose_name="Concluído")
    concluido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='malotes_concluidos',
        verbose_name="Concluído por",
    )
    concluido_em = models.DateTimeField(null=True, blank=True, verbose_name="Concluído em")

    class Meta:
        verbose_name = "Caixa ADM"
        verbose_name_plural = "Caixas ADM"
        ordering = ['-enviado_em']

    def __str__(self):
        return f"Malote {self.fechamento.data.strftime('%d/%m/%Y')} - {self.enviado_por}"

    @property
    def total_despesas(self):
        from django.db.models import Sum
        return self.despesas.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    @property
    def dinheiro_liquido(self):
        """Dinheiro do malote já descontado das despesas."""
        return self.fechamento.total_dinheiro - self.total_despesas

    @property
    def total_final_liquido(self):
        """Total final do malote já descontado das despesas."""
        return self.fechamento.total_final - self.total_despesas


class DespesaMalote(models.Model):
    """
    Despesa vinculada a um malote (CaixaAdm) registrada pelo ADM.
    """
    malote = models.ForeignKey(
        CaixaAdm,
        on_delete=models.CASCADE,
        related_name='despesas',
        verbose_name="Malote",
    )
    valor = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Valor",
    )
    descricao = models.CharField(max_length=255, verbose_name="Descrição")
    comprovante = models.FileField(
        upload_to='despesas_malote/',
        blank=True,
        null=True,
        verbose_name="Comprovante",
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='despesas_malote',
        verbose_name="Registrado por",
    )
    registrado_em = models.DateTimeField(auto_now_add=True, verbose_name="Registrado em")

    class Meta:
        verbose_name = "Despesa do Malote"
        verbose_name_plural = "Despesas do Malote"
        ordering = ['-registrado_em']

    def __str__(self):
        return f"Despesa R$ {self.valor} - {self.malote} - {self.descricao[:40]}"
