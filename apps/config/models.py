from django.db import models
from decimal import Decimal
from utils.models import TimeStampedModel
from django.conf import settings


class _SingletonMixin(models.Model):
    """Base para instância única (pk=1) - não usar mais, mantido para compatibilidade."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ConfigTempoEspera(TimeStampedModel):
    max_order_time_minutes = models.PositiveIntegerField(
        default=20,
        verbose_name="Tempo Máximo de Espera (minutos)",
        help_text="Pedidos abertos após este tempo farão a comanda piscar em vermelho.",
    )

    class Meta:
        verbose_name = "Tempo de Espera"
        verbose_name_plural = "Tempo de Espera"

    def __str__(self):
        return f"Tempo de Espera: {self.max_order_time_minutes} min"
    
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ConfigTrocoInicial(TimeStampedModel):
    troco_inicial = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("50.00"),
        verbose_name="Troco Inicial (R$)",
        help_text="Valor padrão com que o caixa inicia todos os dias.",
    )

    class Meta:
        verbose_name = "Troco Inicial"
        verbose_name_plural = "Troco Inicial"

    def __str__(self):
        return f"Troco Inicial: R$ {self.troco_inicial}"
    
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ConfigQuebraCaixa(TimeStampedModel):
    quebra_positiva = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("5.00"),
        verbose_name="Quebra de Caixa Positiva (R$)",
        help_text="Margem máxima tolerada de sobra em espécie.",
    )
    quebra_negativa = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("5.00"),
        verbose_name="Quebra de Caixa Negativa (R$)",
        help_text="Margem máxima tolerada de falta em espécie.",
    )

    class Meta:
        verbose_name = "Quebra de Caixa"
        verbose_name_plural = "Quebra de Caixa"

    def __str__(self):
        return f"Quebra: +R${self.quebra_positiva} / -R${self.quebra_negativa}"
    
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class ConfigComissao(TimeStampedModel):
    comissao_percentual = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Comissão sobre Vendas (%)",
        help_text="Percentual de comissão pago ao operador sobre o total de vendas do período.",
    )

    class Meta:
        verbose_name = "Comissão"
        verbose_name_plural = "Comissão"

    def __str__(self):
        return f"Comissão: {self.comissao_percentual}%"
    
    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# Mantido para não quebrar migrações antigas; novos códigos devem usar os modelos acima.
class SystemConfig(models.Model):
    max_order_time_minutes = models.PositiveIntegerField(default=20)
    troco_inicial = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("50.00"))
    quebra_positiva = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("5.00"))
    quebra_negativa = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("5.00"))
    comissao_percentual = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        verbose_name = "Configuração do Sistema (legado)"
        verbose_name_plural = "Configurações do Sistema (legado)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Garcom(models.Model):
    numero = models.PositiveSmallIntegerField(
        unique=True,
        verbose_name="Número do Garçom",
    )
    nome = models.CharField(max_length=100, verbose_name="Nome")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Cadastrado em")
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='garcons_cadastrados',
        verbose_name="Cadastrado por",
    )

    class Meta:
        verbose_name = "Garçom"
        verbose_name_plural = "Garçons"
        ordering = ['numero']

    def __str__(self):
        return f"#{self.numero} - {self.nome}"


class ConfigKioskPin(TimeStampedModel):
    pin = models.CharField(
        max_length=4,
        default='0000',
        verbose_name="PIN do Kiosk",
        help_text="PIN de 4 dígitos que o funcionário deve digitar para abrir uma mesa no kiosk.",
    )

    class Meta:
        verbose_name = "PIN do Kiosk"
        verbose_name_plural = "PIN do Kiosk"

    def __str__(self):
        return f"PIN do Kiosk: {self.pin}"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'pin': '0000'})
        return obj
