from django.db import models
from django.conf import settings
from utils.models import TimeStampedModel
from products.models import Product


class Order(TimeStampedModel):
    """
    Modelo para Comandas Eletrônicas
    """
    
    STATUS_CHOICES = [
        ('aguardando', 'Aguardando'),
        ('preparando', 'Em Preparo'),
        ('pronta', 'Pronta'),
        ('entregue', 'Entregue'),
        ('cancelada', 'Cancelada'),
    ]
    
    # Código de barras Code 39 - 4 dígitos
    code = models.CharField(
        max_length=4,
        unique=True,
        verbose_name="Código da Comanda",
        help_text="Código de 4 dígitos para Code 39"
    )
    
    # Nome da comanda (Mesa 5, João Silva, etc.)
    name = models.CharField(
        max_length=100,
        verbose_name="Nome da Comanda",
        help_text="Ex: Mesa 5, João Silva, Balcão 1"
    )
    
    # Observações especiais
    observations = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observações",
        help_text="Observações especiais para a comanda"
    )
    
    # Status da comanda
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='aguardando',
        verbose_name="Status"
    )
    
    # Valor total da comanda
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

    class Meta:
        verbose_name = "Comanda"
        verbose_name_plural = "Comandas"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['code']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"#{self.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        # Gerar código de 4 dígitos se for uma nova comanda
        if not self.pk and not self.code:
            self.code = self.generate_code()
        
        super().save(*args, **kwargs)
    
    def generate_code(self):
        """Gerar código de 4 dígitos único"""
        import random
        
        # Tentar até encontrar um código disponível
        for _ in range(1000):  # Máximo 1000 tentativas
            code = f"{random.randint(1000, 9999)}"
            if not Order.objects.filter(code=code).exists():
                return code
        
        # Se não encontrar, usar sequencial
        last_code = Order.objects.filter(
            code__isnull=False
        ).order_by('-code').first()
        
        if last_code:
            try:
                next_code = int(last_code.code) + 1
                if next_code > 9999:
                    next_code = 1000  # Reinicia
                return f"{next_code:04d}"
            except ValueError:
                return "1000"
        
        return "1000"
    
    @property
    def barcode_data(self):
        """Dados para gerar código de barras Code 39"""
        return self.code
    
    @property
    def preparation_time(self):
        """Tempo de preparo em minutos"""
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds() / 60
        return None
    
    @property
    def total_time(self):
        """Tempo total em minutos"""
        if self.created_at and self.delivered_at:
            return (self.delivered_at - self.created_at).total_seconds() / 60
        return None

class OrderItem(TimeStampedModel):
    """
    Itens da Comanda
    """
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Comanda"
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
        verbose_name="Preço Unitário"
    )
    
    # Observações específicas do item
    observations = models.TextField(
        blank=True,
        null=True,
        verbose_name="Observações do Item",
        help_text="Ex: Sem cebola, extra queijo"
    )

    class Meta:
        verbose_name = "Item da Comanda"
        verbose_name_plural = "Itens da Comanda"
        ordering = ['id']

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"
    
    def save(self, *args, **kwargs):
        # Definir preço unitário baseado no produto se não estiver definido
        if not self.unit_price:
            self.unit_price = self.product.price
        
        super().save(*args, **kwargs)
        
        # Atualizar total da comanda
        self.order.update_total()
    
    def delete(self, *args, **kwargs):
        order = self.order
        super().delete(*args, **kwargs)
        order.update_total()
    
    @property
    def total_price(self):
        """Preço total do item"""
        return self.quantity * self.unit_price


# Método para atualizar total da comanda
def update_total(self):
    """Atualizar o valor total da comanda"""
    total = sum(item.total_price for item in self.items.all())
    self.total_amount = total
    self.save(update_fields=['total_amount'])

# Adicionar o método à classe Order
Order.add_to_class('update_total', update_total)