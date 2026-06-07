from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0024_itemremovidolog_garcom_numero'),
    ]

    operations = [
        migrations.AlterField(
            model_name='comanda',
            name='status',
            field=models.CharField(
                choices=[
                    ('livre', 'Livre'),
                    ('em_uso', 'Em Uso'),
                    ('fechada', 'Fechada'),
                    ('aguardando_caixa', 'Aguardando Caixa'),
                    ('cancelada', 'Cancelada'),
                    ('cortesia', 'Cortesia'),
                    ('migrada', 'Migrada'),
                ],
                default='livre',
                max_length=20,
                verbose_name='Status',
            ),
        ),
    ]
