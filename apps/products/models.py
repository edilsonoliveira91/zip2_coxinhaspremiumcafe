from django.db import models
from utils.models import TimeStampedModel
from django.core.validators import MinValueValidator
from decimal import Decimal


class Product(TimeStampedModel):
    """
    Modelo de produto individual para a cafeteria
    """
    CATEGORY_CHOICES = [
        ('bebidas', 'Bebidas'),
        ('salgados', 'Salgados'),
        ('doces', 'Doces'),
        ('lanches', 'Lanches'),
        ('outros', 'Outros'),
    ]
    
    name = models.CharField(
        max_length=100,
        verbose_name="Nome do Produto"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descrição"
    )
    
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        verbose_name="Categoria"
    )
    
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Preço"
    )
    
    show_in_menu = models.BooleanField(
        default=True,
        verbose_name="Mostrar no Cardápio"
    )
    
    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True,
        verbose_name="Imagem do Produto"
    )

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} - R$ {self.price}"


class Combo(TimeStampedModel):
    """
    Modelo de combo que agrupa produtos com preços especiais
    """
    name = models.CharField(
        max_length=100,
        verbose_name="Nome do Combo"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descrição do Combo"
    )
    
    show_in_menu = models.BooleanField(
        default=True,
        verbose_name="Mostrar no Cardápio"
    )
    
    image = models.ImageField(
        upload_to='combos/',
        blank=True,
        null=True,
        verbose_name="Imagem do Combo"
    )

    class Meta:
        verbose_name = "Combo"
        verbose_name_plural = "Combos"
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_price(self):
        """Retorna o preço total do combo"""
        return sum(item.combo_price for item in self.items.all())

    @property
    def original_price(self):
        """Retorna o preço original dos produtos sem desconto"""
        return sum(item.product.price for item in self.items.all())

    @property
    def discount_amount(self):
        """Retorna o valor do desconto"""
        return self.original_price - self.total_price

    @property
    def discount_percentage(self):
        """Retorna a porcentagem de desconto"""
        if self.original_price > 0:
            return round(((self.original_price - self.total_price) / self.original_price) * 100, 2)
        return 0


class ComboItem(models.Model):
    """
    Modelo intermediário para produtos dentro de um combo
    """
    combo = models.ForeignKey(
        Combo,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Combo"
    )
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name="Produto"
    )
    
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        verbose_name="Quantidade"
    )
    
    combo_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Preço no Combo",
        help_text="Preço especial deste produto no combo"
    )

    class Meta:
        verbose_name = "Item do Combo"
        verbose_name_plural = "Itens do Combo"
        unique_together = ['combo', 'product']

    def __str__(self):
        return f"{self.combo.name} - {self.product.name} (R$ {self.combo_price})"

    @property
    def total_combo_price(self):
        """Retorna o preço total considerando a quantidade"""
        return self.combo_price * self.quantity

    @property
    def original_total_price(self):
        """Retorna o preço original total considerando a quantidade"""
        return self.product.price * self.quantity