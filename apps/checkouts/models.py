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
        ('parcial', 'Pagamento Parcial'),
        ('cancelado', 'Cancelado'),
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
    
    # Forma de pagamento ('parcial' quando múltiplos métodos usados)
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='dinheiro',
        verbose_name='Forma de Pagamento'
    )

    @property
    def is_parcial(self):
        return self.payment_method == 'parcial'
    
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
        """
        Retorna lista de dicts {payment_method, total, quantidade} com a mesma
        lógica usada em financials/views.py:
          - Checkouts não-parciais: agrupados por payment_method diretamente
          - Checkouts parciais: desdobrados via CheckoutPayment por método
        Garante que alterações feitas pelo operador (alterar_pagamento) sejam refletidas.
        """
        from django.db.models import Sum, Count
        from decimal import Decimal

        checkouts = self.get_checkouts()
        parcial_qs = checkouts.filter(payment_method='parcial')
        parcial_ids = list(parcial_qs.values_list('id', flat=True))

        METODOS = ['dinheiro', 'cartao_debito', 'cartao_credito', 'pix', 'voucher']

        resultado = []
        for metodo in METODOS:
            # Checkouts simples (não-parciais) com esse método
            simples = (
                checkouts.exclude(payment_method='parcial')
                .filter(payment_method=metodo)
                .aggregate(t=Sum('total'), q=Count('id'))
            )
            total_simples = simples['t'] or Decimal('0.00')
            qtd_simples   = simples['q'] or 0

            # Porção deste método dentro de checkouts parciais (via CheckoutPayment)
            if parcial_ids:
                parcial = (
                    CheckoutPayment.objects
                    .filter(checkout_id__in=parcial_ids, payment_method=metodo)
                    .aggregate(t=Sum('amount'), q=Count('id'))
                )
                total_parcial = parcial['t'] or Decimal('0.00')
                qtd_parcial   = parcial['q'] or 0
            else:
                total_parcial = Decimal('0.00')
                qtd_parcial   = 0

            total = total_simples + total_parcial
            quantidade = qtd_simples + qtd_parcial

            if total > 0 or quantidade > 0:
                resultado.append({
                    'payment_method': metodo,
                    'total': total,
                    'quantidade': quantidade,
                })

        return resultado

class CheckoutPayment(TimeStampedModel):
    """
    Registro individual de cada método de pagamento usado em um checkout.
    Um Checkout pode ter múltiplos CheckoutPayment (pagamento parcial).
    """
    PAYMENT_METHOD_CHOICES = [
        ('dinheiro', 'Dinheiro'),
        ('cartao_debito', 'Cartão de Débito'),
        ('cartao_credito', 'Cartão de Crédito'),
        ('pix', 'PIX'),
        ('voucher', 'Voucher'),
    ]

    checkout = models.ForeignKey(
        Checkout,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Checkout'
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name='Forma de Pagamento'
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Valor'
    )

    class Meta:
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.get_payment_method_display()} - R$ {self.amount}'
