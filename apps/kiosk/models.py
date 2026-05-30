from django.db import models
from utils.image_optimizer import compress_image_field, validate_image_file_size
from core.storages import image_media_storage


class KioskSlide(models.Model):
    """Imagens do carrossel na tela inicial do kiosk."""

    image = models.ImageField(storage=image_media_storage, upload_to='kiosk/slides/', validators=[validate_image_file_size], verbose_name='Imagem')
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

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        previous_image_name = None

        if not is_new:
            previous_image_name = (
                KioskSlide.objects.filter(pk=self.pk).values_list("image", flat=True).first()
            )

        super().save(*args, **kwargs)

        if self.image and (is_new or self.image.name != previous_image_name):
            compress_image_field(self.image)
