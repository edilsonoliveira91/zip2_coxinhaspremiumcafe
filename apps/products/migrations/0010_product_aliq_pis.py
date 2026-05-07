# Generated manually

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0009_product_destino_producao'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='aliq_pis',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                max_digits=5,
                verbose_name='Alíquota PIS (%)',
            ),
        ),
    ]
