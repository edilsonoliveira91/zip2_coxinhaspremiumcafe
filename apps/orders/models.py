from django.db import models
from django.conf import settings
from utils.models import TimeStampedModel
from products.models import Product
from django.db.models import Sum
from decimal import Decimal

class Comanda(TimeStampedModel):
    """
    Modelo para a Comanda Eletrônica (o pager físico).
    Cada comanda pode conter múltiplos pedidos.
    """
    STATUS_CHOICES = [
        ('livre', 'Livre'),
        ('em_uso', 'Em Uso'),
        ('fechada', 'Fechada'),
        ('aguardando_caixa', 'Aguardando Caixa'),
        ('cancelada', 'Cancelada'),
        ('cortesia', 'Cortesia'),
        ('migrada', 'Migrada'),
    ]

    numero = models.CharField(
        max_length=50,
        verbose_name="Número da Comanda",
        help_text="Número identificado pelo código de barras do pager."
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

    # Campos para NFCe (emitida por comanda)
    nfce_numero = models.IntegerField(null=True, blank=True, verbose_name="Número NFCe")
    nfce_chave = models.CharField(max_length=44, null=True, blank=True, verbose_name="Chave de Acesso NFCe")
    nfce_protocolo = models.CharField(max_length=20, null=True, blank=True, verbose_name="Protocolo NFCe")
    nfce_emitida_em = models.DateTimeField(null=True, blank=True, verbose_name="NFCe Emitida em")
    nfce_xml_path = models.CharField(max_length=500, null=True, blank=True, verbose_name="Caminho XML NFCe")
    nfce_cpf_cliente = models.CharField(max_length=20, null=True, blank=True, verbose_name="CPF Cliente NFCe")
    forma_pagamento_kiosk = models.CharField(max_length=20, null=True, blank=True, verbose_name="Forma de Pagamento (Kiosk)")
    nfce_cancelada = models.BooleanField(default=False, verbose_name="NFCe Cancelada")
    nfce_cancelada_em = models.DateTimeField(null=True, blank=True, verbose_name="NFCe Cancelada em")
    nfce_protocolo_cancelamento = models.CharField(max_length=20, null=True, blank=True, verbose_name="Protocolo Cancelamento NFCe")

    motivo_cancelamento = models.TextField(
        blank=True,
        null=True,
        verbose_name="Motivo do Cancelamento"
    )

    # Controle de atendimento
    em_atendimento = models.BooleanField(
        default=False,
        verbose_name="Em Atendimento"
    )
    atendente_numero = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Número do Atendente"
    )
    atendimento_em = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Iniciado Atendimento em"
    )

    @property
    def tem_nfce(self):
        return bool(self.nfce_numero)

    class Meta:
        verbose_name = "Comanda"
        verbose_name_plural = "Comandas"
        ordering = ['-created_at']
        permissions = [
            ('view_order', 'Pode visualizar comandas'),
            ('add_order', 'Pode criar comandas'),
            ('change_order', 'Pode editar comandas'),
            ('delete_order', 'Pode excluir comandas'),
            ('cancel_closed_comanda', 'Pode cancelar comanda finalizada'),
        ]

    def __str__(self):
        return f"Comanda #{self.numero}"

    def update_total(self):
        """Atualiza o valor total da comanda somando os totais de seus pedidos.
        Comandas já finalizadas (fechada/cancelada/cortesia) são imutáveis — o valor
        registrado no Checkout não pode ser alterado retroativamente.
        """
        IMUTAVEIS = ('fechada', 'cancelada', 'cortesia', 'migrada')
        if self.status in IMUTAVEIS:
            return  # Não altera o valor de comandas já encerradas
        total = self.pedidos.filter(status__in=['aguardando', 'preparando', 'pronta', 'entregue']).aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
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

    impresso = models.BooleanField(
        default=False,
        verbose_name="Impresso"
    )

    # Atendente responsável por este pedido
    atendente_numero = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name="Número do Atendente"
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
        total = sum((item.total_price for item in self.items.all()), Decimal('0.00'))
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
        on_delete=models.PROTECT,
        verbose_name="Produto"
    )
    opcional_obrigatorio = models.ForeignKey(
        'products.OpcionalObrigatorio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedido_items',
        verbose_name="Sabor / Variação"
    )
    product_name = models.CharField(
        max_length=100,
        blank=True,
        default='',
        verbose_name="Nome do Produto (snapshot)"
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
        sufixo = f" ({self.opcional_obrigatorio.name})" if self.opcional_obrigatorio else ''
        return f"{self.quantity}x {self.product.name}{sufixo}"
    
    def save(self, *args, **kwargs):
        if self.unit_price is None:
            self.unit_price = self.product.price
        if not self.product_name:
            self.product_name = self.product.name
        
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

class ComandaPartialPayment(TimeStampedModel):
    """
    Registro de pagamentos parciais de uma comanda ainda aberta.
    """

    PAYMENT_METHOD_CHOICES = [
        ('dinheiro', 'Dinheiro'),
        ('cartao_debito', 'Cartão de Débito'),
        ('cartao_credito', 'Cartão de Crédito'),
        ('pix', 'PIX'),
        ('voucher', 'Voucher'),
    ]

    comanda = models.ForeignKey(
        Comanda,
        on_delete=models.CASCADE,
        related_name='partial_payments',
        verbose_name='Comanda'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name='Forma de Pagamento'
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Valor Pago'
    )

    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_partial_payments',
        verbose_name='Registrado por'
    )

    notes = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Observações'
    )

    class Meta:
        verbose_name = 'Pagamento Parcial de Comanda'
        verbose_name_plural = 'Pagamentos Parciais de Comanda'
        ordering = ['created_at']

    def __str__(self):
        return f'Comanda #{self.comanda.numero} - {self.get_payment_method_display()} - R$ {self.amount}'



class ItemRemovidoLog(models.Model):
    product_name = models.CharField(max_length=100, verbose_name="Produto")
    quantity = models.PositiveIntegerField(verbose_name="Quantidade")
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço Unitário")
    observations = models.TextField(blank=True, null=True, verbose_name="Observações")
    comanda_numero = models.CharField(max_length=50, verbose_name="Comanda")
    pedido_seq = models.PositiveIntegerField(verbose_name="Nº Pedido")
    garcom_numero = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Nº Garçom")
    removido_em = models.DateTimeField(auto_now_add=True, verbose_name="Removido em")
    removido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='itens_removidos',
        verbose_name="Removido por",
    )

    class Meta:
        verbose_name = "Item Removido"
        verbose_name_plural = "Itens Removidos"
        ordering = ['-removido_em']

    def __str__(self):
        return f"{self.quantity}x {self.product_name} — Comanda {self.comanda_numero} — {self.removido_em}"
