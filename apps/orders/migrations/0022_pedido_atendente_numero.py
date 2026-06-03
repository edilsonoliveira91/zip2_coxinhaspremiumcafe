# Generated manually on 2026-06-01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0021_comanda_atendimento_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='pedido',
            name='atendente_numero',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Número do Atendente'),
        ),
    ]
