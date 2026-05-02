from django.db import migrations, models
import decimal


class Migration(migrations.Migration):

    dependencies = [
        ('config', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemconfig',
            name='troco_inicial',
            field=models.DecimalField(
                decimal_places=2,
                default=decimal.Decimal('50.00'),
                help_text='Valor padrão com que o caixa inicia todos os dias.',
                max_digits=8,
                verbose_name='Troco Inicial (R$)',
            ),
        ),
    ]
