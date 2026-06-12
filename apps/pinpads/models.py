from django.db import models
from django.contrib.auth import get_user_model
from utils.models import TimeStampedModel

User = get_user_model()


class Pinpad(TimeStampedModel):
    name = models.CharField(max_length=100, verbose_name="Nome da Pinpad")
    dias_credito = models.PositiveIntegerField(default=30, verbose_name="Dias Crédito")
    dias_debito = models.PositiveIntegerField(default=1, verbose_name="Dias Débito")
    dias_pix = models.PositiveIntegerField(default=1, verbose_name="Dias PIX")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='pinpads_created', verbose_name="Criado por"
    )
    updated_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='pinpads_updated',
        null=True, blank=True, verbose_name="Atualizado por"
    )

    class Meta:
        verbose_name = "Pinpad"
        verbose_name_plural = "Pinpads"
        ordering = ['-is_active', 'name']

    def __str__(self):
        status = "ATIVO" if self.is_active else "INATIVO"
        return f"{status}: {self.name}"

    def save(self, *args, **kwargs):
        if self.is_active:
            Pinpad.objects.exclude(pk=self.pk).filter(is_active=True).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_active_pinpads(cls):
        return cls.objects.filter(is_active=True).order_by('name')


class BandeiraPinpad(models.Model):
    pinpad = models.ForeignKey(Pinpad, on_delete=models.CASCADE, related_name='bandeiras')
    nome = models.CharField(max_length=100, verbose_name="Bandeira")
    taxa_credito = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Taxa Crédito (%)")
    taxa_debito = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Taxa Débito (%)")

    class Meta:
        verbose_name = "Bandeira"
        verbose_name_plural = "Bandeiras"
        ordering = ['nome']

    def __str__(self):
        return f"{self.nome} — Créd {self.taxa_credito}% / Déb {self.taxa_debito}%"
