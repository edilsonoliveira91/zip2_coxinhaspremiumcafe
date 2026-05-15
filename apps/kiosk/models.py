from django.db import models


class KioskSlide(models.Model):
    """Imagens do carrossel na tela inicial do kiosk."""

    image = models.ImageField(upload_to='kiosk/slides/', verbose_name='Imagem')
    title = models.CharField(max_length=120, blank=True, verbose_name='Título (opcional)')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Ordem')
    is_active = models.BooleanField(default=True, verbose_name='Ativo')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Slide do Kiosk'
        verbose_name_plural = 'Slides do Kiosk'

    def __str__(self):
        return self.title or f'Slide #{self.pk}'
