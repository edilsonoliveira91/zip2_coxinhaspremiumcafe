# Generated manually on 2026-05-10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0010_comanda_nfce_xml_path'),
    ]

    operations = [
        migrations.AddField(
            model_name='comanda',
            name='nfce_cpf_cliente',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='CPF Cliente NFCe'),
        ),
    ]
