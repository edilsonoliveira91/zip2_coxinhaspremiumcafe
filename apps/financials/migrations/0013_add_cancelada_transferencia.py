from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('financials', '0012_add_conciliado_transferencia'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='caixaadmtransferencia',
            name='cancelada',
            field=models.BooleanField(default=False, verbose_name='Cancelada'),
        ),
        migrations.AddField(
            model_name='caixaadmtransferencia',
            name='cancelada_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Cancelada em'),
        ),
        migrations.AddField(
            model_name='caixaadmtransferencia',
            name='cancelada_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='transferencias_canceladas',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Cancelada por',
            ),
        ),
    ]
