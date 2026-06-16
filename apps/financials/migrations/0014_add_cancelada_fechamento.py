from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('financials', '0013_add_cancelada_transferencia'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='fechamentocaixadiario',
            name='cancelada',
            field=models.BooleanField(default=False, verbose_name='Cancelado'),
        ),
        migrations.AddField(
            model_name='fechamentocaixadiario',
            name='cancelada_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Cancelado em'),
        ),
        migrations.AddField(
            model_name='fechamentocaixadiario',
            name='cancelada_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='fechamentos_cancelados',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Cancelado por',
            ),
        ),
    ]
