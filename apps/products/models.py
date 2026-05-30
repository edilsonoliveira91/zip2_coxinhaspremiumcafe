from django.db import models
from utils.models import TimeStampedModel
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.conf import settings
from utils.image_optimizer import compress_image_field, validate_image_file_size
from core.storages import image_media_storage


class Product(TimeStampedModel):
    """
    Modelo de produto individual para a cafeteria
    """
    CATEGORY_CHOICES = [
        ('salgados', 'Salgados'),
        ('cafes', 'Cafés'),
        ('cafes_premium', 'Cafés Premium'),
        ('minisalgados', 'Mini Salgados'),
        ('sanduiches', 'Sanduíches'),
        ('sucos', 'Sucos'),
        ('chas', 'Chás'),
        ('bebidas', 'Bebidas'),
        ('doces', 'Doces'),
        
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
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Preço"
    )
    
    show_in_menu = models.BooleanField(
        default=True,
        verbose_name="Mostrar no Cardápio"
    )

    visivel_kiosk = models.BooleanField(
        default=True,
        verbose_name="Visível no Kiosk"
    )

    DESTINO_CHOICES = [
        ('balcao', 'Balcão'),
        ('cozinha', 'Cozinha'),
    ]
    destino_producao = models.CharField(
        max_length=10,
        choices=DESTINO_CHOICES,
        default='balcao',
        verbose_name="Destino de Produção"
    )

    image = models.ImageField(
        storage=image_media_storage,
        upload_to='products/',
        blank=True,
        null=True,
        validators=[validate_image_file_size],
        verbose_name="Imagem do Produto"
    )

    # --- Campos NFC-e ---
    ncm = models.CharField(
        max_length=10,
        blank=True,
        default='',
        verbose_name="NCM"
    )
    cfop = models.CharField(
        max_length=10,
        blank=True,
        default='',
        verbose_name="CFOP"
    )
    cst_icms = models.CharField(
        max_length=5,
        blank=True,
        default='',
        verbose_name="CST ICMS"
    )
    base_calculo_icms = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="% Base de Cálculo ICMS"
    )
    aliq_icms = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Alíquota ICMS (%)"
    )
    codigo_cbenef = models.CharField(
        max_length=20,
        blank=True,
        default='',
        verbose_name="Código CBENEF"
    )
    dados_adicionais_nfe = models.TextField(
        blank=True,
        default='',
        verbose_name="Dados Adicionais da NF-e"
    )
    cst_pis_cofins = models.CharField(
        max_length=5,
        blank=True,
        default='',
        verbose_name="CST PIS e COFINS"
    )
    aliq_pis = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="Alíquota PIS (%)"
    )
    aliq_cofins = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=Decimal('0.000'),
        verbose_name="Alíquota COFINS (%)"
    )
    cst_ibs_cbs = models.CharField(
        max_length=10,
        blank=True,
        default='',
        verbose_name="CST IBS CBS"
    )
    cclass = models.CharField(
        max_length=20,
        blank=True,
        default='',
        verbose_name="CCLASS"
    )

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ['category', 'name']
        permissions = [
            ('manage_nfce_fields', 'Pode editar campos NFC-e do produto'),
        ]

    def __str__(self):
        return f"{self.name} - R$ {self.price}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        previous_image_name = None

        if not is_new:
            previous_image_name = (
                Product.objects.filter(pk=self.pk).values_list("image", flat=True).first()
            )

        super().save(*args, **kwargs)

        if self.image and (is_new or self.image.name != previous_image_name):
            compress_image_field(self.image)


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
        storage=image_media_storage,
        upload_to='combos/',
        blank=True,
        null=True,
        validators=[validate_image_file_size],
        verbose_name="Imagem do Combo"
    )

    class Meta:
        verbose_name = "Combo"
        verbose_name_plural = "Combos"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        previous_image_name = None

        if not is_new:
            previous_image_name = (
                Combo.objects.filter(pk=self.pk).values_list("image", flat=True).first()
            )

        super().save(*args, **kwargs)

        if self.image and (is_new or self.image.name != previous_image_name):
            compress_image_field(self.image)

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

class Adicional(TimeStampedModel):
    """
    Adicional / complemento disponível para produtos
    """
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='adicionais',
        null=True,
        blank=True,
        verbose_name="Produto",
    )

    name = models.CharField(
        max_length=100,
        verbose_name="Nome"
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Descrição"
    )

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Preço"
    )

    class Meta:
        verbose_name = 'Adicional'
        verbose_name_plural = 'Adicionais'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - R$ {self.price:.2f}"


class OpcionalObrigatorio(TimeStampedModel):
    """
    Opção obrigatória de um produto (ex.: sabor do sorvete).
    Cliente deve escolher exatamente uma no kiosk.
    """
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='opcionais_obrigatorios',
        null=True,
        blank=True,
        verbose_name="Produto",
    )

    name = models.CharField(
        max_length=100,
        verbose_name="Nome"
    )

    description = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Descrição"
    )

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Preço"
    )

    class Meta:
        verbose_name = 'Opcional Obrigatório'
        verbose_name_plural = 'Opcionais Obrigatórios'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} - R$ {self.price:.2f}"


class StockEntry(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_entries',
        verbose_name="Produto"
    )
    opcional_obrigatorio = models.ForeignKey(
        'products.OpcionalObrigatorio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_entries',
        verbose_name="Sabor / Variação"
    )
    date = models.DateField(verbose_name="Data de Entrada")
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Quantidade"
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Valor Unitário (R$)"
    )
    notes = models.CharField(max_length=255, blank=True, verbose_name="Observações")
    created_at = models.DateTimeField(auto_now_add=True)  # já deve estar importado no topo do arquivo
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_entries_created',
        verbose_name="Registrado por"
    )

    class Meta:
        verbose_name = "Entrada de Estoque"
        verbose_name_plural = "Entradas de Estoque"
        ordering = ['-date', '-created_at']

    def __str__(self):
        sufixo = f" ({self.opcional_obrigatorio.name})" if self.opcional_obrigatorio else ''
        return f"{self.product.name}{sufixo} — {self.quantity} un. em {self.date}"

    @property
    def total_cost(self):
        return self.unit_cost * self.quantity

class StockExit(models.Model):
    """
    Saída de estoque gerada automaticamente quando um Pedido é entregue.
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_exits',
        verbose_name="Produto"
    )
    opcional_obrigatorio = models.ForeignKey(
        'products.OpcionalObrigatorio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_exits',
        verbose_name="Sabor / Variação"
    )
    quantity = models.PositiveIntegerField(verbose_name="Quantidade")
    pedido = models.ForeignKey(
        'orders.Pedido',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='stock_exits',
        verbose_name="Pedido"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Saída de Estoque"
        verbose_name_plural = "Saídas de Estoque"
        ordering = ['-created_at']

    def __str__(self):
        sufixo = f" ({self.opcional_obrigatorio.name})" if self.opcional_obrigatorio else ''
        return f"{self.product.name}{sufixo} — -{self.quantity} un."


class RawMaterial(TimeStampedModel):
    """Matéria Prima — ingrediente ou insumo cadastrado no sistema"""

    UNIT_CHOICES = [
        ('kg',      'Quilograma (kg)'),
        ('litros',  'Litro (L)'),
        ('unidade', 'Unidade (un)'),
        ('pacote',  'Pacote (pct)'),
    ]

    name = models.CharField(
        max_length=150,
        unique=True,
        verbose_name='Nome'
    )
    unit_measure = models.CharField(
        max_length=10,
        choices=UNIT_CHOICES,
        default='kg',
        verbose_name='Unidade de Medida'
    )

    class Meta:
        verbose_name = 'Matéria Prima'
        verbose_name_plural = 'Matérias Primas'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_unit_measure_display()})'
