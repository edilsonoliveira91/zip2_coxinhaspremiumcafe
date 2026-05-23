from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0016_product_visivel_kiosk'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='product',
            options={
                'ordering': ['category', 'name'],
                'permissions': [
                    ('manage_product_availability', 'Pode gerenciar disponibilidade de produtos e opcionais'),
                    ('manage_nfce_fields', 'Pode editar campos NFC-e do produto'),
                ],
                'verbose_name': 'Produto',
                'verbose_name_plural': 'Produtos',
            },
        ),
    ]
