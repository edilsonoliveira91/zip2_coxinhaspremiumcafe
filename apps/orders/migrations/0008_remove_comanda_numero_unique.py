from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0007_add_cancelada_status_and_motivo'),
    ]

    operations = [
        migrations.AlterField(
            model_name='comanda',
            name='numero',
            field=models.CharField(
                help_text='Número identificado pelo código de barras do pager.',
                max_length=50,
                verbose_name='Número da Comanda',
            ),
        ),
    ]
