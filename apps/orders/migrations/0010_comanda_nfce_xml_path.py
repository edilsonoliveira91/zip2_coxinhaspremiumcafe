# Generated manually on 2026-05-10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0009_add_cortesia_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='comanda',
            name='nfce_xml_path',
            field=models.CharField(blank=True, max_length=500, null=True, verbose_name='Caminho XML NFCe'),
        ),
    ]
