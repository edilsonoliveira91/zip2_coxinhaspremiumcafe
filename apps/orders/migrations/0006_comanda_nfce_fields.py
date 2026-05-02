from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0005_comanda_custom_permissions'),
    ]

    operations = [
        migrations.AddField(
            model_name='comanda',
            name='nfce_numero',
            field=models.IntegerField(blank=True, null=True, verbose_name='Número NFCe'),
        ),
        migrations.AddField(
            model_name='comanda',
            name='nfce_chave',
            field=models.CharField(blank=True, max_length=44, null=True, verbose_name='Chave de Acesso NFCe'),
        ),
        migrations.AddField(
            model_name='comanda',
            name='nfce_protocolo',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Protocolo NFCe'),
        ),
        migrations.AddField(
            model_name='comanda',
            name='nfce_emitida_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='NFCe Emitida em'),
        ),
    ]
