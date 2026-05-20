from django.db import models
from django.conf import settings


class TimeStampedModel(models.Model):
    """
    Modelo base abstrato que fornece campos de auditoria padrão
    para todos os modelos do sistema ERP como: ID, criado em, atualizado em, criado por, atualizado por e ativo.
    """
    id = models.AutoField(
        primary_key=True,
        verbose_name="ID"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Criado em"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Atualizado em"
    )
    
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
        verbose_name="Criado por"
    )
    
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated',
        verbose_name="Atualizado por"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo"
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.__class__.__name__} - {self.id}"

class SyncLog(models.Model):
    """
    Registro de cada sincronização entre Railway (remoto) e servidor local.
    Visível apenas no Django Admin para superusers.
    """

    DIRECTION_CHOICES = [
        ('railway_to_local', 'Railway → Local'),
        ('local_to_railway', 'Local → Railway'),
        ('bilateral', 'Bilateral'),
    ]

    STATUS_CHOICES = [
        ('running', 'Em andamento'),
        ('success', 'Sucesso'),
        ('partial', 'Parcial'),
        ('error', 'Erro'),
    ]

    TRIGGER_CHOICES = [
        ('automatic', 'Automático'),
        ('manual', 'Manual'),
    ]

    started_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Iniciado em"
    )

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Finalizado em"
    )

    duration_seconds = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Duração (s)"
    )

    direction = models.CharField(
        max_length=20,
        choices=DIRECTION_CHOICES,
        default='railway_to_local',
        verbose_name="Direção"
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='running',
        verbose_name="Status"
    )

    error_message = models.TextField(
        null=True,
        blank=True,
        verbose_name="Mensagem de Erro"
    )

    records_downloaded = models.IntegerField(
        default=0,
        verbose_name="Registros baixados"
    )

    records_uploaded = models.IntegerField(
        default=0,
        verbose_name="Registros enviados"
    )

    records_created = models.IntegerField(
        default=0,
        verbose_name="Registros criados"
    )

    records_updated = models.IntegerField(
        default=0,
        verbose_name="Registros atualizados"
    )

    records_deleted = models.IntegerField(
        default=0,
        verbose_name="Registros desativados"
    )

    images_downloaded = models.IntegerField(
        default=0,
        verbose_name="Imagens baixadas"
    )

    tables_synced = models.TextField(
        null=True,
        blank=True,
        verbose_name="Tabelas sincronizadas"
    )

    sync_from_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Filtro a partir de"
    )

    triggered_by = models.CharField(
        max_length=10,
        choices=TRIGGER_CHOICES,
        default='automatic',
        verbose_name="Disparado por"
    )

    local_server_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="IP do servidor local"
    )

    class Meta:
        verbose_name = "Log de Sync"
        verbose_name_plural = "Logs de Sync"
        ordering = ['-started_at']

    def __str__(self):
        direction_display = dict(self.DIRECTION_CHOICES).get(self.direction, self.direction)
        status_display = dict(self.STATUS_CHOICES).get(self.status, self.status)
        return f"[{self.started_at.strftime('%d/%m/%Y %H:%M:%S')}] {direction_display} — {status_display}"
