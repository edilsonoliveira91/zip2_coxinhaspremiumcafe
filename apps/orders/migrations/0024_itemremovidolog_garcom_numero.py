# Generated manually on 2026-06-02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0023_itemremovidolog'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemremovidolog',
            name='garcom_numero',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Nº Garçom'),
        ),
    ]
