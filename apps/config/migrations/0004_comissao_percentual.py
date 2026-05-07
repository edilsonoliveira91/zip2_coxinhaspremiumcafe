from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('config', '0003_quebra_caixa'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemconfig',
            name='comissao_percentual',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Percentual de comissão pago ao operador sobre o total de vendas do período.',
                max_digits=5,
                verbose_name='Comissão sobre Vendas (%)',
            ),
        ),
    ]
