# Generated manually

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0010_product_aliq_pis'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='aliq_pis',
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal('0.000'),
                max_digits=6,
                verbose_name='Alíquota PIS (%)',
            ),
        ),
        migrations.AlterField(
            model_name='product',
            name='aliq_cofins',
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal('0.000'),
                max_digits=6,
                verbose_name='Alíquota COFINS (%)',
            ),
        ),
    ]
