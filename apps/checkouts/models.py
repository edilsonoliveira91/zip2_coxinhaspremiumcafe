from django.db import models
from django.conf import settings
from utils.models import TimeStampedModel
from orders.models import Comanda


class Checkout(TimeStampedModel):
    """
    Modelo para registro de checkout/pagamento de comandas
    """
    
    PAYMENT_METHOD_CHOICES = [
        ('dinheiro', 'Dinheiro'),
        ('cartao_debito', 'Cartão de Débito'),
        ('cartao_credito', 'Cartão de Crédito'),
        ('pix', 'PIX'),
        ('voucher', 'Voucher'),
    ]
    
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('aprovado', 'Aprovado'),
        ('cancelado', 'Cancelado'),
        ('estornado', 'Estornado'),
    ]
    
    # Relacionamento com a comanda
    comanda = models.OneToOneField(
        Comanda,
        on_delete=models.CASCADE,
        related_name='checkout',
        verbose_name='Comanda'
    )
    
    # Valores
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Subtotal'
    )
    
    desconto = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name='Desconto'
    )
    
    taxa_servico = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name='Taxa de Serviço'
    )
    
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Total'
    )
    
    # Forma de pagamento
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name='Forma de Pagamento'
    )
    
    # Status do pagamento
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pendente',
        verbose_name='Status'
    )
    
    # Informações do cliente
    customer_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Nome do Cliente'
    )
    
    customer_document = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='CPF/CNPJ'
    )
    
    # Controle
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='processed_checkouts',
        verbose_name='Processado por'
    )
    
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Processado em'
    )
    
    # Observações
    notes = models.TextField(
        blank=True,
        verbose_name='Observações'
    )
    
    class Meta:
        verbose_name = 'Checkout'
        verbose_name_plural = 'Checkouts'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'Checkout #{self.comanda.numero} - {self.get_payment_method_display()}'
    
    def save(self, *args, **kwargs):
        """Calcula o total automaticamente"""
        self.total = self.subtotal + self.taxa_servico - self.desconto
        super().save(*args, **kwargs)

class SessaoCaixa(models.Model):
    STATUS_CHOICES = [
        ('aberta', 'Aberta'),
        ('fechada', 'Fechada'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sessoes_caixa',
        verbose_name='Operador'
    )
    aberta_em = models.DateTimeField(auto_now_add=True, verbose_name='Aberta em')
    fechada_em = models.DateTimeField(null=True, blank=True, verbose_name='Fechada em')
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='aberta',
        verbose_name='Status'
    )

    class Meta:
        verbose_name = 'Sessão de Caixa'
        verbose_name_plural = 'Sessões de Caixa'
        ordering = ['-aberta_em']

    def __str__(self):
        return f'Caixa de {self.usuario.username} — {self.aberta_em.strftime("%d/%m/%Y %H:%M")}'

    def get_checkouts(self):
        from django.utils import timezone
        fim = self.fechada_em or timezone.now()
        return Checkout.objects.filter(
            processed_by=self.usuario,
            processed_at__gte=self.aberta_em,
            processed_at__lte=fim,
            status='aprovado',
        )

    def total(self):
        from django.db.models import Sum
        result = self.get_checkouts().aggregate(t=Sum('total'))
        return result['t'] or 0

    def totais_por_metodo(self):
        from django.db.models import Sum, Count
        return (
            self.get_checkouts()
            .values('payment_method')
            .annotate(total=Sum('total'), quantidade=Count('id'))
            .order_by('payment_method')
        )
