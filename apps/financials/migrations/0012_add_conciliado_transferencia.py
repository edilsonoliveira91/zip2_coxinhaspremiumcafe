from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('financials', '0011_add_data_prevista_liquidacao'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='caixaadmtransferencia',
            name='conciliado',
            field=models.BooleanField(default=False, verbose_name='Conciliado'),
        ),
        migrations.AddField(
            model_name='caixaadmtransferencia',
            name='conciliado_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Conciliado em'),
        ),
        migrations.AddField(
            model_name='caixaadmtransferencia',
            name='conciliado_por',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='transferencias_conciliadas',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Conciliado por',
            ),
        ),
    ]
