# Generated manually on 2026-06-01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0020_pedidoitem_opcional_obrigatorio'),
    ]

    operations = [
        migrations.AddField(
            model_name='comanda',
            name='em_atendimento',
            field=models.BooleanField(default=False, verbose_name='Em Atendimento'),
        ),
        migrations.AddField(
            model_name='comanda',
            name='atendente_numero',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Número do Atendente'),
        ),
        migrations.AddField(
            model_name='comanda',
            name='atendimento_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Iniciado Atendimento em'),
        ),
    ]
