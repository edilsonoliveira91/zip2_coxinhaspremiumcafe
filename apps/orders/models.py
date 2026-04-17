from django.db import models
from django.conf import settings
from utils.models import TimeStampedModel
from products.models import Product
from django.db.models import Sum

class Comanda(TimeStampedModel):
    """
    Modelo para a Comanda Eletrônica (o pager físico).
    Cada comanda pode conter múltiplos pedidos.
    """
    STATUS_CHOICES = [
        ('livre', 'Livre'),
        ('em_uso', 'Em Uso'),
        ('fechada', 'Fechada'),
    ]

    numero = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Número da Comanda",
        help_text="Número único identificado pelo código de barras do pager."
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='livre',
        verbose_name="Status"
    )

    cliente_nome = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Nome do Cliente (Opcional)"
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Valor Total"
    )

    class Meta:
        verbose_name = "Comanda"
        verbose_name_plural = "Comandas"
        ordering = ['-created_at']

    def __str__(self):
        return f"Comanda #{self.numero}"

    def update_total(self):
        """Atualiza o valor total da comanda somando os totais de seus pedidos."""
        total = self.pedidos.filter(status__in=['aguardando', 'preparando', 'pronta', 'entregue']).aggregate(Sum('total_amount'))['total_amount__sum'] or 0.00
        self.total_amount = total
        self.save(update_fields=['total_amount'])


class Pedido(TimeStampedModel):
    """
    Modelo para um Pedido feito dentro de uma Comanda.
    (Anteriormente chamado de 'Order')
    """
    
    STATUS_CHOICES = [
        ('aguardando', 'Aguardando'),
        ('preparando', 'Em Preparo'),
        ('pronta', 'Pronta'),
        ('entregue', 'Entregue'),
        ('cancelado', 'Cancelado'),
    ]
    
    comanda = models.ForeignKey(
        Comanda,
        on_delete=models.CASCADE,
        related_name='pedidos',
        verbose_name="Comanda"
    )

    # Código sequencial do pedido dentro da comanda
    pedido_seq = models.PositiveIntegerField(
        default=1,
        verbose_name="Sequencial do Pedido"
    )

    observations = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observações",
        help_text="Observações especiais para o pedido"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='aguardando',
        verbose_name="Status"
    )

    motivo_cancelamento = models.TextField(
        blank=True,
        null=True,
        verbose_name="Motivo do Cancelamento",
        help_text="Justificativa preenchida ao cancelar o pedido"
    )
    
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        verbose_name="Valor Total"
    )
    
    # Timestamps de controle
    started_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Iniciado em"
    )
    
    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Finalizado em"
    )
    
    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Entregue em"
    )

    # Campos para NFCe
    nfce_numero = models.IntegerField(
        null=True, 
        blank=True, 
        verbose_name="Número NFCe"
    )
    nfce_chave = models.CharField(
        max_length=44, 
        null=True, 
        blank=True, 
        verbose_name="Chave de Acesso NFCe"
    )
    nfce_protocolo = models.CharField(
        max_length=20, 
        null=True, 
        blank=True, 
        verbose_name="Protocolo NFCe"
    )
    nfce_emitida_em = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name="NFCe Emitida em"
    )

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Pedido #{self.id} da Comanda #{self.comanda.numero}"
    
    def save(self, *args, **kwargs):
        if not self.pk: # Se é um novo pedido
            last_seq = Pedido.objects.filter(comanda=self.comanda).aggregate(models.Max('pedido_seq'))['pedido_seq__max'] or 0
            self.pedido_seq = last_seq + 1
        super().save(*args, **kwargs)

    def update_total(self):
        """Atualizar o valor total do pedido."""
        total = sum(item.total_price for item in self.items.all())
        self.total_amount = total
        self.save(update_fields=['total_amount'])
        # Após atualizar o total do pedido, atualiza o total da comanda
        self.comanda.update_total()


class PedidoItem(TimeStampedModel):
    """
    Itens de um Pedido.
    (Anteriormente chamado de 'PedidoItem')
    """
    
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Pedido"
    )
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name="Produto"
    )
    
    quantity = models.PositiveIntegerField(
        default=1,
        verbose_name="Quantidade"
    )
    
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Preço Unitário"
    )
    
    observations = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observações do Item",
        help_text="Ex: Sem cebola, extra queijo"
    )

    class Meta:
        verbose_name = "Item do Pedido"
        verbose_name_plural = "Itens do Pedido"
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"
    
    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.product.price
        
        super().save(*args, **kwargs)
        
        # Atualizar total do pedido
        self.pedido.update_total()
    
    def delete(self, *args, **kwargs):
        pedido = self.pedido
        super().delete(*args, **kwargs)
        pedido.update_total()
    
    @property
    def total_price(self):
        """Preço total do item"""
        return self.quantity * self.unit_price
