# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0008_product_nfce_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='destino_producao',
            field=models.CharField(
                choices=[('balcao', 'Balcão'), ('cozinha', 'Cozinha')],
                default='balcao',
                max_length=10,
                verbose_name='Destino de Produção',
            ),
        ),
    ]
