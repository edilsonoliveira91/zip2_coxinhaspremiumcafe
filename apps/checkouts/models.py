from django.db import models
from django.conf import settings
from utils.models import TimeStampedModel
from orders.models import Order


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
    order = models.OneToOneField(
        Order,
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
        return f'Checkout #{self.order.code} - {self.get_payment_method_display()}'
    
    def save(self, *args, **kwargs):
        """Calcula o total automaticamente"""
        self.total = self.subtotal + self.taxa_servico - self.desconto
        super().save(*args, **kwargs)