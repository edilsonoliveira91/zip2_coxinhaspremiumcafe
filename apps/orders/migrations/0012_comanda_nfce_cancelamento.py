# Generated manually on 2026-05-10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0011_comanda_nfce_cpf_cliente'),
    ]

    operations = [
        migrations.AddField(
            model_name='comanda',
            name='nfce_cancelada',
            field=models.BooleanField(default=False, verbose_name='NFCe Cancelada'),
        ),
        migrations.AddField(
            model_name='comanda',
            name='nfce_cancelada_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='NFCe Cancelada em'),
        ),
        migrations.AddField(
            model_name='comanda',
            name='nfce_protocolo_cancelamento',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Protocolo Cancelamento NFCe'),
        ),
    ]
