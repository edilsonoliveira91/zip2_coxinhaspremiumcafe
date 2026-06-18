from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0025_add_migrada_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='comanda',
            name='forma_pagamento_kiosk',
            field=models.CharField(blank=True, max_length=20, null=True, verbose_name='Forma de Pagamento (Kiosk)'),
        ),
    ]
